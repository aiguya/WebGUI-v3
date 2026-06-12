import json
import re
import shutil
import ast
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RELEASE_ROOT = ROOT / "release" / "WebGrok-v3-Hermes"
RELEASE_SEED_ROOT = ROOT / "release_seed" / "library"
STATIC_VERSION = "20260613-release-hermes-14"
SOURCE_STATIC_VERSIONS = [
    "20260605-v3-68",
    "20260612-v3-69",
    "20260612-v3-70",
]
SOURCE_SHELL_CACHE_NAMES = [
    "webgui-shell-v3-68",
    "webgui-shell-v3-69",
    "webgui-shell-v3-70",
]


def apply_release_static_version(text):
    for version in SOURCE_STATIC_VERSIONS:
        text = text.replace(version, STATIC_VERSION)
    for cache_name in SOURCE_SHELL_CACHE_NAMES:
        text = text.replace(cache_name, f"webgui-shell-{STATIC_VERSION}")
    return text


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
        r'\n\s*<div class="settings-card">\s*<h2>무료 크레딧·토큰</h2>.*?</div>',
        "",
        html,
        flags=re.S,
    )
    html = re.sub(
        r'\n\s*<div class="settings-card">\s*<h2>직접 OAuth 로그인</h2>[\s\S]*?</form>\s*</div>',
        "",
        html,
    )
    html = re.sub(
        r'\n\s*<div class="quota-pill is-empty" id="quotaPill"[\s\S]*?</div>',
        "",
        html,
        count=1,
    )
    connection_card = '''
        <div class="settings-card connection-card" id="connectionStatusPanel">
          <h2>연결 상태</h2>
          <div class="connection-list">
            <div class="connection-row is-disconnected" data-connection-service="hermes">
              <span class="connection-icon" aria-hidden="true"></span>
              <div class="connection-main">
                <strong>Hermes xAI</strong>
                <small id="hermesAuthStatus">상태 확인 전</small>
              </div>
              <span class="connection-state" data-connection-label>연결안됨</span>
              <div class="connection-actions">
                <button type="button" id="startHermesAuth" class="secondary">인증</button>
                <button type="button" id="startHermesProxy" class="secondary">Proxy</button>
                <button type="button" id="resetHermesAuth" class="secondary">리셋</button>
                <button type="button" id="logoutHermesAuth" class="secondary danger-btn">로그아웃</button>
              </div>
            </div>
            <div id="hermesAuthBox" class="auth-code-box compact-auth" hidden>
              <a id="hermesAuthUrl" class="button-link login-wide secondary" href="#" target="_blank" rel="noreferrer">xAI 인증 페이지 열기</a>
              <label>인증 코드</label>
              <input type="text" id="hermesAuthCode" autocomplete="off" placeholder="xAI 화면의 코드를 붙여넣기">
              <button type="button" id="submitHermesCode">코드로 로그인 완료</button>
            </div>
            <div class="connection-row is-disconnected" data-connection-service="codex">
              <span class="connection-icon" aria-hidden="true"></span>
              <div class="connection-main">
                <strong>Codex / ChatGPT</strong>
                <small id="codexProxyStatusText">상태 확인 전</small>
              </div>
              <span class="connection-state" data-connection-label>연결안됨</span>
              <div class="connection-actions">
                <button type="button" id="codexProxyStartPanel" class="secondary">시작</button>
                <button type="button" id="codexProxyRefresh" class="secondary">새로고침</button>
              </div>
            </div>
            <dl class="status-list visually-hidden" id="codexProxyStatusList"></dl>
          </div>
        </div>'''
    html = re.sub(
        r'(\n\s*<div class="settings-grid">)',
        r'\1' + connection_card,
        html,
        count=1,
    )
    html = apply_release_static_version(html)
    html = html.replace(r"C:\Users\aiguy\Pictures\WebGUI-v3", r"C:\WebGrok\media")
    html = html.replace("실행 시 Hermes/Grok 쿼터가 사용될 수 있습니다.", "실행 시 Hermes 요청량이 사용될 수 있습니다.")
    return html


def strip_js_official_quota(js):
    js = apply_release_static_version(js)
    js = js.replace("let lastQuotaRefresh = 0;\n", "")
    js = js.replace("  refreshQuota();\n", "")
    js = re.sub(r"\n\s*refreshQuota\(true\);", "", js)
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
        r"\nfunction formatQuotaValue\(value\) \{[\s\S]*?\nfunction ensureModelOption\(",
        "\nfunction ensureModelOption(",
        js,
    )
    js = js.replace('  const grokReady = Boolean(data.grok_official?.chrome_running);\n', "")
    # Keep Codex status live in the Hermes-only release; only the homepage quota
    # route is removed.
    js = js.replace("hermesReady || codexReady || grokReady", "hermesReady || codexReady")
    js = js.replace("!(hermesReady || codexReady || grokReady)", "!(hermesReady || codexReady)")
    js = js.replace(
        '''    <span class="mini-service ${grokReady ? "is-live" : "is-off"}" title="Grok Official ${grokReady ? "Chrome ready" : "not ready"}">
      <span class="status-dot"></span><span>G</span>
    </span>
''',
        "",
    )
    js = re.sub(
        r'    <span class="mini-service \$\{hermesReady \? "is-live" : "is-off"\}" title="Hermes \$\{hermesReady \? "[^"]*" : "[^"]*"\}">',
        '    <span data-top-service="hermes" class="mini-service ${hermesReady ? "is-live" : "is-off"}" title="Hermes ${hermesReady ? "connected" : "disconnected"}">',
        js,
    )
    js = re.sub(
        r'    <span class="mini-service \$\{codexReady \? "is-live" : "is-off"\}" title="Codex \$\{codexReady \? "[^"]*" : "[^"]*"\}">',
        '    <span data-top-service="codex" class="mini-service ${codexReady ? "is-live" : "is-off"}" title="Codex ${codexReady ? "connected" : "disconnected"}">',
        js,
    )
    if "function setTopServiceBadge(" not in js:
        js = js.replace(
            "\nfunction renderStatus(data) {\n",
            """
function setTopServiceBadge(service, connected, title) {
  const item = document.querySelector(`[data-top-service="${service}"]`);
  if (!item) return;
  item.classList.toggle("is-live", Boolean(connected));
  item.classList.toggle("is-off", !connected);
  if (title) item.title = title;
  const statusPill = document.querySelector("#statusPill");
  if (!statusPill) return;
  const live = Boolean(statusPill.querySelector(".mini-service.is-live"));
  statusPill.classList.toggle("is-live", live);
  statusPill.classList.toggle("is-mock", !live);
}

function renderStatus(data) {
""",
            1,
        )
    js = js.replace(
        '''    <dt>Grok Official</dt><dd>${data.grok_official?.chrome_running ? `Chrome ${data.grok_official.chrome_port}` : "없음"}</dd>
''',
        "",
    )
    js = re.sub(
        r"function installQuotaPanel\(\) \{.*?\n\}",
        "",
        js,
        flags=re.S,
    )
    js = re.sub(
        r'\n\s*const oldUsageLink = document\.querySelector\("a\[href=\'https://grok\.com/\?_s=usage\'\]"\);[\s\S]*?oldUsageCard\.remove\(\);\n',
        "\n",
        js,
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
    js = re.sub(
        r'\n\s*<div class="connection-row is-disconnected" data-connection-service="grokOfficial">[\s\S]*?</div>\s*(?=\n\s*<div class="connection-row is-disconnected" data-connection-service="codex">)',
        "\n      ",
        js,
    )
    js = re.sub(r"\n\s*bindGrokOfficialPanel\(\);", "", js)
    js = re.sub(
        r"\nfunction setGrokOfficialStatus\(message, isError = false\) \{[\s\S]*?\nasync function refreshCodexProxyPanel\(",
        "\nasync function refreshCodexProxyPanel(",
        js,
    )
    js = js.replace(
        '      setConnectionBadge("hermes", Boolean(data.proxy_running),',
        '      setTopServiceBadge("hermes", Boolean(data.proxy_running), Boolean(data.proxy_running) ? "Hermes connected" : "Hermes proxy off");\n      setConnectionBadge("hermes", Boolean(data.proxy_running),',
        1,
    )
    js = js.replace(
        '    setConnectionBadge("hermes", false, data.running ?',
        '    setTopServiceBadge("hermes", false, data.running ? "Hermes auth pending" : "Hermes disconnected");\n    setConnectionBadge("hermes", false, data.running ?',
        1,
    )
    js = js.replace(
        '  } catch (error) {\n    setConnectionBadge("hermes", false,',
        '  } catch (error) {\n    setTopServiceBadge("hermes", false, "Hermes check failed");\n    setConnectionBadge("hermes", false,',
        1,
    )
    js = js.replace(
        '    const connected = Boolean(data.running && data.oauth_status === "ready");\n',
        '    const connected = Boolean(data.running && data.oauth_status === "ready");\n    setTopServiceBadge("codex", connected, connected ? "Codex connected" : (data.running ? "Codex OAuth checking" : "Codex disconnected"));\n',
        1,
    )
    js = js.replace(
        '    setConnectionBadge("codex", false,',
        '    setTopServiceBadge("codex", false, "Codex check failed");\n    setConnectionBadge("codex", false,',
        1,
    )
    js = re.sub(r"\n\s*compactSettingsLayout\(\);", "", js)
    js = re.sub(r"\n\s*installQuotaPanel\(\);", "", js)
    js = js.replace("/api/grok-official", "/disabled-home-quota")
    js = js.replace("grok_official", "home_quota_disabled")
    js = js.replace("grokOfficial", "homeQuotaDisabled")
    js = js.replace("Grok Official", "Homepage quota disabled")
    js = js.replace("Grok 공식홈", "공홈 쿼타 제거됨")
    js = js.replace("official:imagine", "disabled-home-image")
    js = js.replace("home_quota_disabled", "disabled_web_provider")
    js = js.replace("homeQuotaDisabled", "disabledWebProvider")
    js = js.replace("disabled-home-quota", "disabled-web-route")
    js = js.replace("Homepage quota disabled", "Disabled web provider")
    js = js.replace("공홈 쿼타 제거됨", "비활성화된 웹 경로")
    js = js.replace("disabled_web_provider", "release_removed_provider")
    js = js.replace("disabledWebProvider", "releaseRemovedProvider")
    js = js.replace("disabled-web-route", "release-disabled-route")
    js = js.replace("Disabled web provider", "Release removed route")
    js = js.replace("비활성화된 웹 경로", "릴리즈 제외 경로")
    js = js.replace("const releaseRemovedProviderEndpointByBase = {};\n\n", "")
    js = re.sub(
        r"function effectiveEndpointForForm\(form\) \{[\s\S]*?\n\}",
        'function effectiveEndpointForForm(form) {\n  return form?.dataset.endpoint || "";\n}',
        js,
        count=1,
    )
    js = js.replace('  if (String(imageModel || "").startsWith("official:")) return "release_removed_provider";\n', "")
    js = js.replace(
        '  return method === "official" || method === "frame" ? "release_removed_provider" : "hermes_proxy";',
        '  return "hermes_proxy";',
    )
    js = js.replace('provider === "release_removed_provider"', "false")
    js = js.replace('provider !== "release_removed_provider"', "true")
    js = re.sub(r'\n\s*"/release-disabled-route-[^"]+": [^,\n]+,?', "", js)
    js = js.replace('"release_removed_provider"', '"hermes_proxy"')
    js = js.replace("releaseRemovedProvider", "hermesProxy")
    js = js.replace("release-disabled-route", "removed-route")
    js = js.replace("릴리즈 제외 경로", "제외된 경로")
    js = re.sub(r'\n\s*release_removed_provider: "[^"]*",', "", js)
    return js


def strip_app_official_quota(py):
    py = remove_official_python_defs(py)
    py = py.replace('APP_BUILD_STAMP = "dev"', f'APP_BUILD_STAMP = "{STATIC_VERSION}"')
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
        if rule.rule.startswith("/api/grok-official"):
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
    py = py.replace("HOME_QUOTA_DISABLED", "DISABLED_WEB_PROVIDER")
    py = py.replace("home_quota_disabled", "disabled_web_provider")
    py = py.replace("home-quota-disabled", "disabled-web-route")
    py = py.replace("공홈 쿼타 제거됨", "비활성화된 웹 경로")
    py = py.replace("DISABLED_WEB_PROVIDER", "RELEASE_REMOVED_PROVIDER")
    py = py.replace("disabled_web_provider", "release_removed_provider")
    py = py.replace("disabled-web-route", "release-disabled-route")
    py = py.replace("비활성화된 웹 경로", "릴리즈 제외 경로")
    py = py.replace('provider == "release_removed_provider"', "False")
    py = py.replace('cfg["provider"] == "release_removed_provider"', "False")
    py = py.replace('"release_removed_provider"', '"removed_provider_unreachable"')
    py = py.replace("release_removed_provider", "removed_provider_unreachable")
    py = py.replace("release-disabled-route", "removed-route")
    py = py.replace("릴리즈 제외 경로", "제외된 경로")
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


def write_bootstrap():
    text = r'''@echo off
setlocal EnableExtensions
cd /d "%~dp0"
if not exist work mkdir work
set "LOG=work\bootstrap.log"
echo [%date% %time%] WebGrok bootstrap started>"%LOG%"

if exist work\bootstrap-ok.txt (
  call :find_python
  call :find_hermes
  if defined PYTHON_CMD if defined HERMES_EXE (
    echo %PYTHON_CMD%>work\python-cmd.txt
    echo %HERMES_EXE%>work\hermes-exe.txt
    echo Dependencies already prepared.>>"%LOG%"
    exit /b 0
  )
)

call :find_python
if not defined PYTHON_CMD (
  echo Usable Python 3.11+ was not detected. Trying winget install...
  echo Usable Python 3.11+ was not detected. Trying winget install...>>"%LOG%"
  call :install_python
  call :find_python
)
if not defined PYTHON_CMD (
  echo Python 3.11+ could not be installed automatically.
  echo Install Python 3.11+ manually, then run this file again.
  echo See %LOG%
  call :show_log
  pause
  exit /b 1
)

echo Using Python: %PYTHON_CMD%
echo %PYTHON_CMD%>work\python-cmd.txt
call :run %PYTHON_CMD% -m pip --version
if errorlevel 1 (
  call :run %PYTHON_CMD% -m ensurepip --upgrade
)
call :run %PYTHON_CMD% -m pip install --upgrade pip
if errorlevel 1 (
  echo Failed to prepare pip. See %LOG%
  call :show_log
  pause
  exit /b 1
)

call :run %PYTHON_CMD% -m pip install -r requirements.txt
if errorlevel 1 (
  echo Failed to install WebGrok Python requirements. See %LOG%
  call :show_log
  pause
  exit /b 1
)

call :find_hermes
if defined HERMES_EXE (
  echo Using existing Hermes Agent: %HERMES_EXE%
  echo Using existing Hermes Agent: %HERMES_EXE%>>"%LOG%"
  echo %HERMES_EXE%>work\hermes-exe.txt
) else (
  echo Hermes Agent was not found.
  echo Hermes Agent was not found.>>"%LOG%"
  echo Installing Hermes Agent into .hermes-venv...
  call :run %PYTHON_CMD% -m venv .hermes-venv
  if errorlevel 1 (
    echo Failed to create Hermes virtual environment. See %LOG%
    call :show_log
    pause
    exit /b 1
  )
  call :run ".hermes-venv\Scripts\python.exe" -m pip install --upgrade pip
  if errorlevel 1 (
    echo Failed to prepare Hermes pip. See %LOG%
    call :show_log
    pause
    exit /b 1
  )
  call :run ".hermes-venv\Scripts\python.exe" -m pip install "hermes-agent[cli]==0.15.1"
  if errorlevel 1 (
    echo Failed to install Hermes Agent. See %LOG%
    call :show_log
    pause
    exit /b 1
  )
)

call :find_hermes
if defined HERMES_EXE (
  echo %HERMES_EXE%>work\hermes-exe.txt
) else (
  echo Hermes Agent executable is still missing. See %LOG%
  call :show_log
  pause
  exit /b 1
)

call :check_node
if errorlevel 1 (
  echo Node.js was not found. Trying winget install...
  call :install_node
  call :check_node
  if errorlevel 1 (
    echo Node.js could not be installed automatically.
    echo Hermes features will still run, but Codex/ChatGPT OAuth proxy needs Node.js.
    echo See %LOG%
  )
)

echo ok>work\bootstrap-ok.txt
echo [%date% %time%] WebGrok bootstrap finished>>"%LOG%"
exit /b 0

:find_python
set "PYTHON_CMD="
for %%P in (
  "%LocalAppData%\Python\bin\python.exe"
  "%LocalAppData%\Python\pythoncore-3.14-64\python.exe"
  "%LocalAppData%\Programs\Python\Python314\python.exe"
  "%LocalAppData%\Programs\Python\Python313\python.exe"
  "%LocalAppData%\Programs\Python\Python312\python.exe"
  "%LocalAppData%\Programs\Python\Python311\python.exe"
  "%ProgramFiles%\Python314\python.exe"
  "%ProgramFiles%\Python313\python.exe"
  "%ProgramFiles%\Python312\python.exe"
  "%ProgramFiles%\Python311\python.exe"
  "%ProgramFiles(x86)%\Python314\python.exe"
  "%ProgramFiles(x86)%\Python313\python.exe"
  "%ProgramFiles(x86)%\Python312\python.exe"
  "%ProgramFiles(x86)%\Python311\python.exe"
) do (
  call :accept_python "%%~P"
  if defined PYTHON_CMD exit /b 0
)
for /f "delims=" %%P in ('where python.exe 2^>nul') do (
  call :accept_python "%%~P"
  if defined PYTHON_CMD exit /b 0
)
for /f "delims=" %%P in ('where py.exe 2^>nul') do (
  echo "%%~P" | find /I "\Microsoft\WindowsApps\" >nul
  if errorlevel 1 (
    "%%~P" -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>nul
    if not errorlevel 1 (
      set "PYTHON_CMD="%%~P" -3"
      exit /b 0
    )
  )
)
exit /b 1

:accept_python
set "PY_CANDIDATE=%~1"
if not exist "%PY_CANDIDATE%" exit /b 0
echo "%PY_CANDIDATE%" | find /I "\Microsoft\WindowsApps\" >nul
if not errorlevel 1 exit /b 0
"%PY_CANDIDATE%" -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>nul
if errorlevel 1 exit /b 0
set "PYTHON_CMD="%PY_CANDIDATE%""
exit /b 0

:install_python
where winget >nul 2>nul
if errorlevel 1 (
  echo winget is not available.>>"%LOG%"
  exit /b 1
)
call :run winget install --id Python.Python.3.12 -e --scope user --accept-package-agreements --accept-source-agreements
if errorlevel 1 (
  call :run winget install --id Python.Python.3.12 -e --accept-package-agreements --accept-source-agreements
)
exit /b %errorlevel%

:find_hermes
set "HERMES_ENV_EXE=%HERMES_EXE%"
set "HERMES_EXE="
if defined WEBGORK_HERMES_EXE call :accept_hermes "%WEBGORK_HERMES_EXE%"
if defined HERMES_EXE exit /b 0
if defined HERMES_ENV_EXE call :accept_hermes "%HERMES_ENV_EXE%"
if defined HERMES_EXE exit /b 0
if exist "work\hermes-exe.txt" (
  for /f "usebackq delims=" %%H in ("work\hermes-exe.txt") do (
    call :accept_hermes "%%~H"
    if defined HERMES_EXE exit /b 0
  )
)
if defined PYTHON_CMD (
  for /f "delims=" %%H in ('%PYTHON_CMD% -c "import pathlib, sysconfig; p=pathlib.Path(sysconfig.get_path('scripts') or '') / 'hermes.exe'; print(p if p.exists() else '')" 2^>nul') do (
    call :accept_hermes "%%~H"
    if defined HERMES_EXE exit /b 0
  )
)
for %%H in (
  ".hermes-venv\Scripts\hermes.exe"
  ".hermes-venv\bin\hermes"
  "%LocalAppData%\Python\bin\hermes.exe"
  "%LocalAppData%\Python\Scripts\hermes.exe"
  "%AppData%\Python\Scripts\hermes.exe"
  "%LocalAppData%\Python\pythoncore-3.14-64\Scripts\hermes.exe"
  "%LocalAppData%\Python\pythoncore-3.13-64\Scripts\hermes.exe"
  "%LocalAppData%\Python\pythoncore-3.12-64\Scripts\hermes.exe"
  "%LocalAppData%\Python\pythoncore-3.11-64\Scripts\hermes.exe"
  "%LocalAppData%\Programs\Python\Python314\Scripts\hermes.exe"
  "%LocalAppData%\Programs\Python\Python313\Scripts\hermes.exe"
  "%LocalAppData%\Programs\Python\Python312\Scripts\hermes.exe"
  "%LocalAppData%\Programs\Python\Python311\Scripts\hermes.exe"
  "%LocalAppData%\pipx\venvs\hermes-agent\Scripts\hermes.exe"
  "%LocalAppData%\pipx\venvs\hermes\Scripts\hermes.exe"
  "%UserProfile%\.local\bin\hermes.exe"
) do (
  call :accept_hermes "%%~H"
  if defined HERMES_EXE exit /b 0
)
for /d %%D in ("%LocalAppData%\Python\pythoncore-*") do (
  call :accept_hermes "%%~D\Scripts\hermes.exe"
  if defined HERMES_EXE exit /b 0
)
for /f "delims=" %%H in ('where hermes.exe 2^>nul') do (
  call :accept_hermes "%%~H"
  if defined HERMES_EXE exit /b 0
)
exit /b 1

:accept_hermes
set "HERMES_CANDIDATE=%~1"
if not exist "%HERMES_CANDIDATE%" exit /b 0
set "HERMES_EXE=%HERMES_CANDIDATE%"
exit /b 0

:check_node
if exist "%ProgramFiles%\nodejs\node.exe" set "PATH=%ProgramFiles%\nodejs;%PATH%"
if exist "%ProgramFiles(x86)%\nodejs\node.exe" set "PATH=%ProgramFiles(x86)%\nodejs;%PATH%"
where node.exe >nul 2>nul
if errorlevel 1 exit /b 1
where npx.cmd >nul 2>nul
if errorlevel 1 exit /b 1
exit /b 0

:install_node
where winget >nul 2>nul
if errorlevel 1 (
  echo winget is not available for Node.js install.>>"%LOG%"
  exit /b 1
)
call :run winget install --id OpenJS.NodeJS.LTS -e --scope user --accept-package-agreements --accept-source-agreements
if errorlevel 1 (
  call :run winget install --id OpenJS.NodeJS.LTS -e --accept-package-agreements --accept-source-agreements
)
if exist "%ProgramFiles%\nodejs" set "PATH=%ProgramFiles%\nodejs;%PATH%"
if exist "%ProgramFiles(x86)%\nodejs" set "PATH=%ProgramFiles(x86)%\nodejs;%PATH%"
exit /b 0

:run
echo ^> %*>>"%LOG%"
%*>>"%LOG%" 2>&1
exit /b %errorlevel%

:show_log
echo.
echo ---- Recent bootstrap log ----
if exist "%LOG%" (
  powershell -NoProfile -Command "Get-Content -LiteralPath '%CD%\\%LOG%' -Tail 40" 2>nul
) else (
  echo Log file was not created.
)
echo ---- End bootstrap log ----
echo.
exit /b 0
'''
    write(RELEASE_ROOT / "WEBGROK_BOOTSTRAP.bat", text)


def write_runner():
    text = f'''@echo off
setlocal
cd /d "%~dp0"

if exist WEBGROK_BOOTSTRAP.bat (
  call WEBGROK_BOOTSTRAP.bat
  if errorlevel 1 (
    echo WebGrok bootstrap failed. Check work\\bootstrap.log
    call :show_log work\\bootstrap.log
    pause
    exit /b 1
  )
)

set "PYTHON_CMD="
call :find_python
if not defined PYTHON_CMD (
  echo Python was not found after bootstrap.
  call :show_log work\\bootstrap.log
  pause
  exit /b 1
)

if not exist work mkdir work
set "HEALTH_STATE=missing"
for /f "delims=" %%S in ('powershell -NoProfile -Command "try {{ $json=(Invoke-WebRequest -UseBasicParsing http://127.0.0.1:7863/health -TimeoutSec 3).Content ^| ConvertFrom-Json; if($json.build_stamp -eq '{STATIC_VERSION}') {{ 'current' }} else {{ 'stale' }} }} catch {{ 'missing' }}" 2^>nul') do set "HEALTH_STATE=%%S"
if /I "%HEALTH_STATE%"=="stale" (
  echo Another or older WebGrok server is already running on 127.0.0.1:7863.
  echo Close the existing WebGrok server, then run this launcher again.
  pause
  exit /b 1
)
if /I not "%HEALTH_STATE%"=="current" (
  echo Starting WebGrok Hermes-only server...
  start "WebGrok Hermes Server" /min cmd /c "set WEBGORK_OPEN_BROWSER=0&& set WEBGORK_PORT=7863&& %PYTHON_CMD% work\\run_server.py"
  powershell -NoProfile -Command "$ok=$false; for($i=0; $i -lt 60; $i++){{ try {{ $json=(Invoke-WebRequest -UseBasicParsing http://127.0.0.1:7863/health -TimeoutSec 3).Content | ConvertFrom-Json; if($json.build_stamp -eq '{STATIC_VERSION}'){{ $ok=$true; break }} }} catch {{ }}; Start-Sleep -Milliseconds 500 }}; if($ok){{ exit 0 }} else {{ exit 1 }}"
  if errorlevel 1 (
    echo Server did not start, or an older WebGrok server is still occupying port 7863.
    echo Check work\\server-runner.log
    call :show_log work\\server-runner.log
    pause
    exit /b 1
  )
)

start "" http://127.0.0.1:7863/?v={STATIC_VERSION}
endlocal
exit /b 0

:find_python
set "PYTHON_CMD="
for %%P in (
  "%LocalAppData%\\Python\\bin\\python.exe"
  "%LocalAppData%\\Python\\pythoncore-3.14-64\\python.exe"
  "%LocalAppData%\\Programs\\Python\\Python314\\python.exe"
  "%LocalAppData%\\Programs\\Python\\Python313\\python.exe"
  "%LocalAppData%\\Programs\\Python\\Python312\\python.exe"
  "%LocalAppData%\\Programs\\Python\\Python311\\python.exe"
  "%ProgramFiles%\\Python314\\python.exe"
  "%ProgramFiles%\\Python313\\python.exe"
  "%ProgramFiles%\\Python312\\python.exe"
  "%ProgramFiles%\\Python311\\python.exe"
  "%ProgramFiles(x86)%\\Python314\\python.exe"
  "%ProgramFiles(x86)%\\Python313\\python.exe"
  "%ProgramFiles(x86)%\\Python312\\python.exe"
  "%ProgramFiles(x86)%\\Python311\\python.exe"
) do (
  call :accept_python "%%~P"
  if defined PYTHON_CMD exit /b 0
)
for /f "delims=" %%P in ('where python.exe 2^>nul') do (
  call :accept_python "%%~P"
  if defined PYTHON_CMD exit /b 0
)
for /f "delims=" %%P in ('where py.exe 2^>nul') do (
  echo "%%~P" | find /I "\\Microsoft\\WindowsApps\\" >nul
  if errorlevel 1 (
    "%%~P" -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>nul
    if not errorlevel 1 (
      set "PYTHON_CMD="%%~P" -3"
      exit /b 0
    )
  )
)
exit /b 1

:accept_python
set "PY_CANDIDATE=%~1"
if not exist "%PY_CANDIDATE%" exit /b 0
echo "%PY_CANDIDATE%" | find /I "\\Microsoft\\WindowsApps\\" >nul
if not errorlevel 1 exit /b 0
"%PY_CANDIDATE%" -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>nul
if errorlevel 1 exit /b 0
set "PYTHON_CMD="%PY_CANDIDATE%""
exit /b 0

:show_log
echo.
echo ---- Recent log: %~1 ----
if exist "%~1" (
  powershell -NoProfile -Command "Get-Content -LiteralPath '%CD%\\%~1' -Tail 50" 2>nul
) else (
  echo Log file was not created.
)
echo ---- End log ----
echo.
exit /b 0
'''
    write(RELEASE_ROOT / "RUN_WEBGROK_HERMES_ONLY.bat", text)


def build_chrome_app_launcher():
    source = RELEASE_ROOT / "work" / "WebGrokChromeAppLauncher.cs"
    exe = RELEASE_ROOT / "WEBGROK_CHROME_APP.exe"
    csc = Path(r"C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe")
    if not csc.exists():
        csc = Path(r"C:\Windows\Microsoft.NET\Framework\v4.0.30319\csc.exe")
    code = f'''using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Net;
using System.Threading;
using System.Windows.Forms;

internal static class WebGrokChromeAppLauncher
{{
    private const string Port = "7863";
    private const string BuildStamp = "{STATIC_VERSION}";
    private const string HealthUrl = "http://127.0.0.1:" + Port + "/health";
    private const string AppUrl = "http://127.0.0.1:" + Port + "/?v={STATIC_VERSION}";

    [STAThread]
    private static int Main()
    {{
        string root = AppDomain.CurrentDomain.BaseDirectory;
        Process serverProcess = null;
        bool startedServer = false;
        try
        {{
            bool serverResponding = HealthResponds();
            if (!HealthMatchesBuild())
            {{
                if (serverResponding)
                {{
                    MessageBox.Show(
                        "Another or older WebGrok server is already running on 127.0.0.1:" + Port + ".\\r\\n\\r\\nClose the existing WebGrok server, then run this launcher again.",
                        "WebGrok Chrome App",
                        MessageBoxButtons.OK,
                        MessageBoxIcon.Warning);
                    return 1;
                }}
                EnsureBootstrap(root);
                serverProcess = StartServer(root);
                startedServer = serverProcess != null;
            }}
            if (!WaitForHealth())
            {{
                MessageBox.Show(
                    "WebGrok server did not start.\\r\\n\\r\\n" + ReadFailureLogs(root),
                    "WebGrok Chrome App",
                    MessageBoxButtons.OK,
                    MessageBoxIcon.Error);
                return 1;
            }}
            Process chromeProcess = OpenChromeApp(root);
            if (startedServer)
            {{
                WaitForChromeAppExit(chromeProcess);
                StopStartedServer(serverProcess);
            }}
            return 0;
        }}
        catch (Exception ex)
        {{
            MessageBox.Show(
                ex.Message + "\\r\\n\\r\\n" + ReadFailureLogs(root),
                "WebGrok Chrome App",
                MessageBoxButtons.OK,
                MessageBoxIcon.Error);
            return 1;
        }}
    }}

    private static bool HealthResponds()
    {{
        try
        {{
            HttpWebRequest request = (HttpWebRequest)WebRequest.Create(HealthUrl);
            request.Method = "GET";
            request.Timeout = 1500;
            using (HttpWebResponse response = (HttpWebResponse)request.GetResponse())
            {{
                return (int)response.StatusCode >= 200 && (int)response.StatusCode < 300;
            }}
        }}
        catch
        {{
            return false;
        }}
    }}

    private static bool HealthMatchesBuild()
    {{
        try
        {{
            HttpWebRequest request = (HttpWebRequest)WebRequest.Create(HealthUrl);
            request.Method = "GET";
            request.Timeout = 1500;
            using (HttpWebResponse response = (HttpWebResponse)request.GetResponse())
            using (Stream stream = response.GetResponseStream())
            using (StreamReader reader = new StreamReader(stream))
            {{
                string body = reader.ReadToEnd();
                return (int)response.StatusCode >= 200
                    && (int)response.StatusCode < 300
                    && body.Contains("\\"build_stamp\\":\\"" + BuildStamp + "\\"");
            }}
        }}
        catch
        {{
            return false;
        }}
    }}

    private static bool WaitForHealth()
    {{
        for (int i = 0; i < 80; i++)
        {{
            if (HealthMatchesBuild()) return true;
            Thread.Sleep(500);
        }}
        return false;
    }}

    private static Process StartServer(string root)
    {{
        string python = FindPython();
        if (String.IsNullOrEmpty(python))
        {{
            throw new InvalidOperationException("Python was not found after bootstrap. Check work\\\\bootstrap.log.");
        }}

        ProcessStartInfo info = new ProcessStartInfo();
        info.WorkingDirectory = root;
        info.UseShellExecute = false;
        info.CreateNoWindow = true;
        info.WindowStyle = ProcessWindowStyle.Minimized;
        info.EnvironmentVariables["WEBGORK_OPEN_BROWSER"] = "0";
        info.EnvironmentVariables["WEBGORK_PORT"] = Port;
        if (Path.GetFileName(python).Equals("py.exe", StringComparison.OrdinalIgnoreCase))
        {{
            info.FileName = python;
            info.Arguments = "-3 work\\\\run_server.py";
        }}
        else
        {{
            info.FileName = python;
            info.Arguments = "work\\\\run_server.py";
        }}
        return Process.Start(info);
    }}

    private static string FindPython()
    {{
        string localAppData = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
        string programFiles = Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles);
        string programFilesX86 = Environment.GetFolderPath(Environment.SpecialFolder.ProgramFilesX86);
        string[] candidates = new string[]
        {{
            Path.Combine(localAppData, "Python", "bin", "python.exe"),
            Path.Combine(localAppData, "Python", "pythoncore-3.14-64", "python.exe"),
            Path.Combine(localAppData, "Programs", "Python", "Python314", "python.exe"),
            Path.Combine(localAppData, "Programs", "Python", "Python313", "python.exe"),
            Path.Combine(localAppData, "Programs", "Python", "Python312", "python.exe"),
            Path.Combine(localAppData, "Programs", "Python", "Python311", "python.exe"),
            Path.Combine(programFiles, "Python314", "python.exe"),
            Path.Combine(programFiles, "Python313", "python.exe"),
            Path.Combine(programFiles, "Python312", "python.exe"),
            Path.Combine(programFiles, "Python311", "python.exe"),
            Path.Combine(programFilesX86, "Python314", "python.exe"),
            Path.Combine(programFilesX86, "Python313", "python.exe"),
            Path.Combine(programFilesX86, "Python312", "python.exe"),
            Path.Combine(programFilesX86, "Python311", "python.exe")
        }};
        foreach (string item in candidates)
        {{
            if (AcceptPython(item, false)) return item;
        }}
        foreach (string item in FindAllOnPath("python.exe"))
        {{
            if (AcceptPython(item, false)) return item;
        }}
        foreach (string item in FindAllOnPath("py.exe"))
        {{
            if (AcceptPython(item, true)) return item;
        }}
        return "";
    }}

    private static bool AcceptPython(string path, bool pythonLauncher)
    {{
        if (String.IsNullOrEmpty(path)) return false;
        if (!File.Exists(path)) return false;
        if (path.IndexOf("\\\\Microsoft\\\\WindowsApps\\\\", StringComparison.OrdinalIgnoreCase) >= 0) return false;

        ProcessStartInfo info = new ProcessStartInfo();
        info.FileName = path;
        info.Arguments = pythonLauncher
            ? "-3 -c \\"import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)\\""
            : "-c \\"import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)\\"";
        info.UseShellExecute = false;
        info.CreateNoWindow = true;
        try
        {{
            using (Process process = Process.Start(info))
            {{
                if (process == null) return false;
                if (!process.WaitForExit(5000))
                {{
                    try {{ process.Kill(); }} catch {{ }}
                    return false;
                }}
                return process.ExitCode == 0;
            }}
        }}
        catch
        {{
            return false;
        }}
    }}

    private static void EnsureBootstrap(string root)
    {{
        if (!NeedsBootstrap(root)) return;
        string bootstrap = Path.Combine(root, "WEBGROK_BOOTSTRAP.bat");
        if (!File.Exists(bootstrap))
        {{
            throw new InvalidOperationException("WEBGROK_BOOTSTRAP.bat was not found.");
        }}
        MessageBox.Show(
            "WebGrok will prepare first-run dependencies now. If Python 3.11+ or Hermes Agent is already installed, it will be reused. If Python is missing, WebGrok may try to install it through winget. The setup can also install app Python packages, Hermes Agent when missing, and optionally Node.js. A setup window will open and may take several minutes.",
            "WebGrok first-run setup",
            MessageBoxButtons.OK,
            MessageBoxIcon.Information);
        ProcessStartInfo info = new ProcessStartInfo();
        info.FileName = "cmd.exe";
        info.Arguments = "/c \\"" + bootstrap + "\\"";
        info.WorkingDirectory = root;
        info.UseShellExecute = true;
        info.WindowStyle = ProcessWindowStyle.Normal;
        Process process = Process.Start(info);
        if (process == null)
        {{
            throw new InvalidOperationException("Failed to start WebGrok bootstrap.");
        }}
        process.WaitForExit();
        if (process.ExitCode != 0)
        {{
            throw new InvalidOperationException("WebGrok bootstrap failed.");
        }}
    }}

    private static string ReadFailureLogs(string root)
    {{
        string bootstrap = TailFile(Path.Combine(root, "work", "bootstrap.log"), 5000);
        string server = TailFile(Path.Combine(root, "work", "server-runner.log"), 5000);
        string message = "";
        if (!String.IsNullOrEmpty(bootstrap))
        {{
            message += "Recent bootstrap.log:\\r\\n" + bootstrap + "\\r\\n\\r\\n";
        }}
        if (!String.IsNullOrEmpty(server))
        {{
            message += "Recent server-runner.log:\\r\\n" + server + "\\r\\n";
        }}
        if (String.IsNullOrEmpty(message))
        {{
            message = "No setup log was found yet. Check the release folder's work directory.";
        }}
        return message;
    }}

    private static string TailFile(string path, int maxChars)
    {{
        try
        {{
            if (!File.Exists(path)) return "";
            string text = File.ReadAllText(path);
            text = text.Replace("\\n", "\\r\\n").Replace("\\r\\r\\n", "\\r\\n");
            if (text.Length <= maxChars) return text;
            return text.Substring(text.Length - maxChars);
        }}
        catch (Exception ex)
        {{
            return "Could not read " + path + ": " + ex.Message;
        }}
    }}

    private static bool NeedsBootstrap(string root)
    {{
        if (String.IsNullOrEmpty(FindPython())) return true;
        string marker = Path.Combine(root, "work", "bootstrap-ok.txt");
        if (!File.Exists(marker)) return true;
        if (String.IsNullOrEmpty(FindHermes(root))) return true;
        return false;
    }}

    private static string FindHermes(string root)
    {{
        string localAppData = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
        string appData = Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData);
        string userProfile = Environment.GetFolderPath(Environment.SpecialFolder.UserProfile);
        string hint = Path.Combine(root, "work", "hermes-exe.txt");
        if (File.Exists(hint))
        {{
            try
            {{
                string value = File.ReadAllText(hint).Trim().Trim('"');
                if (File.Exists(value)) return value;
            }}
            catch {{ }}
        }}
        string[] candidates = new string[]
        {{
            Path.Combine(root, ".hermes-venv", "Scripts", "hermes.exe"),
            Path.Combine(root, ".hermes-venv", "bin", "hermes"),
            Path.Combine(localAppData, "Python", "bin", "hermes.exe"),
            Path.Combine(localAppData, "Python", "Scripts", "hermes.exe"),
            Path.Combine(appData, "Python", "Scripts", "hermes.exe"),
            Path.Combine(localAppData, "Python", "pythoncore-3.14-64", "Scripts", "hermes.exe"),
            Path.Combine(localAppData, "Python", "pythoncore-3.13-64", "Scripts", "hermes.exe"),
            Path.Combine(localAppData, "Python", "pythoncore-3.12-64", "Scripts", "hermes.exe"),
            Path.Combine(localAppData, "Python", "pythoncore-3.11-64", "Scripts", "hermes.exe"),
            Path.Combine(localAppData, "Programs", "Python", "Python314", "Scripts", "hermes.exe"),
            Path.Combine(localAppData, "Programs", "Python", "Python313", "Scripts", "hermes.exe"),
            Path.Combine(localAppData, "Programs", "Python", "Python312", "Scripts", "hermes.exe"),
            Path.Combine(localAppData, "Programs", "Python", "Python311", "Scripts", "hermes.exe"),
            Path.Combine(localAppData, "pipx", "venvs", "hermes-agent", "Scripts", "hermes.exe"),
            Path.Combine(localAppData, "pipx", "venvs", "hermes", "Scripts", "hermes.exe"),
            Path.Combine(userProfile, ".local", "bin", "hermes.exe")
        }};
        foreach (string item in candidates)
        {{
            if (File.Exists(item)) return item;
        }}
        try
        {{
            string pythonRoot = Path.Combine(localAppData, "Python");
            if (Directory.Exists(pythonRoot))
            {{
                foreach (string dir in Directory.GetDirectories(pythonRoot, "pythoncore-*"))
                {{
                    string item = Path.Combine(dir, "Scripts", "hermes.exe");
                    if (File.Exists(item)) return item;
                }}
            }}
        }}
        catch {{ }}
        foreach (string item in FindAllOnPath("hermes.exe"))
        {{
            if (File.Exists(item)) return item;
        }}
        return "";
    }}

    private static bool HermesProxyCapable(string path)
    {{
        if (String.IsNullOrEmpty(path)) return false;
        if (!File.Exists(path)) return false;
        ProcessStartInfo info = new ProcessStartInfo();
        info.FileName = path;
        info.Arguments = "proxy status";
        info.UseShellExecute = false;
        info.CreateNoWindow = true;
        try
        {{
            using (Process process = Process.Start(info))
            {{
                if (process == null) return false;
                if (!process.WaitForExit(8000))
                {{
                    try {{ process.Kill(); }} catch {{ }}
                    return false;
                }}
                return process.ExitCode == 0;
            }}
        }}
        catch
        {{
            return false;
        }}
    }}

    private static string FindChrome()
    {{
        string[] candidates = new string[]
        {{
            Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles), "Google", "Chrome", "Application", "chrome.exe"),
            Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ProgramFilesX86), "Google", "Chrome", "Application", "chrome.exe"),
            Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "Google", "Chrome", "Application", "chrome.exe")
        }};
        foreach (string item in candidates)
        {{
            if (File.Exists(item)) return item;
        }}
        return FindOnPath("chrome.exe");
    }}

    private static string FindOnPath(string fileName)
    {{
        string path = Environment.GetEnvironmentVariable("PATH") ?? "";
        foreach (string dir in path.Split(Path.PathSeparator))
        {{
            try
            {{
                if (String.IsNullOrWhiteSpace(dir)) continue;
                string full = Path.Combine(dir.Trim(), fileName);
                if (File.Exists(full)) return full;
            }}
            catch {{ }}
        }}
        return "";
    }}

    private static string[] FindAllOnPath(string fileName)
    {{
        List<string> matches = new List<string>();
        string path = Environment.GetEnvironmentVariable("PATH") ?? "";
        foreach (string dir in path.Split(Path.PathSeparator))
        {{
            try
            {{
                if (String.IsNullOrWhiteSpace(dir)) continue;
                string full = Path.Combine(dir.Trim(), fileName);
                if (File.Exists(full)) matches.Add(full);
            }}
            catch {{ }}
        }}
        return matches.ToArray();
    }}

    private static Process OpenChromeApp(string root)
    {{
        string chrome = FindChrome();
        if (!String.IsNullOrEmpty(chrome))
        {{
            string profile = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "WebGrok", "v3-Hermes", "chrome-app-profile");
            Directory.CreateDirectory(profile);
            ProcessStartInfo info = new ProcessStartInfo();
            info.FileName = chrome;
            info.Arguments = "--user-data-dir=\\"" + profile + "\\" --no-first-run --app=\\"" + AppUrl + "\\" --new-window";
            info.UseShellExecute = false;
            return Process.Start(info);
        }}
        ProcessStartInfo fallback = new ProcessStartInfo(AppUrl);
        fallback.UseShellExecute = true;
        Process.Start(fallback);
        return null;
    }}

    private static void WaitForChromeAppExit(Process chromeProcess)
    {{
        if (chromeProcess == null) return;
        try
        {{
            chromeProcess.WaitForExit();
        }}
        catch
        {{
        }}
    }}

    private static void StopStartedServer(Process serverProcess)
    {{
        if (serverProcess == null) return;
        try
        {{
            if (serverProcess.HasExited) return;
            try
            {{
                serverProcess.CloseMainWindow();
            }}
            catch
            {{
            }}
            if (!serverProcess.WaitForExit(1500))
            {{
                serverProcess.Kill();
                serverProcess.WaitForExit(5000);
            }}
        }}
        catch
        {{
        }}
    }}
}}
'''
    write(source, code)
    if not csc.exists():
        print("Chrome app launcher skipped: csc.exe not found")
        return
    subprocess.run(
        [
            str(csc),
            "/nologo",
            "/target:winexe",
            "/platform:anycpu",
            "/reference:System.Windows.Forms.dll",
            f"/out:{exe}",
            str(source),
        ],
        check=True,
    )
    try:
        source.unlink()
    except OSError:
        pass


def write_release_notes():
    text = f"""# WebGrok v3 Hermes-only Release

This release folder is a privacy-clean, one-click runnable package.

Included:
- Hermes Proxy based image generation, image editing, image-to-video, queue, templates, library, and local media tools.
- A sanitized sample video template JSON. No sample image or video assets are bundled.
- `USER_MANUAL.md` Korean feature/user manual.
- `WEBGROK_BOOTSTRAP.bat` first-run dependency bootstrapper.
- `RUN_WEBGROK_HERMES_ONLY.bat` one-click launcher.
- `WEBGROK_CHROME_APP.exe` one-click Chrome app-mode launcher.

Excluded:
- Homepage quota UI and related web-session routes.
- Homepage Chrome profile, cookie, CDP, and browser-session launch data.
- `.webgork-private`, `.chrome-*`, generated media-library images/videos, `backups`, local logs, git metadata, and local settings from the development workspace.

First run:
1. Run `WEBGROK_CHROME_APP.exe` to open the app in Chrome app mode, or run `RUN_WEBGROK_HERMES_ONLY.bat` to open it in the default browser.
2. On the first run, WebGrok prepares app Python packages automatically. If a usable Python 3.11+ or Hermes Agent is already installed, WebGrok reuses it. It installs a local Hermes Agent venv only when Hermes Agent is missing, and tries to install Python/Node.js through winget only when they are missing.
3. Open Settings, press `인증`, and complete Hermes xAI OAuth.

Note:
- `WEBGROK_CHROME_APP.exe` is locally built and unsigned, so Windows may show a SmartScreen/security prompt.
- If an older WebGrok server is already running on `127.0.0.1:7863`, close that server before launching this release.

Build stamp: {STATIC_VERSION}
"""
    write(RELEASE_ROOT / "README_RELEASE.md", text)


def write_user_manual():
    copy_file(ROOT / "docs" / "USER_MANUAL_HERMES_RELEASE.md", RELEASE_ROOT / "USER_MANUAL.md")


def write_clean_settings():
    settings = {
        "provider": "hermes_proxy",
        "hermes_base_url": "http://127.0.0.1:8645/v1",
        "codex_proxy_base_url": "http://127.0.0.1:3333",
    }
    write(RELEASE_ROOT / "webgork-settings.json", json.dumps(settings, ensure_ascii=False, indent=2))


def write_release_media_seed():
    library = RELEASE_ROOT / "media-library"
    library.mkdir(parents=True, exist_ok=True)
    json_defaults = {
        "metadata.json": [],
        "prompts.json": [],
        "projects.json": [],
        "video-templates.json": [],
        "video-template-blocks.json": [],
    }
    for filename, default in json_defaults.items():
        seed = RELEASE_SEED_ROOT / filename
        if seed.exists():
            copy_file(seed, library / filename)
        else:
            write(library / filename, json.dumps(default, ensure_ascii=False, indent=2) + "\n")
    usage = {"requests": 0, "tokens": 0, "cost_usd": 0, "last_usage": None}
    write(library / "usage.json", json.dumps(usage, ensure_ascii=False, indent=2) + "\n")


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
        apply_release_static_version(read(RELEASE_ROOT / "static" / "service-worker.js")),
    )
    write_clean_settings()
    write_release_media_seed()
    write_bootstrap()
    write_runner()
    build_chrome_app_launcher()
    write_release_notes()
    write_user_manual()
    print(RELEASE_ROOT)


if __name__ == "__main__":
    main()
