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


class AppendLogWriter:
    def __init__(self, path: Path):
        self.path = path

    def write(self, text: str) -> int:
        if not text:
            return 0
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8", errors="replace") as handle:
                handle.write(text)
        except OSError:
            pass
        return len(text)

    def flush(self) -> None:
        pass


def port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except OSError:
        return False


sys.stdout = AppendLogWriter(LOG)
sys.stderr = AppendLogWriter(LOG)

port = int(os.environ.get("WEBGORK_PORT", "7863"))
if port_open("127.0.0.1", port):
    print(f"webgork server already running on 127.0.0.1:{port}", flush=True)
    sys.exit(0)

print("starting webgork server", flush=True)
runpy.run_path(str(ROOT / "app.py"), run_name="__main__")
