"""Real ecCodes fixtures: partition, automatic routes, CLI, UI, and download parity."""

import argparse
from io import BytesIO
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from zipfile import ZipFile

import pandas as pd
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from grib_groups import discover_groups, export_groups, group_output_stem, read_group, select_groups
from grib_to_csv import convert_grib
from web_workflow import (choices_from_discoveries, discover_source_groups, filters_from_inputs,
                          group_batch, local_source, results_zip, sync_group_selection,
                          uploaded_sources)
from grib_fixtures import message, mixed_fixture
from test_web_workflow import upload, widget, workbook_snapshot

SAMPLE = None


class GroupTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.path = self.directory / "mixed.grib"
        self.count = mixed_fixture(self.path)

    def test_real_partition_routes_geometry_level_coverage_and_member_failure(self):
        with patch("eccodes.codes_get_values", side_effect=AssertionError("Decoded values during header discovery")):
            discovery = discover_groups(self.path)
        self.assertTrue(discovery.complete)
        self.assertEqual(len(discovery.messages), 31)
        self.assertEqual(len(discovery.groups), 8)
        indexes = [message.index for group in discovery.groups for message in group.messages]
        self.assertEqual(sorted(indexes), list(range(self.count)))
        self.assertEqual(len(indexes), len(set(indexes)))
        self.assertEqual({(g.filters["dataType"], g.filters["numberOfPoints"]) for g in discovery.groups},
                         {("fc", 4), ("fc", 6), ("em", 4), ("es", 4)})
        self.assertEqual([g.identity for g in discovery.groups],
                         [g.identity for g in discover_groups(self.path).groups])
        results = export_groups(self.path, discovery.groups, self.directory / "outputs")
        self.assertEqual(sum(result.error is None for result in results), 7)
        self.assertEqual(sum("Unsupported GRIB dimensions" in (result.error or "") for result in results), 1)
        monthly = [result for result in results if result.error is None and result.metadata["route"] == "monthly"]
        self.assertEqual({result.group.filters["dataType"] for result in monthly}, {"fc", "em"})
        em = next(result for result in monthly if result.group.filters["dataType"] == "em")
        self.assertEqual(em.frame["hour"].tolist(), [0, 6, 27, 0, 6, 27])
        self.assertEqual(em.frame.shape, (6, 6))
        singleton = next(result for result in results if result.group.filters["dataType"] == "es" and not result.error)
        self.assertEqual(singleton.frame.shape, (1, 5))
        names = [result.csv_path.name for result in results if not result.error]
        self.assertEqual(len(names), len(set(names)))
        self.assertTrue(all("__dataType-" in name and "__numberOfPoints-" in name and "__group-" in name for name in names))
        self.assertTrue(all(len(name) < 180 for name in names))
        em_only = select_groups(discovery, data_type="em")
        self.assertEqual(len(em_only), 1)
        self.assertEqual(len(select_groups(discovery, number_of_points=6)), 1)
        self.assertEqual(select_groups(discovery, identities=[em_only[0].identity]), em_only)

    def test_duplicates_trailing_junk_truncation_and_actual_user_point_counts(self):
        duplicate = self.directory / "duplicate.grib"
        duplicate.write_bytes(message(value=1) + message(value=2))
        group = discover_groups(duplicate).groups[0]
        self.assertTrue(group.ambiguous)
        with self.assertRaisesRegex(ValueError, "duplikat"):
            read_group(duplicate, group)
        trailing = self.directory / "trailing.grib"
        trailing.write_bytes(self.path.read_bytes() + b"trailing junk")
        self.assertFalse(discover_groups(trailing).complete)
        truncated = self.directory / "truncated.grib"
        truncated.write_bytes(self.path.read_bytes()[:-20])
        self.assertFalse(discover_groups(truncated).complete)
        points = self.directory / "user-points.grib"
        points.write_bytes(message(ni=153, nj=100) + message(ni=85, nj=45))
        found = discover_groups(points)
        self.assertTrue(found.complete)
        self.assertEqual({g.filters["numberOfPoints"] for g in found.groups}, {15300, 3825})
        self.assertTrue(all(read_group(points, group)[0].shape == (1, 5) for group in found.groups))

    def test_batch_cache_subset_change_duplicate_sources_and_zip(self):
        payload = self.path.read_bytes()
        sources = uploaded_sources([upload("a/same.grib", payload), upload("b/same.grib", payload)])
        reports = discover_source_groups(sources, filters_from_inputs())
        choices = choices_from_discoveries(reports)
        self.assertEqual(len(choices), 16)
        subset = [choice for choice in choices if choice.group.filters["dataType"] == "em"]
        preview = group_batch(subset)
        with patch("web_workflow.read_group", side_effect=AssertionError("Unexpected reread")):
            results = group_batch(subset, export=True, previews=preview)
        self.assertTrue(all(result.error is None for result in results))
        with ZipFile(BytesIO(results_zip(results))) as archive:
            self.assertEqual(len(archive.namelist()), 4)
            self.assertEqual(len(set(archive.namelist())), 4)
            self.assertTrue(all(len(Path(name).parts) == 3 for name in archive.namelist()))
        state = {"results": results}
        sync_group_selection(state, subset)
        state["results"] = results
        sync_group_selection(state, subset[:1])
        self.assertEqual(state["results"], [])
        source = local_source(self.path)
        choice = choices_from_discoveries(discover_source_groups([source], filters_from_inputs("em")))[0]
        self.path.write_bytes(payload + b"changed")
        self.assertIsNotNone(group_batch([choice])[0].error)

    def test_cli_default_all_subset_partial_failure_and_legacy_option(self):
        cli = [sys.executable, str(ROOT / "grib_to_csv.py"), str(self.path)]
        result = subprocess.run(cli + ["--output-dir", str(self.directory / "cli")], capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout.count("EXPORTED "), 7)
        self.assertEqual(result.stdout.count("FAILED "), 1)
        self.assertEqual(len(list((self.directory / "cli").glob("*.csv"))), 7)
        em = select_groups(discover_groups(self.path), data_type="em")[0]
        selected = subprocess.run(cli + ["--group", em.identity, "--output-dir", str(self.directory / "subset")], capture_output=True, text=True)
        self.assertEqual(selected.returncode, 0, selected.stderr)
        self.assertEqual(len(list((self.directory / "subset").glob("*.csv"))), 1)
        narrowed = subprocess.run(cli + ["--data-type", "fc", "--number-of-points", "6", "--list-groups"], capture_output=True, text=True)
        self.assertEqual(narrowed.returncode, 0)
        self.assertEqual(narrowed.stdout.count("filter_by_keys="), 1)

    def test_real_sample_group_download_matches_legacy_reference_values(self):
        if SAMPLE is None:
            self.skipTest("Supply --sample for original GRIB parity")
        discovery = discover_groups(SAMPLE)
        self.assertTrue(discovery.complete)
        self.assertEqual(len(discovery.groups), 1)
        group = discovery.groups[0]
        self.assertEqual((group.filters["dataType"], group.filters["numberOfPoints"]), ("an", 1639))
        self.assertEqual(len(group.messages), 6336)
        frame, csv, xlsx = convert_grib(SAMPLE, self.directory / "legacy")
        result = export_groups(SAMPLE, [group], self.directory / "group")[0]
        self.assertIsNone(result.error)
        self.assertEqual(result.frame.shape, (3168, 6))
        pd.testing.assert_frame_equal(frame, result.frame, check_exact=True)
        self.assertEqual(csv.read_bytes(), result.csv_path.read_bytes())
        self.assertEqual(workbook_snapshot(xlsx.read_bytes()), workbook_snapshot(result.xlsx_path.read_bytes()))

    def test_app_default_all_subset_preview_labels_and_partial_results(self):
        app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60).run()
        app.file_uploader[0].set_value(("mixed.grib", self.path.read_bytes(), "application/octet-stream")).run()
        widget(app.button, "Periksa kelompok GRIB").click().run()
        self.assertFalse(app.exception)
        groups = widget(app.multiselect, "Kelompok yang dipilih")
        self.assertEqual(len(groups.value), 8)
        widget(app.button, "Proses berkas terpilih").click().run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.session_state["results"]), 8)
        self.assertEqual(sum(result.error is None for result in app.session_state["results"]), 7)
        self.assertTrue(app.error)
        choices = choices_from_discoveries(app.session_state["discoveries"])
        em_id = next(choice.identity for choice in choices if choice.group.filters["dataType"] == "em")
        widget(app.multiselect, "Kelompok yang dipilih").set_value([em_id]).run()
        self.assertEqual(app.session_state["results"], [])
        widget(app.button, "Lihat cuplikan").click().run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.session_state["previews"]), 1)
        self.assertIn("dataType=em", app.selectbox[0].options[0])
        self.assertIn("numberOfPoints=4", app.selectbox[0].options[0])
        widget(app.checkbox, "Lihat grafik").check().run()
        self.assertFalse(app.exception)
        self.assertTrue(widget(app.selectbox, "Waktu referensi").options)
        widget(app.multiselect, "Kelompok yang dipilih").set_value([]).run()
        self.assertTrue(widget(app.button, "Lihat cuplikan").disabled)
        self.assertTrue(widget(app.button, "Proses berkas terpilih").disabled)
        self.assertEqual(app.session_state["previews"], [])
        widget(app.text_input, "dataType").set_value("em").run()
        self.assertEqual(app.session_state["discoveries"], [])
        app.file_uploader[0].set_value(("new.grib", message("fc"), "application/octet-stream")).run()
        self.assertEqual(app.session_state["discoveries"], [])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample", type=Path)
    args = parser.parse_args()
    SAMPLE = args.sample.resolve() if args.sample else None
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(GroupTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)
