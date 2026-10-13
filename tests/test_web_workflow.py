"""Input, batch parity, chart semantics, and real browser-state regressions."""

import argparse
from copy import copy
from hashlib import sha256
from io import BytesIO
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from zipfile import ZipFile

import cfgrib
import numpy as np
import openpyxl
import pandas as pd
from streamlit.testing.v1 import AppTest
import xarray as xr

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from grib_to_csv import convert_grib, read_grib
from web_workflow import (filters_from_inputs, local_source, plot_data, preview_batch,
                          process_batch, results_zip, safe_label, scan_folder,
                          selection_signature, sync_session, uploaded_sources)

SAMPLE = None
NO_FILTER = filters_from_inputs()


def upload(name, content):
    return SimpleNamespace(name=name, getvalue=lambda: content)


def workbook_snapshot(content):
    workbook = openpyxl.load_workbook(BytesIO(content))
    try:
        return [(sheet.title, [[(cell.value, cell.data_type) for cell in row]
                               for row in sheet.iter_rows()],
                 [[copy(getattr(cell, name)) for name in
                   ("font", "alignment", "border", "fill", "number_format", "protection")]
                  for cell in sheet[1]]) for sheet in workbook]
    finally:
        workbook.close()


def synthetic_read(monthly=False):
    times = np.array(["2024-12-31T21:00", "2025-01-01T03:00"], dtype="datetime64[ns]")
    if monthly:
        values = np.array([1, np.nan, 3, 4, 5, 6], dtype=np.float32).reshape(2, 3, 1, 1)
        dataset = xr.Dataset({"mass": (("time", "step", "latitude", "longitude"), values)},
                             coords={"time": times, "step": np.array([0, 90, 1620], dtype="timedelta64[m]"),
                                     "latitude": [-7.5], "longitude": [111.]})
    else:
        dataset = xr.Dataset({"mass": (("time", "latitude", "longitude"),
                                        np.array([1, 2], dtype=np.float32).reshape(2, 1, 1))},
                             coords={"time": times, "latitude": [-7.5], "longitude": [111.]})
    dataset["mass"].attrs["units"] = "kg m**-3"
    with TemporaryDirectory() as directory:
        placeholder = Path(directory) / "synthetic.grib"
        placeholder.touch()
        with patch.object(cfgrib, "open_dataset", return_value=dataset):
            return read_grib(placeholder)


class WorkflowTests(unittest.TestCase):
    def test_names_extensions_and_unique_outputs(self):
        malicious = ["../../CON.grib", r"C:\other\..\NUL.GRB2", "nested/a/same.grb", "nested/b/same.grb"]
        sources = uploaded_sources([upload(name, b"GRIB") for name in malicious])
        self.assertEqual(len({source.identity for source in sources}), 4)
        for source in sources:
            self.assertNotIn("..", source.label.split("/"))
            self.assertNotIn("\\", source.label)
            self.assertNotIn(":", source.label)
        self.assertTrue(sources[0].label.endswith("_CON.grib"))
        with self.assertRaises(ValueError):
            safe_label("../../")
        with self.assertRaises(ValueError):
            safe_label("fake.csv")
        frame, metadata = synthetic_read()
        with patch("web_workflow.read_grib", return_value=(frame, metadata)):
            outcomes = process_batch(sources, NO_FILTER)
        self.assertTrue(all(result.error is None for result in outcomes))
        with ZipFile(BytesIO(results_zip(outcomes))) as archive:
            names = archive.namelist()
            self.assertEqual(len(names), 8)
            self.assertEqual(len(set(names)), 8)
            self.assertTrue(all(len(Path(name).parts) == 2 for name in names))

    def test_folder_scanning_and_filter_validation(self):
        with TemporaryDirectory() as directory:
            self.assertEqual(scan_folder(f' "{directory}" '), [])
            root = Path(directory)
            (root / "one.GRIB2").touch()
            (root / "other.txt").touch()
            (root / "sub").mkdir()
            (root / "sub" / "two.grb").touch()
            self.assertEqual(len(scan_folder(root)), 1)
            self.assertEqual(len(scan_folder(root, True)), 2)
            with self.assertRaises(ValueError):
                scan_folder(root / "missing")
        for points in ("-1", "0", "1.2", "abc"):
            with self.assertRaises(ValueError):
                filters_from_inputs(points=points)
        with self.assertRaises(ValueError):
            filters_from_inputs("../../fc")

    def test_preview_cache_respects_filters_and_changed_local_files(self):
        frame, metadata = synthetic_read()
        with TemporaryDirectory() as directory:
            path = Path(directory) / "one.grib"
            path.write_bytes(b"first")
            source = local_source(path)
            with patch("web_workflow.read_grib", return_value=(frame, metadata)) as reader:
                previews = preview_batch([source], NO_FILTER)
                process_batch([source], NO_FILTER, previews)
                self.assertEqual(reader.call_count, 1)
                process_batch([source], filters_from_inputs("es"), previews)
                self.assertEqual(reader.call_count, 2)
                self.assertEqual(reader.call_args.kwargs["data_type"], "es")
                path.write_bytes(b"changed content")
                outcome = process_batch([source], NO_FILTER, previews)[0]
                self.assertIn("berubah sejak", outcome.error)
                self.assertEqual(reader.call_count, 2)
            state = {}
            initial = selection_signature([source], NO_FILTER)
            sync_session(state, initial)
            state["results"] = ["stored"]
            self.assertFalse(sync_session(state, initial))
            self.assertTrue(sync_session(state, selection_signature([local_source(path)], NO_FILTER)))
            self.assertEqual(state["results"], [])

    def test_chart_gaps_duplicate_times_and_actual_monthly_steps(self):
        frame, metadata = synthetic_read(True)
        before = frame.copy(deep=True)
        self.assertEqual(metadata["units"]["mass"], "kg m**-3")
        self.assertEqual(frame["hour"].tolist(), [0, 1, 27, 0, 1, 27])
        data, kind, _ = plot_data(frame, metadata, "mass", metadata["time"][0])
        self.assertEqual(data["x"].tolist(), [0., 1.5, 27.])
        self.assertEqual(kind, "line")
        self.assertNotEqual(data["segment"].iloc[0], data["segment"].iloc[2])
        second, _, _ = plot_data(frame, metadata, "mass", metadata["time"][1])
        self.assertEqual(second["value"].tolist(), [4., 5., 6.])
        with self.assertRaises(ValueError):
            plot_data(frame, metadata, "mass")
        pd.testing.assert_frame_equal(before, frame, check_exact=True)
        yearly, meta = synthetic_read()
        for time in (["2025-01-01", "2025-01-01"], ["2025-01-02", "2025-01-01"]):
            meta["reference_time"] = pd.to_datetime(time)
            self.assertEqual(plot_data(yearly, meta, "mass")[1], "scatter")

    def test_real_batch_continues_and_downloads_match_cli(self):
        if SAMPLE is None:
            self.skipTest("Supply --sample for real GRIB batch/CLI parity")
        original_hash = sha256(SAMPLE.read_bytes()).hexdigest()
        payload = SAMPLE.read_bytes()
        sources = uploaded_sources([upload("a/same.grib", payload), upload("broken.grib", b"not a GRIB"),
                                    upload("b/same.grib", payload)])
        outcomes = process_batch(sources, NO_FILTER)
        self.assertEqual([outcome.error is None for outcome in outcomes], [True, False, True])
        with TemporaryDirectory() as directory:
            frame, csv, xlsx = convert_grib(SAMPLE, directory)
            for result in (outcomes[0], outcomes[2]):
                pd.testing.assert_frame_equal(frame, result.frame, check_exact=True)
                self.assertEqual(csv.read_bytes(), result.csv_bytes)
                self.assertEqual(workbook_snapshot(xlsx.read_bytes()), workbook_snapshot(result.xlsx_bytes))
        with ZipFile(BytesIO(results_zip(outcomes))) as archive:
            self.assertEqual(len(archive.namelist()), 4)
            self.assertEqual(len(set(archive.namelist())), 4)
        self.assertEqual(original_hash, sha256(SAMPLE.read_bytes()).hexdigest())
        wrong = process_batch([local_source(SAMPLE)], filters_from_inputs("es"))[0]
        self.assertIsNotNone(wrong.error)


def widget(elements, label):
    return next(element for element in elements if element.label == label)


class AppStateTests(unittest.TestCase):
    def test_upload_preview_processing_graph_and_filter_invalidation(self):
        if SAMPLE is None:
            self.skipTest("Supply --sample for real upload UI")
        app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60).run()
        self.assertFalse(app.exception)
        self.assertTrue(widget(app.button, "Lihat cuplikan").disabled)
        app.file_uploader[0].set_value((SAMPLE.name, SAMPLE.read_bytes(), "application/octet-stream")).run()
        self.assertEqual(app.session_state["previews"], [])
        widget(app.button, "Lihat cuplikan").click().run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.dataframe[0].value), 20)
        with patch("web_workflow.read_grib", side_effect=AssertionError("Unexpected reread")):
            widget(app.button, "Proses berkas terpilih").click().run()
            self.assertFalse(app.exception)
            results = app.session_state["results"]
            self.assertEqual(len(results), 1)
            self.assertIsNone(results[0].error)
            csv = results[0].csv_bytes
            widget(app.checkbox, "Lihat grafik").check().run()
            self.assertFalse(app.exception)
            self.assertEqual(app.session_state["results"][0].csv_bytes, csv)
        widget(app.text_input, "dataType").set_value("es").run()
        self.assertEqual(app.session_state["results"], [])
        self.assertEqual(app.session_state["previews"], [])
        widget(app.button, "Proses berkas terpilih").click().run()
        self.assertFalse(app.exception)
        self.assertTrue(app.error)

    def test_local_folder_selection_and_missing_folder_error(self):
        if SAMPLE is None:
            self.skipTest("Supply --sample for real folder UI")
        app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60).run()
        app.radio[0].set_value("Folder lokal").run()
        widget(app.text_input, "Lokasi folder GRIB").set_value(f'"{SAMPLE.parent}"').run()
        widget(app.button, "Tampilkan berkas").click().run()
        self.assertTrue(app.multiselect[0].value)
        widget(app.button, "Proses berkas terpilih").click().run()
        self.assertFalse(app.exception)
        self.assertTrue(app.success)
        widget(app.text_input, "Lokasi folder GRIB").set_value(str(SAMPLE.parent / "missing-folder")).run()
        widget(app.button, "Tampilkan berkas").click().run()
        self.assertEqual(app.session_state["results"], [])
        self.assertTrue(app.error)

    def test_directory_uploader_and_partial_errors(self):
        frame, metadata = synthetic_read()
        app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60).run()
        app.radio[0].set_value("Unggah folder").run()
        self.assertTrue(app.file_uploader[0].accept_directory)
        app.file_uploader[0].set_value([("folder/a.grb2", b"valid", "application/octet-stream"),
                                        ("folder/b.grib", b"broken", "application/octet-stream")]).run()
        with patch("web_workflow.read_grib", side_effect=[(frame, metadata), ValueError("corrupt")]):
            widget(app.button, "Proses berkas terpilih").click().run()
        self.assertFalse(app.exception)
        self.assertTrue(app.success)
        self.assertTrue(app.error)
        self.assertEqual(sum(result.error is None for result in app.session_state["results"]), 1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample", type=Path)
    options = parser.parse_args()
    SAMPLE = options.sample.resolve() if options.sample else None
    suite = unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromTestCase(WorkflowTests),
                               unittest.defaultTestLoader.loadTestsFromTestCase(AppStateTests)])
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)
