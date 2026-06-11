import json
import re
import shutil
import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RELEASE_ROOT = ROOT / "release" / "WebGrok-v3-Hermes"
STATIC_VERSION = "20260611-release-hermes-01"


def copy_tree(src, dst):
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))


def copy_file(src, dst):
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def read(path):
    return path.read_text(encoding="utf-8")


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def strip_html_official_quota(html):
    html = re.sub(r'\n\s*<option value="grok_official">.*?</option>', "", html)
    html = re.sub(r'\n\s*<option value="direct">.*?</option>', "", html)
    html = re.sub(
        r'\n\s*<div class="settings-card">\s*<h2>무료 크레딧/쿼터</h2>.*?</div>',
        "",
        html,
        flags=re.S,
    )
    html = re.sub(
        r'\n\s*<div class="settings-card">\s*<h2>직접 OAuth 로그인</h2>.*?</div>',
        "",
        html,
        flags=re.S,
    )
    html = html.replace("20260605-v3-68", STATIC_VERSION)
    return html


def strip_js_official_quota(js):
    js = js.replace("20260605-v3-68", STATIC_VERSION)
    js = js.replace("webgui-shell-v3-68", f"webgui-shell-{STATIC_VERSION}")
    js = re.sub(
        r"const grokOfficialEndpointByBase = \{.*?\};",
        "const grokOfficialEndpointByBase = {};",
        js,
        flags=re.S,
    )
    js = js.replace('  if (imageModel.startsWith("official:")) return "grok_official";\n', "")
    js = js.replace(
        '  return ["hermes_proxy", "grok_official", "direct", "codex_proxy"].includes(value) ? value : "";',
        '  return ["hermes_proxy", "direct", "codex_proxy"].includes(value) ? value : "";',
    )
    js = js.replace('    grok_official: "Grok 공식홈",\n', "")
    js = js.replace('    grok_official: "Grok 공식홈 Quota",\n', "")
    js = re.sub(
        r"const officialVideoModelLabels = \{.*?\};",
        "const officialVideoModelLabels = {};",
        js,
        flags=re.S,
    )
    js = re.sub(
        r"const officialImageModelLabels = \{.*?\};",
        "const officialImageModelLabels = {};",
        js,
        flags=re.S,
    )
    js = re.sub(
        r"function applyOfficialModelCandidates\(models = \{\}\) \{.*?\n\}",
        "function applyOfficialModelCandidates(models = {}) {\n  syncAllRouteModelOptions();\n}",
        js,
        flags=re.S,
    )
    js = re.sub(
        r"async function refreshQuota\(force = false\) \{.*?\n\}",
        "async function refreshQuota(force = false) {\n  renderQuota(null, \"Hermes-only release\");\n}",
        js,
        flags=re.S,
    )
    js = re.sub(
        r"function installGrokOfficialPanel\(\) \{.*?\n\}",
        "function installGrokOfficialPanel() {}",
        js,
        flags=re.S,
    )
    js = re.sub(
        r"function refreshGrokOfficialPanel\(\) \{.*?\n\}",
        "function refreshGrokOfficialPanel() {}",
        js,
        flags=re.S,
    )
    js = js.replace("/api/grok-official", "/disabled-home-quota")
    js = js.replace("grok_official", "home_quota_disabled")
    js = js.replace("grokOfficial", "homeQuotaDisabled")
    js = js.replace("Grok Official", "Homepage quota disabled")
    js = js.replace("Grok 공식홈", "공홈 쿼타 제거됨")
    js = js.replace("official:imagine", "disabled-home-image")
    return js


def strip_app_official_quota(py):
    py = remove_official_python_defs(py)
    py = py.replace(
        '    "grok_official_image_candidates": unique_model_ids(GROK_OFFICIAL_IMAGE_MODEL_CANDIDATES),\n'
        '        "grok_official_video_candidates": unique_model_ids(GROK_OFFICIAL_VIDEO_MODEL_CANDIDATES),\n',
        '        "grok_official_image_candidates": [],\n'
        '        "grok_official_video_candidates": [],\n',
    )
    py = py.replace('"grok_official", ', "")
    py = py.replace(', "grok_official"', "")
    py = py.replace('or provider == "grok_official"\n        ', "")
    py = py.replace('or (cfg["provider"] == "grok_official" and grok_official.get("chrome_running") and grok_official.get("session_cookie"))\n            ', "")
    py = py.replace('grok_official = grok_official_status_payload(check_cookie=cfg["provider"] == "grok_official")', 'grok_official = {"configured": False, "chrome_running": False, "session_cookie": False, "message": "Hermes-only release"}')
    py = py.replace('and cfg["provider"] == "grok_official"\n        ', "")
    py = py.replace('and grok_official.get("session_cookie")\n        ', "")

    guard = '''

def _disable_grok_official_release_routes():
    blocked = []
    for rule in list(app.url_map.iter_rules()):
        if rule.rule.startswith("/api/grok-official") or rule.rule == "/api/oauth/quota":
            blocked.append(rule)
    for rule in blocked:
        try:
            app.url_map._rules.remove(rule)
            rules = app.url_map._rules_by_endpoint.get(rule.endpoint, [])
            if rule in rules:
                rules.remove(rule)
            app.view_functions.pop(rule.endpoint, None)
        except Exception:
            pass


_disable_grok_official_release_routes()
'''
    marker = '\nif __name__ == "__main__":'
    if marker in py:
        py = py.replace(marker, guard + marker)
    else:
        py += guard
    py = py.replace("GROK_OFFICIAL", "HOME_QUOTA_DISABLED")
    py = py.replace("grok_official", "home_quota_disabled")
    py = py.replace("grok-official", "home-quota-disabled")
    py = py.replace("grok.com/rest/media", "disabled.home/rest/media")
    py = py.replace("grok.com/rest/app-chat", "disabled.home/rest/app-chat")
    py = py.replace("grok.com/ws/imagine", "disabled.home/ws/imagine")
    py = py.replace("official:imagine", "disabled-home-image")
    py = py.replace("xai-oauth-token.json", "release-disabled-token.json")
    py = py.replace("webgork-oauth-token.json", "release-disabled-web-token.json")
    py = py.replace("Grok 공식홈 Quota", "공홈 쿼타 제거됨")
    py = py.replace("Grok 공식홈", "공홈 쿼타 제거됨")
    return py


def remove_official_python_defs(py):
    tree = ast.parse(py)
    line_ranges = []
    remove_names = {
        "CdpWebSocket",
        "MinimalWebSocket",
        "ensure_grok_chrome",
        "chrome_process_count",
        "stop_chrome_processes",
        "chrome_executable_candidates",
        "chrome_executable_path",
        "grok_default_chrome_user_data_dir",
        "grok_default_chrome_profile_name",
        "grok_oauth_quota",
        "oauth_quota",
        "compose_official_connected_result",
    }
    for node in tree.body:
        name = getattr(node, "name", "")
        decorators = " ".join(ast.unparse(item) for item in getattr(node, "decorator_list", []))
        text = f"{name} {decorators}".lower()
        should_remove = (
            name in remove_names
            or "grok" in name.lower()
            or "grok_official" in text
            or "grok-official" in text
            or "grok_chrome" in text
            or decorators.startswith("app.get('/api/oauth/quota")
        )
        if should_remove and hasattr(node, "lineno") and hasattr(node, "end_lineno"):
            start = min([node.lineno, *[item.lineno for item in getattr(node, "decorator_list", [])]])
            line_ranges.append((start, node.end_lineno))
    lines = py.splitlines()
    removed = set()
    for start, end in line_ranges:
        removed.update(range(start, end + 1))
    kept = [line for index, line in enumerate(lines, start=1) if index not in removed]
    py = "\n".join(kept) + "\n"
    py = re.sub(r"GROK_OFFICIAL_IMAGE_MODEL_CANDIDATES = \[.*?\]\n", "GROK_OFFICIAL_IMAGE_MODEL_CANDIDATES = []\n", py, flags=re.S)
    py = re.sub(r"GROK_OFFICIAL_VIDEO_MODEL_CANDIDATES = \[.*?\]\n", "GROK_OFFICIAL_VIDEO_MODEL_CANDIDATES = []\n", py, flags=re.S)
    py = re.sub(r"GROK_OFFICIAL_IMAGE_MODEL_NAMES = \{.*?\}\n", "GROK_OFFICIAL_IMAGE_MODEL_NAMES = {}\n", py, flags=re.S)
    py = re.sub(r"GROK_OFFICIAL_PRO_MODELS = \{.*?\}\n", "GROK_OFFICIAL_PRO_MODELS = set()\n", py, flags=re.S)
    py = re.sub(r"GROK_OFFICIAL_PROGRESS = \{.*?\}\n", "GROK_OFFICIAL_PROGRESS = {}\n", py, flags=re.S)
    py = py.replace("GROK_OFFICIAL_PROGRESS_LOCK = Lock()\n", "")
    py = re.sub(
        r"\n\s*if grok_official_image_model_is_experimental\(requested\).*?raise ValueError\(.*?\)\n",
        "\n",
        py,
        flags=re.S,
    )
    return py


def write_runner():
    text = f'''@echo off
setlocal
cd /d "%~dp0"

set "PYTHON_CMD="
if exist "%LocalAppData%\\Python\\pythoncore-3.14-64\\python.exe" set "PYTHON_CMD=%LocalAppData%\\Python\\pythoncore-3.14-64\\python.exe"
if not defined PYTHON_CMD (
  where py >nul 2>nul
  if not errorlevel 1 set "PYTHON_CMD=py -3"
)
if not defined PYTHON_CMD (
  where python >nul 2>nul
  if not errorlevel 1 set "PYTHON_CMD=python"
)
if not defined PYTHON_CMD (
  echo Python was not found. Install Python 3.11+ and run this file again.
  pause
  exit /b 1
)

%PYTHON_CMD% -c "import flask, requests, dotenv, imageio_ffmpeg, PIL" >nul 2>nul
if not %errorlevel%==0 (
  echo Installing required Python packages...
  %PYTHON_CMD% -m pip install -r requirements.txt
  if not %errorlevel%==0 (
    echo Failed to install requirements.
    pause
    exit /b 1
  )
)

if not exist work mkdir work
powershell -NoProfile -Command "try {{ Invoke-WebRequest -UseBasicParsing http://127.0.0.1:7863/health -TimeoutSec 3 | Out-Null; exit 0 }} catch {{ exit 1 }}" >nul 2>nul
if not %errorlevel%==0 (
  echo Starting WebGrok Hermes-only server...
  start "WebGrok Hermes Server" /min cmd /c "set WEBGORK_OPEN_BROWSER=0&& set WEBGORK_PORT=7863&& %PYTHON_CMD% work\\run_server.py"
  powershell -NoProfile -Command "$ok=$false; for($i=0; $i -lt 60; $i++){{ try {{ Invoke-WebRequest -UseBasicParsing http://127.0.0.1:7863/health -TimeoutSec 3 | Out-Null; $ok=$true; break }} catch {{ Start-Sleep -Milliseconds 500 }} }}; if($ok){{ exit 0 }} else {{ exit 1 }}"
  if not %errorlevel%==0 (
    echo Server did not start. Check work\\server-runner.log
    pause
    exit /b 1
  )
)

start "" http://127.0.0.1:7863/?v={STATIC_VERSION}
endlocal
'''
    write(RELEASE_ROOT / "RUN_WEBGROK_HERMES_ONLY.bat", text)


def write_release_notes():
    text = f"""# WebGrok v3 Hermes-only Release

This release folder is a privacy-clean, one-click runnable package.

Included:
- Hermes Proxy based image generation, image editing, image-to-video, queue, templates, library, and local media tools.
- `RUN_WEBGROK_HERMES_ONLY.bat` one-click launcher.

Excluded:
- Homepage quota UI and related web-session routes.
- Homepage Chrome profile, cookie, CDP, and browser-session launch data.
- `.webgork-private`, `.chrome-*`, `media-library`, `backups`, local logs, git metadata, and local settings from the development workspace.

First run:
1. Start your Hermes proxy separately if it is not already running.
2. Run `RUN_WEBGROK_HERMES_ONLY.bat`.
3. Open Settings and adjust `Hermes Proxy Base URL` if needed.

Build stamp: {STATIC_VERSION}
"""
    write(RELEASE_ROOT / "README_RELEASE.md", text)


def write_clean_settings():
    settings = {
        "provider": "hermes_proxy",
        "hermes_base_url": "http://127.0.0.1:8645/v1",
        "codex_proxy_base_url": "http://127.0.0.1:3333",
    }
    write(RELEASE_ROOT / "webgork-settings.json", json.dumps(settings, ensure_ascii=False, indent=2))


def main():
    if RELEASE_ROOT.exists():
        shutil.rmtree(RELEASE_ROOT)
    RELEASE_ROOT.mkdir(parents=True)

    for filename in ("app.py", "requirements.txt"):
        copy_file(ROOT / filename, RELEASE_ROOT / filename)
    copy_tree(ROOT / "templates", RELEASE_ROOT / "templates")
    copy_tree(ROOT / "static", RELEASE_ROOT / "static")
    copy_file(ROOT / "work" / "run_server.py", RELEASE_ROOT / "work" / "run_server.py")

    write(RELEASE_ROOT / "app.py", strip_app_official_quota(read(RELEASE_ROOT / "app.py")))
    write(RELEASE_ROOT / "templates" / "index.html", strip_html_official_quota(read(RELEASE_ROOT / "templates" / "index.html")))
    write(RELEASE_ROOT / "static" / "app.js", strip_js_official_quota(read(RELEASE_ROOT / "static" / "app.js")))
    write(
        RELEASE_ROOT / "static" / "service-worker.js",
        read(RELEASE_ROOT / "static" / "service-worker.js")
        .replace("20260605-v3-68", STATIC_VERSION)
        .replace("webgui-shell-v3-68", f"webgui-shell-{STATIC_VERSION}"),
    )
    write_clean_settings()
    write_runner()
    write_release_notes()
    print(RELEASE_ROOT)


if __name__ == "__main__":
    main()
