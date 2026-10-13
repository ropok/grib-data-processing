"""Small real ECMWF GRIB1 messages generated and read back with ecCodes."""

from pathlib import Path

import eccodes as e
import numpy as np


def message(kind="fc", date=20240101, step=0, parameter=130, ni=2, nj=2, longitude=0,
            level=0, member=0, value=1):
    handle = e.codes_grib_new_from_samples("regular_ll_sfc_grib1")
    try:
        # ECMWF local definition 1 contains the actual MARS fc/em/es type keys.
        e.codes_set(handle, "localDefinitionNumber", 1)
        e.codes_set(handle, "dataType", kind)
        e.codes_set(handle, "Ni", ni)
        e.codes_set(handle, "Nj", nj)
        latitude_step = 0.5 if nj > 90 else 1
        e.codes_set(handle, "latitudeOfFirstGridPointInDegrees", (nj - 1) * latitude_step)
        e.codes_set(handle, "latitudeOfLastGridPointInDegrees", 0)
        e.codes_set(handle, "longitudeOfFirstGridPointInDegrees", longitude)
        e.codes_set(handle, "longitudeOfLastGridPointInDegrees", longitude + ni - 1)
        e.codes_set(handle, "iDirectionIncrementInDegrees", 1)
        e.codes_set(handle, "jDirectionIncrementInDegrees", latitude_step)
        e.codes_set(handle, "dataDate", date)
        e.codes_set(handle, "dataTime", 0)
        e.codes_set(handle, "step", step)
        e.codes_set(handle, "paramId", parameter)
        if level:
            e.codes_set(handle, "typeOfLevel", "heightAboveGround")
            e.codes_set(handle, "level", level)
        e.codes_set(handle, "number", member)
        e.codes_set_values(handle, np.full(ni * nj, value, dtype=float))
        raw = e.codes_get_message(handle)
        check = e.codes_new_from_message(raw)
        try:
            assert e.codes_get(check, "dataType") == kind
            assert e.codes_get(check, "numberOfPoints") == ni * nj
        finally:
            e.codes_release(check)
        return raw
    finally:
        e.codes_release(handle)


def mixed_fixture(path):
    records = []
    for date in (20240101, 20240102):
        for parameter in (130, 131, 133):
            records.append(message(date=date, parameter=parameter, value=parameter))
        records.append(message(date=date, ni=3))
        for step in (0, 6):
            records.append(message(date=date, step=step, parameter=132))
    for date in (20240101, 20240201):
        for step in (0, 6, 27):
            for parameter in (130, 131):
                records.append(message("em", date, step, parameter))
    records.append(message("es", 20240301, 12))
    records.append(message(longitude=10, date=20240401))
    records.append(message(level=2, date=20240401))
    for date in (20240501, 20240502):
        for member in (0, 1):
            records.append(message("es", date, parameter=131, member=member))
    Path(path).write_bytes(b"".join(records))
    return len(records)
