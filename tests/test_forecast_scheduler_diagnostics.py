import importlib.util
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('diagnostics', ROOT / 'scripts/diagnose_county_forecast_validation.py')
diag = importlib.util.module_from_spec(spec)
spec.loader.exec_module(diag)


class SchedulerDiagnosticsTests(unittest.TestCase):
    def test_accounting_has_longer_timeout_and_preserves_partial_evidence(self):
        with patch.object(diag.subprocess, 'run', side_effect=subprocess.TimeoutExpired(['qacct'], 600, output=b'partial accounting')) as run:
            result = diag.capture(['qacct', '-j', '123'])
        self.assertEqual(run.call_args[1]['timeout'], 600)
        self.assertEqual(result['output'], 'partial accounting')
        self.assertIsNone(result['exit_status'])

    def test_live_query_still_bounded(self):
        with patch.object(diag.subprocess, 'run', return_value=subprocess.CompletedProcess(['qstat'], 0, '')) as run:
            diag.capture(['qstat', '-j', '123'])
        self.assertEqual(run.call_args[1]['timeout'], 45)


if __name__ == '__main__':
    unittest.main()
