"""Windows CMD outcomes: real offline installs and explicitly simulated failures.

Run with --wheelhouse data/install-tests/wheelhouse for a complete fresh install.
The wheelhouse is a local QA cache, not part of the repository distribution.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
CMD = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32/cmd.exe"
BASE_PYTHON = Path(sys._base_executable)
WHEELHOUSE: Path | None = None


@unittest.skipUnless(os.name == "nt", "Windows CMD required")
class InstallerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cache = ROOT / "data/install-tests"
        cls.cache.mkdir(parents=True, exist_ok=True)
        cls.owned = tempfile.TemporaryDirectory(prefix="CMD space & (round)! ", dir=cls.cache)
        cls.base = Path(cls.owned.name)
        # Native executable simulates only Python/pip failure branches. Real
        # success/version/prefix tests below use actual Python interpreters.
        source = cls.base / "fake.cs"
        source.write_text('''using System;
using System.IO;
class FakePython {
 static int Main(string[] args) {
  string text = String.Join(" ", args);
  string fail = Environment.GetEnvironmentVariable("GRIB_TEST_FAIL");
  string trace = Environment.GetEnvironmentVariable("GRIB_TEST_TRACE");
  if (trace != null) File.AppendAllText(trace, text + "\\n");
  if (text.Contains("pip install")) { Console.WriteLine("SECRET_MARKER_TOKEN_URL"); if (fail == "packages") return 7; }
  if (text.Contains("pip check") && fail == "check") return 8;
  if (text.Contains("codes_get_api_version") && fail == "imports") return 9;
  if (text.Contains("-m streamlit")) return 17;
  return 0;
 }
}''', encoding="utf-8")
        cls.fake = cls.base / "fake.exe"
        compiler = Path(os.environ["SystemRoot"]) / "Microsoft.NET/Framework64/v4.0.30319/csc.exe"
        subprocess.run([str(compiler), "/nologo", f"/out:{cls.fake}", str(source)], check=True, capture_output=True)

    @classmethod
    def tearDownClass(cls):
        cls.owned.cleanup()

    def fixture(self, label, fake=False):
        directory = self.base / label
        directory.mkdir()
        for name in ("install.cmd", "start-web.cmd", "requirements-web.txt", "requirements.txt"):
            shutil.copy2(ROOT / name, directory / name)
        (directory / "app.py").write_text("# installer fixture\n", encoding="utf-8")
        if fake:
            scripts = directory / ".venv/Scripts"
            scripts.mkdir(parents=True)
            shutil.copy2(self.fake, scripts / "python.exe")
        return directory

    def invoke(self, directory, *, env=None, args="--no-pause", launcher=False):
        settings = os.environ.copy()
        settings.pop("PYTHONHOME", None)
        settings.pop("PYTHONPATH", None)
        settings["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
        if WHEELHOUSE:
            settings.update(PIP_NO_INDEX="1", PIP_FIND_LINKS=str(WHEELHOUSE))
        if env:
            settings.update(env)
        script = directory / ("start-web.cmd" if launcher else "install.cmd")
        command = f'"{CMD}" /d /v:off /s /c ""{script}" {args}"'
        return subprocess.run(command, cwd=self.base, env=settings, stdin=subprocess.DEVNULL,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                              errors="replace", timeout=240)

    def test_01_real_existing_environment(self):
        before = (ROOT / ".venv/pyvenv.cfg").read_bytes()
        result = self.invoke(ROOT)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("ecCodes native:", result.stdout)
        self.assertEqual(before, (ROOT / ".venv/pyvenv.cfg").read_bytes())
        log = (ROOT / "data/install-logs/install.log").read_text()
        self.assertIn("stage=complete status=success exit_code=0", log)

    def test_02_real_fresh_environment_and_rerun_special_path(self):
        if not WHEELHOUSE:
            self.skipTest("provide --wheelhouse for offline fresh dependency installation")
        directory = self.fixture("fresh space & (round)!")
        result = self.invoke(directory)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("Membuat .venv", result.stdout)
        self.assertIn("ecCodes native:", result.stdout)
        config = directory / ".venv/pyvenv.cfg"
        before = (config.read_bytes(), config.stat().st_mtime_ns)
        again = self.invoke(directory)
        self.assertEqual(again.returncode, 0, again.stdout)
        self.assertNotIn("Membuat .venv", again.stdout)
        self.assertEqual(before, (config.read_bytes(), config.stat().st_mtime_ns))

    def test_03_missing_project_python_partial_and_arguments(self):
        project = self.fixture("missing project")
        (project / "requirements-web.txt").unlink()
        result = self.invoke(project)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("File proyek belum lengkap", result.stdout)
        missing = self.fixture("missing python")
        result = self.invoke(missing, env={"PATH": "", "LOCALAPPDATA": str(self.base / "absent")})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("python-3119", result.stdout)
        self.assertFalse((missing / ".venv").exists())
        partial = self.fixture("partial")
        (partial / ".venv").mkdir()
        sentinel = partial / ".venv/keep.txt"
        sentinel.write_text("preserve")
        result = self.invoke(partial)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(sentinel.read_text(), "preserve")
        self.assertNotIn("Memasang paket", result.stdout)
        result = self.invoke(partial, args="--no-pause --unknown")
        self.assertEqual(result.returncode, 2)

    def test_04_real_wrong_version_and_nonvenv_preserved(self):
        bundled = Path(os.environ["USERPROFILE"]) / ".cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe"
        if not bundled.exists():
            self.skipTest("second actual Python version unavailable")
        incompatible = self.fixture("incompatible")
        subprocess.run([str(bundled), "-m", "venv", "--without-pip", str(incompatible / ".venv")], check=True, capture_output=True)
        before = (incompatible / ".venv/pyvenv.cfg").read_bytes()
        result = self.invoke(incompatible)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(before, (incompatible / ".venv/pyvenv.cfg").read_bytes())
        self.assertNotIn("Memasang paket", result.stdout)
        nonvenv = self.fixture("global copied python")
        scripts = nonvenv / ".venv/Scripts"
        scripts.mkdir(parents=True)
        shutil.copy2(BASE_PYTHON, scripts / "python.exe")
        for dll in BASE_PYTHON.parent.glob("*.dll"):
            shutil.copy2(dll, scripts / dll.name)
        sentinel = nonvenv / ".venv/keep.txt"
        sentinel.write_text("global must not receive pip")
        result = self.invoke(nonvenv, env={"PYTHONHOME": str(BASE_PYTHON.parent)})
        self.assertIn("Python 3.11", result.stdout, result.stdout)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("Memasang paket", result.stdout)
        self.assertEqual(sentinel.read_text(), "global must not receive pip")

    def test_05_simulated_pipeline_failures_and_private_log(self):
        for stage, expected in (("packages", 7), ("check", 8), ("imports", 9)):
            with self.subTest(stage=stage):
                directory = self.fixture("failure " + stage, fake=True)
                trace = directory / "trace.txt"
                result = self.invoke(directory, env={"GRIB_TEST_FAIL": stage, "GRIB_TEST_TRACE": str(trace)})
                self.assertEqual(result.returncode, expected, result.stdout)
                log = (directory / "data/install-logs/install.log").read_text()
                self.assertIn(f"status=failure exit_code={expected}", log)
                self.assertNotIn("SECRET_MARKER", log)
                self.assertNotIn(str(directory), log)
                calls = trace.read_text()
                if stage == "packages":
                    self.assertNotIn("pip check", calls)
                if stage != "imports":
                    self.assertNotIn("codes_get_api_version", calls)
                self.assertNotIn("Instalasi selesai", result.stdout)

    def test_06_log_failure_is_optional_and_launcher_exit_preserved(self):
        directory = self.fixture("unwritable log", fake=True)
        (directory / "data").write_text("blocking directory")
        result = self.invoke(directory)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("tidak dapat disimpan", result.stdout)
        launcher = self.invoke(directory, args="", launcher=True)
        self.assertEqual(launcher.returncode, 17, launcher.stdout)
        missing = self.fixture("launcher missing")
        launcher = self.invoke(missing, args="", launcher=True)
        self.assertNotEqual(launcher.returncode, 0)
        self.assertIn("install.cmd", launcher.stdout)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--wheelhouse", type=Path)
    options, rest = parser.parse_known_args()
    WHEELHOUSE = options.wheelhouse.resolve() if options.wheelhouse else None
    unittest.main(argv=[sys.argv[0], *rest])
