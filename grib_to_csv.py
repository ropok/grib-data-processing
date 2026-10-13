"""Export the last GRIB grid point using GribToCsv.ipynb's table semantics."""

import argparse
from pathlib import Path

import cfgrib
import numpy as np
import pandas as pd
from openpyxl.styles import Alignment, Border, Font, PatternFill, Protection, Side


YEARLY_DIMS = ("time", "latitude", "longitude")
MONTHLY_DIMS = ("time", "step", "latitude", "longitude")


def dataset_to_dataframe(dataset):
    """Preserve notebook variable order, time order, dtype promotion, and NaNs.

    Yearly exports use the reference timestamp's hour. Monthly exports use
    forecast step hours with the reference date, even for steps beyond 24 hours.
    """
    variables = list(dataset.data_vars)
    if not variables:
        raise ValueError("No GRIB variables found; check the selected filters.")
    dimensions = {tuple(dataset[name].dims) for name in variables}
    if dimensions not in ({YEARLY_DIMS}, {MONTHLY_DIMS}):
        details = ", ".join(f"{name}: {dataset[name].dims}" for name in variables)
        raise ValueError(
            "Unsupported GRIB dimensions. Expected all variables to have "
            "(time, latitude, longitude) or (time, step, latitude, longitude). "
            f"Found {details}."
        )
    for coordinate in next(iter(dimensions)):
        if dataset.sizes[coordinate] == 0:
            raise ValueError(f"GRIB coordinate {coordinate!r} is empty.")

    monthly = dimensions == {MONTHLY_DIMS}
    values = []
    for name in variables:
        # The notebook selects the final coordinate, not a spatial average.
        data = dataset[name].values
        if monthly:
            values.append([data[t][s][-1][-1]
                           for t in range(len(dataset.time))
                           for s in range(len(dataset.step))])
        else:
            values.append([data[t][-1][-1] for t in range(len(data))])
    # Building variables as rows before transposing preserves notebook promotion.
    data_frame = pd.DataFrame(values).T
    data_frame.columns = variables
    dates = pd.DatetimeIndex(dataset["time"].values)
    if monthly:
        steps = dataset["step"].values.astype("timedelta64[h]")
        step_hours = [step.astype("timedelta64[h]").astype(int) for step in steps]
        time_values = [[], [], [], []]
        for date in dates:
            for hour in step_hours:
                for column, value in zip(time_values,
                                         (date.year, date.month, date.day, hour)):
                    column.append(value)
    else:
        time_values = [dates.year.tolist(), dates.month.tolist(),
                       dates.day.tolist(), dates.hour.tolist()]
    time_frame = pd.DataFrame(time_values).T
    time_frame.columns = ["year", "month", "day", "hour"]
    return pd.concat([time_frame, data_frame], axis=1)


def output_stem(input_path, data_type=None, number_of_points=None):
    stem = Path(input_path).stem
    if data_type is not None:
        stem += f"_{data_type}"
    if number_of_points is not None:
        stem += f"_{number_of_points}"
    return stem


def read_grib(input_path, data_type=None, number_of_points=None):
    """Read the notebook table and original coordinates without writing files."""
    input_path = Path(input_path)
    if not input_path.is_file():
        raise FileNotFoundError(f"GRIB input file does not exist: {input_path}")
    filters = {}
    if data_type is not None:
        filters["dataType"] = data_type
    if number_of_points is not None:
        filters["numberOfPoints"] = number_of_points
    # Avoid cfgrib index sidecars and stale indexes when filters change.
    with cfgrib.open_dataset(str(input_path), filter_by_keys=filters, indexpath="") as dataset:
        frame = dataset_to_dataframe(dataset)
        monthly = tuple(dataset[next(iter(dataset.data_vars))].dims) == MONTHLY_DIMS
        times = dataset.time.values.copy()
        steps = dataset.step.values.copy() if monthly else None
        metadata = {
            "dimensions": dict(dataset.sizes),
            "variables": list(dataset.data_vars),
            "units": {name: dataset[name].attrs.get("units") for name in dataset.data_vars},
            "latitude": float(dataset.latitude.values[-1]),
            "longitude": float(dataset.longitude.values[-1]),
            "route": "monthly" if monthly else "yearly",
            "time": times, "step": steps,
            "reference_time": np.repeat(times, len(steps)) if monthly else times.copy(),
            "step_hours": np.tile(steps / np.timedelta64(1, "h"), len(times)) if monthly else None,
            "row_count": len(frame),
            "missing": {name: int(frame[name].isna().sum()) for name in dataset.data_vars},
        }
    return frame, metadata


def export_dataframe(frame, stem):
    """Write both formats with the same LF and complete reference header style."""
    stem = Path(stem)
    stem.parent.mkdir(parents=True, exist_ok=True)
    csv_path, xlsx_path = Path(f"{stem}.csv"), Path(f"{stem}.xlsx")
    # Use the Colab reference's LF newlines on every operating system.
    frame.to_csv(csv_path, index=False, lineterminator="\n")
    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
        frame.to_excel(writer, index=False)
        # Match the supplied reference's complete header style. Font name and
        # size are intentionally unset; Excel inherits them from the workbook.
        for cell in writer.sheets["Sheet1"][1]:
            cell.font = Font(bold=True)
            cell.alignment = Alignment(horizontal="center", vertical="top")
            cell.border = Border(left=Side(style="thin"), right=Side(style="thin"),
                                 top=Side(style="thin"), bottom=Side(style="thin"))
            cell.fill = PatternFill()
            cell.number_format = "General"
            cell.protection = Protection(locked=True, hidden=False)
    return csv_path, xlsx_path


def convert_grib(input_path, output_dir=None, data_type=None, number_of_points=None):
    """Convert one GRIB file; return its DataFrame and the two exported paths."""
    input_path = Path(input_path)
    frame, _ = read_grib(input_path, data_type, number_of_points)
    directory = (Path(output_dir) if output_dir is not None
                 else input_path.parent / f"output_{input_path.stem}")
    stem = directory / output_stem(input_path, data_type, number_of_points)
    csv_path, xlsx_path = export_dataframe(frame, stem)
    return frame, csv_path, xlsx_path


def positive_integer(value):
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("number of points must be positive")
    return number


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Path to one .grib file")
    parser.add_argument("--output-dir", type=Path, help="Output folder (default: beside input)")
    parser.add_argument("--data-type", help="GRIB dataType filter, e.g. fc, em, es")
    parser.add_argument("--number-of-points", type=positive_integer,
                        help="GRIB numberOfPoints filter")
    args = parser.parse_args(argv)
    try:
        frame, csv_path, xlsx_path = convert_grib(
            args.input, args.output_dir, args.data_type, args.number_of_points)
    except (OSError, ValueError) as exc:
        parser.exit(1, f"Conversion failed: {exc}\n")
    print(f"Exported {len(frame)} rows; columns: {', '.join(frame.columns)}")
    print(f"CSV: {csv_path.resolve()}")
    print(f"XLSX: {xlsx_path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
