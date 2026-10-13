"""Discover a disjoint partition of real GRIB messages and export strict groups."""

from collections import Counter, defaultdict
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import re
from tempfile import TemporaryDirectory

import cfgrib
import eccodes

from grib_to_csv import dataset_metadata, dataset_to_dataframe, export_dataframe

BASE_KEYS = ("dataType", "numberOfPoints", "gridType", "typeOfLevel", "level", "stepType")
GEOMETRY_KEYS = ("Ni", "Nj", "Nx", "Ny", "latitudeOfFirstGridPointInDegrees",
                 "longitudeOfFirstGridPointInDegrees", "latitudeOfLastGridPointInDegrees",
                 "longitudeOfLastGridPointInDegrees", "iDirectionIncrementInDegrees",
                 "jDirectionIncrementInDegrees", "iScansNegatively", "jScansPositively",
                 "jPointsAreConsecutive", "alternativeRowScanning", "LaDInDegrees",
                 "LoVInDegrees", "latitudeOfSouthernPoleInDegrees", "longitudeOfSouthernPoleInDegrees")
COORDINATE_KEYS = ("dataDate", "dataTime", "endStep", "stepUnits", "number")


def _get(handle, key):
    try:
        return eccodes.codes_get(handle, key)
    except eccodes.CodesInternalError:
        return None


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


@dataclass(frozen=True)
class Message:
    index: int
    offset: int
    size: int
    digest: str
    headers: dict
    geometry: str
    coordinate: tuple


@dataclass(frozen=True)
class GroupSpec:
    identity: str
    filters: dict
    parameter_ids: tuple
    parameters: tuple
    messages: tuple
    geometry: str
    ambiguous: bool = False

    @property
    def label(self):
        keys = self.filters
        return (f"group {self.identity} · dataType={keys.get('dataType', 'unknown')} · "
                f"numberOfPoints={keys.get('numberOfPoints', 'unknown')} · "
                f"{keys.get('typeOfLevel', 'unknown')}={keys.get('level', 'unknown')} · "
                f"stepType={keys.get('stepType', 'unknown')}")


@dataclass
class Discovery:
    groups: list
    messages: list
    complete: bool
    errors: list


def discover_groups(input_path):
    """Read every header without decoding values; never invent filter pairs."""
    path = Path(input_path)
    messages, errors = [], []
    expected_offset = 0
    with path.open("rb") as stream:
        while True:
            handle = None
            try:
                handle = eccodes.codes_grib_new_from_file(stream)
                if handle is None:
                    break
                offset = eccodes.codes_get_message_offset(handle)
                raw = eccodes.codes_get_message(handle)
                if offset != expected_offset:
                    errors.append(f"Ada {offset - expected_offset} byte di luar pesan GRIB sebelum offset {offset}.")
                headers = {key: _get(handle, key) for key in (*BASE_KEYS, *COORDINATE_KEYS, "paramId", "shortName", "startStep")}
                grid_hash = _get(handle, "md5GridSection")
                geometry = grid_hash or canonical({key: _get(handle, key) for key in GEOMETRY_KEYS})
                coordinate = tuple(headers[key] for key in COORDINATE_KEYS)
                messages.append(Message(len(messages), offset, len(raw), sha256(raw).hexdigest(),
                                        headers, geometry, coordinate))
                expected_offset = offset + len(raw)
            except eccodes.CodesInternalError as exc:
                errors.append(f"Pembacaan terhenti pada offset {stream.tell()}: {exc}")
                break
            finally:
                if handle is not None:
                    eccodes.codes_release(handle)
    if expected_offset != path.stat().st_size:
        errors.append(f"Cakupan pesan berakhir pada {expected_offset} dari {path.stat().st_size} byte; discovery tidak lengkap.")
    if not messages:
        errors.append("Tidak ada pesan GRIB yang berhasil ditemukan.")

    primary = defaultdict(list)
    for message in messages:
        key = canonical({**{key: message.headers[key] for key in BASE_KEYS}, "geometry": message.geometry})
        primary[key].append(message)
    groups = []
    for primary_key, candidates in primary.items():
        parameters = defaultdict(list)
        for message in candidates:
            parameters[message.headers["paramId"]].append(message)
        # Variables can share a group only when their coordinate coverage agrees.
        coverage = defaultdict(list)
        for parameter, records in parameters.items():
            coords = sorted((record.coordinate for record in records), key=canonical)
            coverage[canonical(coords)].append(parameter)
        for coordinate_key, parameter_ids in coverage.items():
            owned = tuple(message for message in candidates if message.headers["paramId"] in parameter_ids)
            identity_spec = {"primary": json.loads(primary_key), "parameters": sorted(parameter_ids, key=str),
                             "coordinates": json.loads(coordinate_key)}
            identity = sha256(canonical(identity_spec).encode()).hexdigest()[:12]
            first = owned[0]
            filters = {key: first.headers[key] for key in BASE_KEYS if first.headers[key] is not None}
            if _get_geometry_filter(first):
                filters["md5GridSection"] = first.geometry
            filters["paramId"] = parameter_ids[0] if len(parameter_ids) == 1 else sorted(parameter_ids, key=str)
            duplicates = any(any(count > 1 for count in Counter(record.coordinate for record in parameters[p]).values())
                             for p in parameter_ids)
            names = tuple(dict.fromkeys(message.headers["shortName"] or str(message.headers["paramId"]) for message in owned))
            groups.append(GroupSpec(identity, filters, tuple(parameter_ids), names, owned, first.geometry, duplicates))
    groups.sort(key=lambda group: group.messages[0].index)
    indexes = [message.index for group in groups for message in group.messages]
    if len(indexes) != len(messages) or len(set(indexes)) != len(messages):
        raise AssertionError("GRIB message partition is not disjoint and complete")
    return Discovery(groups, messages, not errors, errors)


def _get_geometry_filter(message):
    # Native md5GridSection is a header key; fallback geometry JSON is not one.
    return not message.geometry.startswith("{")


def select_groups(discovery, data_type=None, number_of_points=None, identities=None):
    groups = [group for group in discovery.groups
              if (data_type is None or group.filters.get("dataType") == data_type)
              and (number_of_points is None or group.filters.get("numberOfPoints") == number_of_points)]
    if identities is not None:
        unknown = set(identities) - {group.identity for group in groups}
        if unknown:
            raise ValueError(f"Group ID tidak tersedia untuk filter ini: {', '.join(sorted(unknown))}")
        groups = [group for group in groups if group.identity in identities]
    return groups


def _safe(value, limit=44):
    value = "unknown" if value is None else str(value)
    return re.sub(r'[^A-Za-z0-9_.-]', "_", value).strip(" .")[:limit] or "unknown"


def group_output_stem(input_path, group):
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", Path(input_path).stem).strip(" .")[:40] or "GRIB"
    if name.split(".")[0].upper() in {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}:
        name = "_" + name
    keys = group.filters
    extra = ""
    if keys.get("typeOfLevel") != "surface" or keys.get("level") != 0:
        extra = f"__typeOfLevel-{_safe(keys.get('typeOfLevel'), 16)}__level-{_safe(keys.get('level'), 8)}"
    if keys.get("stepType") != "instant":
        extra += f"__stepType-{_safe(keys.get('stepType'), 10)}"
    return (f"{name}__dataType-{_safe(keys.get('dataType'), 12)}"
            f"__numberOfPoints-{_safe(keys.get('numberOfPoints'), 12)}{extra}__group-{group.identity}")


def read_group(input_path, group):
    """Spool exact original messages, decode strictly, and normalize scalar time only."""
    if group.ambiguous:
        raise ValueError("Pesan duplikat pada parameter/waktu/step/member yang sama; kelompok ambigu tidak dipilih diam-diam.")
    with TemporaryDirectory(prefix="grib-group-") as directory:
        selected = Path(directory) / "selected.grib"
        with Path(input_path).open("rb") as source, selected.open("wb") as target:
            for message in group.messages:
                source.seek(message.offset)
                raw = source.read(message.size)
                if sha256(raw).hexdigest() != message.digest:
                    raise ValueError("Sumber berubah setelah discovery; periksa kelompok ulang.")
                target.write(raw)
        with cfgrib.open_dataset(str(selected), indexpath="", errors="raise") as dataset:
            if "time" in dataset.coords and dataset.time.ndim == 0:
                dataset = dataset.expand_dims("time")
            frame = dataset_to_dataframe(dataset)
            metadata = dataset_metadata(dataset, frame)
    metadata["group_id"] = group.identity
    metadata["filter_by_keys"] = group.filters.copy()
    metadata["message_count"] = len(group.messages)
    return frame, metadata


@dataclass
class GroupExport:
    group: GroupSpec
    frame: object = None
    metadata: dict = None
    csv_path: Path = None
    xlsx_path: Path = None
    error: str = None


def export_groups(input_path, groups, output_dir):
    results = []
    for group in groups:
        try:
            frame, metadata = read_group(input_path, group)
            csv, xlsx = export_dataframe(frame, Path(output_dir) / group_output_stem(input_path, group))
            results.append(GroupExport(group, frame, metadata, csv, xlsx))
        except Exception as exc:
            results.append(GroupExport(group, error=f"{type(exc).__name__}: {exc}"))
    return results
