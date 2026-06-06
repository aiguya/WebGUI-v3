import os
import runpy
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LOG = ROOT / "work" / "server-runner.log"

os.chdir(ROOT)
os.environ["WEBGORK_OPEN_BROWSER"] = "0"
os.environ.setdefault("WEBGORK_PORT", "7863")

log_file = LOG.open("a", encoding="utf-8", buffering=1)
sys.stdout = log_file
sys.stderr = log_file

print("starting webgork server", flush=True)
runpy.run_path(str(ROOT / "app.py"), run_name="__main__")
