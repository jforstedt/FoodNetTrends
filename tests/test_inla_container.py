#!/usr/bin/env python3
"""Test safe container publication without invoking a real container runtime."""
import os
import shutil
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parent.parent
BUILDER = ROOT / "scripts/build_inla_container.sh"


class ContainerBuilderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="inla build test ")
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.builder = BUILDER
        self.runtime = self.directory / "fake runtime"
        self.runtime.write_text('''#!/usr/bin/env bash
set -eu
case "$1" in
    --version) echo fixture-runtime ;;
    build)
        shift
        if [[ "$1" == --fakeroot ]]; then shift; fi
        if [[ -n "${EXPECTED_DEFINITION:-}" ]]; then [[ "$2" == "$EXPECTED_DEFINITION" ]]; fi
        printf 'fixture image' > "$1"
        exit "${FAKE_BUILD_STATUS:-0}" ;;
    test)
        [[ "$2" == --cleanenv ]]
        [[ -f "$3" ]]
        exit "${FAKE_TEST_STATUS:-0}" ;;
    *) exit 2 ;;
esac
''')
        self.runtime.chmod(0o755)
        self.env = dict(os.environ, INLA_CONTAINER_RUNTIME=str(self.runtime))

    def run_builder(self, output, *args):
        return subprocess.run(
            ["bash", str(self.builder), str(output)] + list(args), env=self.env,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)

    def assert_cleaned(self):
        self.assertEqual(list(self.directory.glob(".foodnet-inla-build.*")), [])

    def test_success_with_quoted_paths(self):
        output = self.directory / "test ' image $(touch unexpected).sif"
        result = self.run_builder(output, "--fakeroot")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(output.read_text(), "fixture image")
        self.assertIn("INLA CONTAINER COMPLETE:", result.stdout)
        self.assertEqual(len(list(self.directory.glob("foodnet-inla-build.*.log"))), 1)
        self.assert_cleaned()

    def test_failed_build_does_not_publish(self):
        self.env["FAKE_BUILD_STATUS"] = "7"
        output = self.directory / "failed-build.sif"
        result = self.run_builder(output)
        self.assertEqual(result.returncode, 7)
        self.assertFalse(output.exists())
        self.assert_cleaned()

    def test_failed_finished_image_test_does_not_publish(self):
        self.env["FAKE_TEST_STATUS"] = "9"
        output = self.directory / "failed-test.sif"
        result = self.run_builder(output)
        self.assertEqual(result.returncode, 9)
        self.assertFalse(output.exists())
        self.assert_cleaned()

    def test_existing_image_unchanged(self):
        output = self.directory / "existing.sif"
        output.write_text("previous image")
        result = self.run_builder(output)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(output.read_text(), "previous image")

    def test_production_name_refused(self):
        output = self.directory / "foodnet.sif"
        result = self.run_builder(output)
        self.assertEqual(result.returncode, 2)
        self.assertFalse(output.exists())

    def test_repair_reuses_existing_image_and_preserves_it(self):
        fixture = self.directory / "checkout"
        (fixture / "scripts").mkdir(parents=True)
        self.builder = fixture / "scripts/build_inla_container.sh"
        shutil.copyfile(str(BUILDER), str(self.builder))
        base = fixture / "foodnet-inla.sif"
        output = self.directory / "fixed.sif"
        missing = self.run_builder(output, "--repair-permissions")
        self.assertEqual(missing.returncode, 2)
        self.assertFalse(output.exists())
        base.write_text("original INLA image")
        self.env["EXPECTED_DEFINITION"] = "containers/foodnet-inla-permissions.def"
        result = self.run_builder(output, "--repair-permissions")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(base.read_text(), "original INLA image")
        self.assertEqual(output.read_text(), "fixture image")
        recipe = (ROOT / "containers/foodnet-inla-permissions.def").read_text()
        self.assertIn("Bootstrap: localimage\nFrom: foodnet-inla.sif", recipe)
        self.assertIn("chmod -R a+rX /usr/local/lib/R/site-library/INLA", recipe)
        self.assertNotIn("install.packages", recipe)
        self.assertNotIn("apt-get", recipe)

    def test_definition_smoke_uses_empty_report_directory(self):
        definition = (ROOT / "containers/foodnet-inla.def").read_text()
        section = definition.split("%test\n", 1)[1].split("\n%", 1)[0]
        fake_bin = self.directory / "bin"
        fake_bin.mkdir()
        rscript = fake_bin / "Rscript"
        rscript.write_text('''#!/usr/bin/env bash
set -eu
[[ "$1" == --vanilla ]]
[[ "$2" == /opt/foodnet-inla/inla_smoke.R ]]
[[ -d "$3" && "$4" == 2 ]]
[[ -z $(ls -A -- "$3") ]]
printf '%s' "$3" > "$FIXTURE_REPORT_PATH"
echo PASS > "$3/status.txt"
''')
        rscript.chmod(0o755)
        record = self.directory / "report path"
        env = dict(self.env, PATH=str(fake_bin) + os.pathsep + os.environ["PATH"],
                   FIXTURE_REPORT_PATH=str(record))
        result = subprocess.run(["bash", "-c", section], env=env,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                universal_newlines=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(Path(record.read_text()).exists())
        self.assertIn("export R_LIBS_USER=/opt/foodnet-inla/no-user-library", definition)
        # R normalizes the installed version to 26.8.7; string equality fails.
        self.assertIn('packageVersion("INLA") == package_version("26.08.07")', definition)
        self.assertNotIn('as.character(packageVersion("INLA")) == "26.08.07"', definition)


if __name__ == "__main__":
    unittest.main()
