import os
import runpy
import socket
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LOG = ROOT / "work" / "server-runner.log"

os.chdir(ROOT)
os.environ["WEBGORK_OPEN_BROWSER"] = "0"
os.environ.setdefault("WEBGORK_PORT", "7863")


def port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except OSError:
        return False


log_file = LOG.open("a", encoding="utf-8", buffering=1)
sys.stdout = log_file
sys.stderr = log_file

port = int(os.environ.get("WEBGORK_PORT", "7863"))
if port_open("127.0.0.1", port):
    print(f"webgork server already running on 127.0.0.1:{port}", flush=True)
    sys.exit(0)

print("starting webgork server", flush=True)
runpy.run_path(str(ROOT / "app.py"), run_name="__main__")
