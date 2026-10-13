"""Local browser workflow: safe sources, independent batch jobs, and plot data."""

from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
from pathlib import Path
import re
from tempfile import TemporaryDirectory
from zipfile import ZIP_DEFLATED, ZipFile

import numpy as np
import pandas as pd

from grib_to_csv import export_dataframe, output_stem, read_grib
from grib_groups import canonical, discover_groups, group_output_stem, read_group, select_groups

GRIB_EXTENSIONS = {".grib", ".grb", ".grib2", ".grb2"}
RESERVED_NAMES = {"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$",
                  *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}


def safe_label(name):
    """Normalize a display/output name; never use an upload name as a disk path."""
    parts = []
    for part in str(name).replace("\\", "/").split("/"):
        if part in ("", ".", ".."):
            continue
        part = re.sub(r'[<>:"|?*\x00-\x1f]', "_", part).strip(" .")
        if not part:
            continue
        if part.split(".")[0].strip(" .").upper() in RESERVED_NAMES:
            part = "_" + part
        if len(part) > 180:
            component = Path(part)
            part = component.stem[:170] + component.suffix
        parts.append(part)
    if not parts:
        raise ValueError("Nama berkas kosong atau tidak dapat digunakan.")
    label = "/".join(parts)
    if Path(parts[-1]).suffix.lower() not in GRIB_EXTENSIONS:
        raise ValueError("Pilih berkas GRIB: .grib, .grb, .grib2, atau .grb2.")
    return label


@dataclass(frozen=True)
class Source:
    identity: str
    label: str
    fingerprint: str
    size: int
    path: Path | None = None
    payload: bytes | None = None


def local_fingerprint(path):
    stat = path.stat()
    return f"{path.resolve()}:{stat.st_size}:{stat.st_mtime_ns}"


def local_source(path, label=None):
    path = Path(path).resolve()
    if not path.is_file():
        raise ValueError(f"Berkas tidak tersedia: {path.name}")
    label = safe_label(label or path.name)
    identity = sha256(str(path).casefold().encode()).hexdigest()[:16]
    return Source(identity, label, local_fingerprint(path), path.stat().st_size, path=path)


def scan_folder(folder, recursive=False):
    path = Path(str(folder).strip().strip('"')).expanduser()
    if not path.is_dir():
        raise ValueError("Folder tidak ditemukan. Gunakan alamat folder pada komputer aplikasi ini.")
    files = path.rglob("*") if recursive else path.iterdir()
    return [local_source(p, str(p.relative_to(path))) for p in sorted(files)
            if p.is_file() and p.suffix.lower() in GRIB_EXTENSIONS]


def uploaded_sources(uploads):
    sources = []
    occurrences = {}
    for upload in uploads:
        original_name = str(upload.name)
        label = safe_label(original_name)
        payload = upload.getvalue()
        digest = sha256(payload).hexdigest()
        token = original_name + ":" + digest
        occurrence = occurrences.get(token, 0)
        occurrences[token] = occurrence + 1
        identity = sha256(f"{token}:{occurrence}".encode()).hexdigest()[:16]
        sources.append(Source(identity, label, digest, len(payload), payload=payload))
    return sources


def filters_from_inputs(data_type="", points=""):
    data_type, points = data_type.strip(), str(points).strip()
    if data_type and not re.fullmatch(r"[A-Za-z0-9_-]+", data_type):
        raise ValueError("dataType hanya boleh berisi huruf, angka, underscore, atau tanda minus.")
    try:
        number = int(points) if points else None
    except ValueError:
        raise ValueError("numberOfPoints harus berupa bilangan bulat positif.") from None
    if number is not None and number <= 0:
        raise ValueError("numberOfPoints harus berupa bilangan bulat positif.")
    return {"data_type": data_type or None, "number_of_points": number}


def selection_signature(sources, filters, context=""):
    return (context, tuple((s.identity, s.fingerprint) for s in sources),
            tuple(sorted(filters.items())))


def sync_session(state, signature):
    """Discard stale products when a selection, source, mode, or filter changes."""
    if state.get("source_signature") != signature:
        state["source_signature"] = signature
        state["previews"] = []
        state["results"] = []
        state["discoveries"] = []
        return True
    return False


@dataclass
class Outcome:
    source: Source
    frame: pd.DataFrame | None = None
    metadata: dict | None = None
    error: str | None = None
    technical_error: str | None = None
    filters: dict | None = None
    csv_name: str | None = None
    csv_bytes: bytes | None = None
    xlsx_name: str | None = None
    xlsx_bytes: bytes | None = None
    group: object = None

    @property
    def identity(self):
        return f"{self.source.identity}-{self.group.identity}" if self.group else self.source.identity

    @property
    def label(self):
        return f"{self.source.label} · {self.group.label}" if self.group else self.source.label


def _read_source(source, directory, filters):
    if source.path is not None:
        if local_fingerprint(source.path) != source.fingerprint:
            raise ValueError("Berkas berubah sejak dipilih. Tampilkan daftar dan pilih ulang berkas.")
        path = source.path
    else:
        path = directory / f"{source.identity}.grib"
        path.write_bytes(source.payload)
    return read_grib(path, **filters)


def _failure(source, exc):
    if isinstance(exc, FileNotFoundError):
        message = "Berkas sudah tidak tersedia. Pilih ulang sumber data."
    elif "berubah sejak" in str(exc):
        message = str(exc)
    else:
        message = "Berkas belum dapat dibaca. Periksa file GRIB dan filter yang dipilih."
    return Outcome(source, error=message, technical_error=f"{type(exc).__name__}: {exc}")


def preview_batch(sources, filters, progress=None):
    outcomes = []
    with TemporaryDirectory(prefix="grib-preview-") as temporary:
        directory = Path(temporary)
        for source in sources:
            try:
                frame, metadata = _read_source(source, directory, filters)
                result = Outcome(source, frame=frame, metadata=metadata, filters=filters.copy())
            except Exception as exc:
                result = _failure(source, exc)
            outcomes.append(result)
            if progress:
                progress(result)
    return outcomes


def process_batch(sources, filters, previews=(), progress=None):
    """Continue after individual errors, using only app-owned temporary files."""
    cache = {p.source.identity: p for p in previews if p.error is None}
    outcomes = []
    with TemporaryDirectory(prefix="grib-export-") as temporary:
        directory = Path(temporary)
        for source in sources:
            try:
                # Recheck local sources even when their preview is already cached.
                if source.path is not None and local_fingerprint(source.path) != source.fingerprint:
                    raise ValueError("Berkas berubah sejak dipilih. Tampilkan daftar dan pilih ulang berkas.")
                cached = cache.get(source.identity)
                if (cached is not None and cached.source.fingerprint == source.fingerprint
                        and cached.filters == filters):
                    frame, metadata = cached.frame, cached.metadata
                else:
                    frame, metadata = _read_source(source, directory, filters)
                stem = output_stem(Path(source.label).name, **filters)
                csv_path, xlsx_path = export_dataframe(frame, directory / source.identity / stem)
                result = Outcome(source, frame=frame, metadata=metadata, filters=filters.copy(),
                                 csv_name=csv_path.name, csv_bytes=csv_path.read_bytes(),
                                 xlsx_name=xlsx_path.name, xlsx_bytes=xlsx_path.read_bytes())
            except Exception as exc:
                result = _failure(source, exc)
            outcomes.append(result)
            if progress:
                progress(result)
    return outcomes


def results_zip(outcomes):
    buffer = BytesIO()
    with ZipFile(buffer, "w", compression=ZIP_DEFLATED) as archive:
        for result in outcomes:
            if result.error is None and result.csv_bytes is not None:
                folder = result.source.identity
                if result.group:
                    folder += f"/{result.group.identity}"
                archive.writestr(f"{folder}/{result.csv_name}", result.csv_bytes)
                archive.writestr(f"{folder}/{result.xlsx_name}", result.xlsx_bytes)
    return buffer.getvalue()


@dataclass
class SourceDiscovery:
    source: Source
    discovery: object = None
    groups: list = None
    error: str = None


@dataclass(frozen=True)
class GroupChoice:
    source: Source
    group: object

    @property
    def identity(self):
        return f"{self.source.identity}-{self.group.identity}"

    @property
    def label(self):
        return f"{self.source.label} · {self.group.label}"

    @property
    def cache_key(self):
        return (self.source.identity, self.source.fingerprint, self.group.identity,
                canonical(self.group.filters))


def _source_path(source, directory):
    if source.path is not None:
        if local_fingerprint(source.path) != source.fingerprint:
            raise ValueError("Berkas berubah sejak dipilih. Periksa kelompok ulang.")
        return source.path
    path = directory / f"{source.identity}.grib"
    if not path.exists():
        path.write_bytes(source.payload)
    return path


def discover_source_groups(sources, filters):
    reports = []
    with TemporaryDirectory(prefix="grib-discovery-") as temporary:
        for source in sources:
            try:
                discovery = discover_groups(_source_path(source, Path(temporary)))
                groups = select_groups(discovery, **filters)
                reports.append(SourceDiscovery(source, discovery, groups))
            except Exception as exc:
                reports.append(SourceDiscovery(source, error=f"{type(exc).__name__}: {exc}"))
    return reports


def choices_from_discoveries(reports):
    return [GroupChoice(report.source, group) for report in reports if report.groups
            for group in report.groups]


def sync_group_selection(state, choices):
    signature = tuple(choice.cache_key for choice in choices)
    if state.get("group_signature") != signature:
        state["group_signature"] = signature
        state["previews"] = []
        state["results"] = []


def group_batch(choices, export=False, previews=(), progress=None):
    cache = {(p.source.identity, p.source.fingerprint, p.group.identity, canonical(p.group.filters)): p
             for p in previews if p.error is None and p.group is not None}
    outcomes = []
    with TemporaryDirectory(prefix="grib-web-groups-") as temporary:
        directory = Path(temporary)
        for choice in choices:
            source, group = choice.source, choice.group
            try:
                path = _source_path(source, directory)
                cached = cache.get(choice.cache_key)
                if cached is not None:
                    frame, metadata = cached.frame, cached.metadata
                else:
                    frame, metadata = read_group(path, group)
                outcome = Outcome(source, frame=frame, metadata=metadata, group=group)
                if export:
                    stem = directory / source.identity / group.identity / group_output_stem(source.label, group)
                    csv, xlsx = export_dataframe(frame, stem)
                    outcome.csv_name, outcome.xlsx_name = csv.name, xlsx.name
                    outcome.csv_bytes, outcome.xlsx_bytes = csv.read_bytes(), xlsx.read_bytes()
            except Exception as exc:
                outcome = _failure(source, exc)
                outcome.group = group
            outcomes.append(outcome)
            if progress:
                progress(outcome)
    return outcomes


def plot_data(frame, metadata, variable, reference_time=None, row_range=None):
    """Prepare a separate plotting copy; never alter export rows or values."""
    if variable not in metadata["variables"]:
        raise ValueError("Variabel tidak ditemukan.")
    values = frame[variable].copy().reset_index(drop=True)
    if metadata["route"] == "monthly":
        if reference_time is None:
            raise ValueError("Pilih satu waktu referensi untuk grafik monthly.")
        mask = pd.to_datetime(metadata["reference_time"]) == pd.Timestamp(reference_time)
        x = np.asarray(metadata["step_hours"])[mask]
        values = values.loc[mask].reset_index(drop=True)
    else:
        x = pd.to_datetime(metadata["reference_time"])
    data = pd.DataFrame({"x": x, "value": values.to_numpy()})
    if row_range is not None:
        data = data.iloc[row_range[0]:row_range[1] + 1].copy()
    data = data.reset_index(drop=True)
    data["order"] = np.arange(len(data))
    data["segment"] = data["value"].isna().cumsum()
    valid_x = data["x"].dropna()
    scatter = valid_x.duplicated().any() or not valid_x.is_monotonic_increasing
    note = ("Waktu atau step berulang/tidak berurutan: grafik titik dipakai agar tidak membentuk garis menyesatkan."
            if scatter else "Grafik garis membantu melihat tren dan lonjakan; garis terputus pada nilai kosong.")
    return data, "scatter" if scatter else "line", note
