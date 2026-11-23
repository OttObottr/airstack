import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class LaunchTest(unittest.TestCase):
    def test_started_from_a_hostile_folder_it_still_runs_this_server(self):
        with tempfile.TemporaryDirectory() as tmp:
            for bad in ("airstack/__init__.py", "json.py"):
                path = Path(tmp) / bad
                path.parent.mkdir(exist_ok=True)
                path.write_text("open('ran-here', 'w').close()\nraise SystemExit(9)\n")
            run = subprocess.run([sys.executable, str(ROOT / "server.py")], cwd=tmp, input='{"jsonrpc":"2.0","id":1,"method":"ping"}\n', capture_output=True, text=True, timeout=20)
            self.assertFalse((Path(tmp) / "ran-here").exists(), run.stderr)
            self.assertIn('"id": 1', run.stdout.replace('"id":1', '"id": 1'))


if __name__ == "__main__":
    unittest.main()
