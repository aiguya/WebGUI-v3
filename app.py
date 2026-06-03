import base64
import hashlib
import html
import json
import mimetypes
import os
import re
import secrets
import shutil
import socket
import struct
import subprocess
import sys
import time
import uuid
import webbrowser
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Lock, Thread
from urllib.parse import parse_qs, urlparse
from urllib.parse import urlencode

import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, make_response, redirect, render_template, request, send_from_directory, session
from werkzeug.utils import secure_filename


load_dotenv()

APP_ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
ROOT = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
SETTINGS_PATH = ROOT / "webgork-settings.json"
PRIVATE_STATE_DIR = Path(os.getenv("WEBGORK_CONFIG_DIR") or (ROOT / ".webgork-private")).expanduser().resolve()
SENSITIVE_MEDIA_FILENAMES = {
    "xai-oauth-token.json",
    "webgork-oauth-token.json",
}
HERMES_LOGIN_LOCK = Lock()
HERMES_LOGIN_STATE = {
    "process": None,
    "lines": [],
    "auth_url": "",
    "started_at": None,
}
HERMES_PROXY_PROCESS = None
CODEX_PROXY_PROCESS = None


def read_settings():
    try:
        return json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, FileNotFoundError):
        return {}


def write_settings(settings):
    SETTINGS_PATH.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8")


def discover_codex_proxy_url():
    candidates = [
        PRIVATE_STATE_DIR / "ima2" / "server.json",
        Path.home() / ".ima2" / "server.json",
        Path(os.getenv("IMA2_ADVERTISE_FILE") or "") if os.getenv("IMA2_ADVERTISE_FILE") else None,
    ]
    for path in candidates:
        if not path:
            continue
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            backend = data.get("backend") if isinstance(data, dict) else None
            url = (backend or {}).get("url") or data.get("url")
            if url:
                return str(url).strip().rstrip("/")
        except (OSError, json.JSONDecodeError, AttributeError):
            continue
    return ""


def codex_proxy_config_dir():
    path = PRIVATE_STATE_DIR / "ima2"
    path.mkdir(parents=True, exist_ok=True)
    return path


def ensure_codex_proxy_oauth_config():
    cfg_dir = codex_proxy_config_dir()
    config_file = cfg_dir / "config.json"
    data = {}
    if config_file.exists():
        try:
            data = json.loads(config_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = {}
    data["provider"] = "oauth"
    config_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return cfg_dir


def media_root():
    configured = read_settings().get("media_root") or os.getenv("WEBGORK_MEDIA_ROOT")
    if configured:
        return Path(configured).expanduser().resolve()
    return (ROOT / "media-library").resolve()


def media_path(*parts):
    return media_root().joinpath(*parts)


def ensure_media_dirs_for(root):
    root = Path(root)
    for folder in ("image", "video", "uploads", "thumbnails", "manga_trans", "manga_panels", "metadata-backups"):
        (root / folder).mkdir(parents=True, exist_ok=True)
    meta = root / "metadata.json"
    prompts = root / "prompts.json"
    video_templates = root / "video-templates.json"
    video_template_blocks = root / "video-template-blocks.json"
    usage = root / "usage.json"
    if not meta.exists():
        meta.write_text("[]", encoding="utf-8")
    if not prompts.exists():
        prompts.write_text("[]", encoding="utf-8")
    if not video_templates.exists():
        video_templates.write_text("[]", encoding="utf-8")
    if not video_template_blocks.exists():
        video_template_blocks.write_text("[]", encoding="utf-8")
    if not usage.exists():
        usage.write_text(json.dumps({"requests": 0, "tokens": 0, "cost_usd": 0, "last_usage": None}), encoding="utf-8")


def ensure_media_dirs():
    ensure_media_dirs_for(media_root())


def ensure_private_state_dir():
    PRIVATE_STATE_DIR.mkdir(parents=True, exist_ok=True)


def merge_copy_tree(src, dst):
    src = Path(src)
    dst = Path(dst)
    if not src.exists() or src.resolve() == dst.resolve():
        return
    for item in src.rglob("*"):
        rel = item.relative_to(src)
        target = dst / rel
        if item.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        elif item.is_file():
            if item.name in SENSITIVE_MEDIA_FILENAMES:
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists():
                shutil.copy2(item, target)


def meta_path():
    return media_path("metadata.json")


def metadata_backup_dir():
    return media_path("metadata-backups")


def usage_path():
    return media_path("usage.json")


def prompts_path():
    return media_path("prompts.json")


def video_templates_path():
    return media_path("video-templates.json")


def video_template_blocks_path():
    return media_path("video-template-blocks.json")


def oauth_token_path():
    return PRIVATE_STATE_DIR / "xai-oauth-token.json"


def migrate_legacy_oauth_token():
    ensure_private_state_dir()
    legacy_path = media_path("xai-oauth-token.json")
    new_path = oauth_token_path()
    if legacy_path.exists():
        if not new_path.exists():
            shutil.move(str(legacy_path), str(new_path))
        else:
            legacy_path.unlink()


ensure_private_state_dir()
ensure_media_dirs()
migrate_legacy_oauth_token()

app = Flask(__name__, template_folder=str(APP_ROOT / "templates"), static_folder=str(APP_ROOT / "static"))
app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024 * 1024
app.secret_key = os.getenv("WEBGORK_SECRET_KEY", uuid.uuid4().hex)

LAST_ERROR = None
OAUTH_PENDING = {}
OAUTH_CALLBACK_SERVER = None
MANGA_BATCH_JOBS = {}
MANGA_BATCH_LOCK = Lock()
MANGA_BATCH_MAX_UPLOADS = 500
MANGA_BATCH_MAX_PARALLEL = 50
MANGA_PANEL_REFERENCE_LIMIT = 2
MANGA_PANEL_MAX_CROPS = 1000


def config():
    settings = read_settings()
    session_api_key = session.get("xai_api_key") if request else None
    requested_mode = session.get("webgork_mode", os.getenv("WEBGORK_MODE", "mock")).strip().lower() if request else os.getenv("WEBGORK_MODE", "mock").strip().lower()
    provider = (settings.get("provider") or os.getenv("WEBGORK_PROVIDER") or "direct").strip().lower()
    if provider not in {"direct", "hermes_proxy", "openai_api", "codex_proxy"}:
        provider = "direct"
    hermes_base = (settings.get("hermes_base_url") or os.getenv("HERMES_PROXY_BASE_URL") or "").strip().rstrip("/")
    hermes_key = (settings.get("hermes_api_key") or os.getenv("HERMES_PROXY_API_KEY") or "").strip()
    openai_key = (settings.get("openai_api_key") or os.getenv("OPENAI_API_KEY") or "").strip()
    codex_base = (settings.get("codex_proxy_base_url") or os.getenv("CODEX_IMAGE_PROXY_BASE_URL") or discover_codex_proxy_url() or "http://127.0.0.1:3333").strip().rstrip("/")
    mode = "live" if (
        (provider == "hermes_proxy" and hermes_base)
        or (provider == "openai_api" and openai_key)
        or (provider == "codex_proxy" and codex_base)
    ) else ("live" if oauth_token_path().exists() else requested_mode)
    return {
        "mode": mode,
        "provider": provider,
        "api_key": session_api_key or os.getenv("XAI_API_KEY", ""),
        "management_key": session.get("xai_management_key", os.getenv("XAI_MANAGEMENT_KEY", "")) if request else os.getenv("XAI_MANAGEMENT_KEY", ""),
        "team_id": session.get("xai_team_id", os.getenv("XAI_TEAM_ID", "")) if request else os.getenv("XAI_TEAM_ID", ""),
        "api_base": hermes_base if provider == "hermes_proxy" and hermes_base else os.getenv("XAI_API_BASE", "https://api.x.ai/v1").rstrip("/"),
        "hermes_base_url": hermes_base,
        "hermes_api_key": hermes_key,
        "openai_api_key": openai_key,
        "openai_api_base": os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1").rstrip("/"),
        "openai_image_model": os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-1.5"),
        "codex_proxy_base_url": codex_base,
        "codex_image_model": os.getenv("CODEX_IMAGE_MODEL", "gpt-5.4-mini"),
        "management_base": os.getenv("XAI_MANAGEMENT_BASE", "https://management-api.x.ai").rstrip("/"),
        "image_model": os.getenv("XAI_IMAGE_MODEL", "grok-imagine-image-quality"),
        "video_model": os.getenv("XAI_VIDEO_MODEL", "grok-imagine-video"),
        "vision_model": os.getenv("XAI_VISION_MODEL", "grok-4.3"),
        "prompt_planner_model": os.getenv("XAI_PROMPT_PLANNER_MODEL", "grok-4.20-0309-reasoning"),
        "oauth_issuer": os.getenv("XAI_OAUTH_ISSUER", "https://auth.x.ai").rstrip("/"),
        "oauth_client_id": os.getenv("XAI_OAUTH_CLIENT_ID", ""),
        "oauth_scope": os.getenv("XAI_OAUTH_SCOPE", "openid profile email offline_access grok-cli:access api:access"),
        "oauth_redirect_uri": os.getenv("XAI_OAUTH_REDIRECT_URI", "http://127.0.0.1:56121/callback"),
    }


def now_stamp():
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def public_path(path):
    try:
        return "/" + path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return "/media-library/" + path.resolve().relative_to(media_root()).as_posix()


def error_detail_text(detail):
    if detail is None:
        return ""
    text = str(detail)
    response = getattr(detail, "response", None)
    if response is not None:
        try:
            response_detail = response_error_detail(response)
        except Exception:
            response_detail = getattr(response, "text", "") or ""
        if response_detail:
            text = f"{text} {response_detail}".strip()
    if not text:
        text = repr(detail)
    return text[:4000]


def safe_error(message, detail=None, status=400):
    global LAST_ERROR
    detail_text = error_detail_text(detail)
    lowered_detail = detail_text.lower()
    policy_blocked = (
        "content moderation" in lowered_detail
        or "content_policy_violation" in lowered_detail
        or "content policy" in lowered_detail
        or "policy_violation" in lowered_detail
    )
    user_message = "콘텐츠 정책 검열로 생성이 차단되었습니다." if policy_blocked else message
    next_message = (
        "프롬프트나 참조 이미지의 민감한 요소를 줄이고 다시 시도해 주세요."
        if policy_blocked
        else "입력값과 설정을 확인한 뒤 다시 실행해 주세요."
    )
    LAST_ERROR = {
        "time": datetime.now(timezone.utc).isoformat(),
        "message": user_message,
        "detail": detail_text,
    }
    return jsonify({
        "ok": False,
        "error": user_message,
        "detail": detail_text,
        "next": next_message,
    }), status


def valid_aspect_ratio(value, allow_source=False):
    allowed = {"auto", "2:3", "3:2", "1:1", "9:16", "16:9"}
    if allow_source:
        allowed.add("source")
    ratio = (value or "auto").strip()
    return ratio if ratio in allowed else "auto"


def valid_image_resolution(value):
    resolution = (value or "auto").strip().lower()
    return resolution if resolution in {"auto", "1k", "2k"} else "auto"


def valid_image_model(value, cfg=None):
    fallback = (cfg or config())["image_model"]
    model = (value or fallback).strip()
    if re.fullmatch(r"[A-Za-z0-9._:-]{1,96}", model):
        return model
    return fallback


def valid_openai_image_model(value, cfg=None):
    fallback = (cfg or config())["openai_image_model"]
    model = (value or fallback).strip()
    if model in {"gpt-image-1.5", "gpt-image-1", "gpt-image-1-mini"}:
        return model
    return fallback


def valid_codex_image_model(value, cfg=None):
    fallback = (cfg or config())["codex_image_model"]
    model = (value or fallback).strip()
    if model in {"gpt-5.4-mini", "gpt-5.4", "gpt-5.5"}:
        return model
    return fallback


def selected_image_backend(value, cfg=None):
    cfg = cfg or config()
    requested = (value or "").strip()
    if requested.startswith("gpt-image-") or (not requested and cfg["provider"] == "openai_api"):
        raise ValueError("OpenAI API 모델은 현재 UI에서 사용하지 않습니다. Codex/ChatGPT OAuth 모델(gpt-5 계열)을 선택해 주세요.")
    if requested.startswith("gpt-5.") or (not requested and cfg["provider"] == "codex_proxy"):
        model = valid_codex_image_model(requested, cfg)
        if requested and model != requested:
            raise ValueError(f"지원하지 않는 Codex 이미지 모델입니다: {requested}")
        return "codex_proxy", model
    model = valid_image_model(requested, cfg)
    if requested and model != requested:
        raise ValueError(f"지원하지 않는 Grok 이미지 모델입니다: {requested}")
    provider = cfg["provider"] if cfg["provider"] in {"direct", "hermes_proxy"} else ("hermes_proxy" if cfg.get("hermes_base_url") else "direct")
    return provider, model


def selected_image_model(value, cfg=None):
    return selected_image_backend(value, cfg)[1]


def valid_edit_input_mode(value):
    mode = (value or "stitch").strip().lower()
    return mode if mode in {"stitch", "multi"} else "stitch"


def checked(value):
    return str(value or "").strip().lower() in {"1", "true", "on", "yes"}


def valid_video_resolution(value):
    resolution = (value or "720p").strip()
    return resolution if resolution in {"480p", "720p"} else "720p"


def valid_video_model(value, cfg=None):
    fallback = (cfg or config())["video_model"]
    model = (value or fallback).strip()
    if model in {"grok-imagine-video", "grok-imagine-video-1.5-preview"}:
        return model
    return fallback


def video_model_single_reference_only(model):
    return "1.5" in (model or "")


def valid_duration(value):
    try:
        return max(2, min(15, int(value or 6)))
    except (TypeError, ValueError):
        return 6


def valid_connect_time(value):
    if value in (None, ""):
        return None
    try:
        parsed = round(float(value), 1)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def read_metadata():
    try:
        data = json.loads(meta_path().read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, FileNotFoundError):
        return []


def normalize_metadata_item(item):
    if isinstance(item, dict) and "favorite" not in item:
        item["favorite"] = False
    return item


def scanned_library_items():
    metadata = []
    for item in read_metadata():
        if not isinstance(item, dict):
            continue
        rel = item.get("file_path")
        if not rel:
            continue
        if resolve_public_media_path(rel):
            metadata.append(normalize_metadata_item(item))
    known_paths = {item.get("file_path") for item in metadata}
    scanned = []
    roots = [
        ("image", "image", {".png", ".jpg", ".jpeg", ".webp", ".svg"}),
        ("video", "video", {".mp4", ".webm", ".mov"}),
        ("manga_trans", "edit", {".png", ".jpg", ".jpeg", ".webp", ".svg"}),
    ]
    for folder, kind, extensions in roots:
        directory = media_path(folder)
        if not directory.exists():
            continue
        for path in sorted(directory.rglob("*"), key=lambda item: item.stat().st_mtime, reverse=True):
            if not path.is_file() or path.suffix.lower() not in extensions:
                continue
            rel = public_path(path)
            if rel in known_paths:
                continue
            scanned.append({
                "id": "scan-" + hashlib.sha1(str(path.resolve()).encode("utf-8")).hexdigest(),
                "kind": kind,
                "prompt": "(저장 경로에서 발견된 파일)",
                "created_at": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(),
                "model": "scanned",
                "file_path": rel,
                "source_path": None,
                "favorite": False,
                "extra": {"scanned": True},
            })
    return sorted(metadata + scanned, key=lambda item: item.get("created_at") or "", reverse=True)


def video_thumbnail_public_path(rel):
    target = resolve_public_media_path(rel, {".mp4", ".webm", ".mov"})
    stat = target.stat()
    digest = hashlib.sha1(f"{target.resolve()}:{stat.st_mtime_ns}:{stat.st_size}".encode("utf-8")).hexdigest()
    dest = media_path("thumbnails", f"{digest}.jpg")
    if dest.exists() and dest.stat().st_size > 0:
        return public_path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg = ffmpeg_executable()
    if ffmpeg:
        for timestamp in ("1", "0.05"):
            completed = subprocess.run(
                [
                    ffmpeg,
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-ss",
                    timestamp,
                    "-i",
                    str(target),
                    "-frames:v",
                    "1",
                    "-vf",
                    "scale='min(640,iw)':-2",
                    "-q:v",
                    "4",
                    "-y",
                    str(dest),
                ],
                capture_output=True,
                text=True,
                timeout=60,
            )
            if completed.returncode == 0 and dest.exists() and dest.stat().st_size > 0:
                return public_path(dest)
    try:
        import cv2

        capture = cv2.VideoCapture(str(target))
        if not capture.isOpened():
            raise RuntimeError("video open failed")
        fps = float(capture.get(cv2.CAP_PROP_FPS) or 0)
        if fps > 0:
            capture.set(cv2.CAP_PROP_POS_FRAMES, max(0, int(fps)))
        ok, frame = capture.read()
        capture.release()
        if ok and cv2.imwrite(str(dest), frame):
            return public_path(dest)
    except Exception:
        pass
    raise RuntimeError("영상 썸네일을 생성할 수 없습니다.")


def backup_metadata_file():
    source = meta_path()
    if not source.exists() or source.stat().st_size == 0:
        return
    backup_dir = metadata_backup_dir()
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H")
    target = backup_dir / f"metadata-{stamp}.json"
    if not target.exists():
        shutil.copy2(source, target)


def write_metadata(items):
    target = meta_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    backup_metadata_file()
    normalized = [normalize_metadata_item(item) for item in items if isinstance(item, dict)]
    temp = target.with_name(f"{target.name}.tmp")
    temp.write_text(json.dumps(normalized, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(target)


PROMPT_TASKS = {
    "image": "이미지 생성",
    "edit": "이미지 편집",
    "video": "이미지→영상",
    "extend": "공식 연장",
    "frame": "프레임 연장",
    "manga": "망가 실사화·역식",
    "general": "범용",
}
PROMPT_STRUCTURED_FIELDS = ("subject", "scene", "style", "lighting", "camera", "keep", "change", "negative", "extra")
VIDEO_TEMPLATE_METHODS = {
    "i2v": "이미지→영상",
    "frame": "프레임 연장",
    "official": "공식 연장",
    "image": "이미지 생성",
    "edit": "이미지 편집",
}
VIDEO_TEMPLATE_TRANSITIONS = {"cut", "fade", "crossfade", "fade_in", "fade_out"}


def clean_template_key(value, fallback="var"):
    key = re.sub(r"[^a-zA-Z0-9_]+", "_", str(value or "").strip()).strip("_").lower()
    return (key or fallback)[:48]


def clean_prompt_tag(tag):
    tag = re.sub(r"\s+", " ", str(tag or "")).strip()
    return tag[:32]


def normalize_prompt_tags(value):
    if isinstance(value, str):
        raw = re.split(r"[,#\n]", value)
    elif isinstance(value, list):
        raw = value
    else:
        raw = []
    tags = []
    seen = set()
    for item in raw:
        tag = clean_prompt_tag(item)
        key = tag.lower()
        if tag and key not in seen:
            seen.add(key)
            tags.append(tag)
    return tags[:20]


def normalize_prompt_structure(value):
    if not isinstance(value, dict):
        return {}
    structured = {}
    for key in PROMPT_STRUCTURED_FIELDS:
        text = str(value.get(key) or "").strip()
        if text:
            structured[key] = text[:4000]
    return structured


def normalize_prompt_item(item):
    item = dict(item or {})
    prompt = str(item.get("prompt") or "").strip()
    structured = normalize_prompt_structure(item.get("structured"))
    title = str(item.get("title") or "").strip()[:160]
    if not title:
        title = (prompt[:48] + "…") if len(prompt) > 48 else (prompt or "새 프롬프트")
    task = str(item.get("task") or "general").strip()
    if task not in PROMPT_TASKS:
        task = "general"
    created_at = item.get("created_at") or datetime.now(timezone.utc).isoformat()
    updated_at = item.get("updated_at") or created_at
    versions = item.get("versions") if isinstance(item.get("versions"), list) else []
    normalized_versions = []
    for version in versions[-30:]:
        if not isinstance(version, dict):
            continue
        normalized_versions.append({
            "at": version.get("at") or updated_at,
            "title": str(version.get("title") or title)[:160],
            "prompt": str(version.get("prompt") or "")[:20000],
            "structured": normalize_prompt_structure(version.get("structured")),
            "tags": normalize_prompt_tags(version.get("tags")),
        })
    return {
        "id": str(item.get("id") or uuid.uuid4().hex),
        "title": title,
        "task": task,
        "task_label": PROMPT_TASKS[task],
        "prompt": prompt[:20000],
        "structured": structured,
        "tags": normalize_prompt_tags(item.get("tags")),
        "favorite": bool(item.get("favorite")),
        "created_at": created_at,
        "updated_at": updated_at,
        "usage_count": int(item.get("usage_count") or 0),
        "last_used_at": item.get("last_used_at"),
        "source_item_id": item.get("source_item_id"),
        "source_file_path": item.get("source_file_path"),
        "versions": normalized_versions,
    }


def read_prompts():
    try:
        data = json.loads(prompts_path().read_text(encoding="utf-8"))
    except (json.JSONDecodeError, FileNotFoundError):
        data = []
    if not isinstance(data, list):
        data = []
    return [normalize_prompt_item(item) for item in data if isinstance(item, dict)]


def write_prompts(items):
    target = prompts_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    normalized = [normalize_prompt_item(item) for item in items if isinstance(item, dict)]
    temp = target.with_name(f"{target.name}.tmp")
    temp.write_text(json.dumps(normalized, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(target)


def prompt_item_response(item):
    normalized = normalize_prompt_item(item)
    normalized["version_count"] = len(normalized.get("versions") or [])
    return normalized


def normalize_template_variables(value):
    raw = value if isinstance(value, list) else []
    variables = []
    seen = set()
    for index, item in enumerate(raw, start=1):
        if isinstance(item, dict):
            key = clean_template_key(item.get("key"), f"var_{index}")
            label = str(item.get("label") or key).strip()[:80]
            default = str(item.get("default") if item.get("default") is not None else item.get("value") or "").strip()[:1000]
        else:
            key = clean_template_key(item, f"var_{index}")
            label = key
            default = ""
        if key in seen:
            continue
        seen.add(key)
        variables.append({"key": key, "label": label or key, "default": default})
    return variables[:40]


def normalize_template_slots(value):
    raw = value if isinstance(value, list) else []
    slots = []
    seen = set()
    for index, item in enumerate(raw, start=1):
        if isinstance(item, dict):
            key = clean_template_key(item.get("key"), f"slot_{index}")
            label = str(item.get("label") or key).strip()[:80]
            kind = str(item.get("kind") or "image").strip().lower()
            note = str(item.get("note") or "").strip()[:1000]
        else:
            key = clean_template_key(item, f"slot_{index}")
            label = key
            kind = "image"
            note = ""
        if kind not in {"image", "video", "text"}:
            kind = "image"
        if key in seen:
            continue
        seen.add(key)
        slots.append({"key": key, "label": label or key, "kind": kind, "note": note})
    return slots[:24]


def normalize_template_shots(value):
    raw = value if isinstance(value, list) else []
    shots = []
    for index, item in enumerate(raw, start=1):
        if not isinstance(item, dict):
            continue
        method = str(item.get("method") or "i2v").strip()
        if method not in VIDEO_TEMPLATE_METHODS:
            method = "i2v"
        transition = str(item.get("transition") or "cut").strip()
        if transition not in VIDEO_TEMPLATE_TRANSITIONS:
            transition = "cut"
        try:
            duration = float(item.get("duration") or 6)
        except (TypeError, ValueError):
            duration = 6
        duration = max(1, min(15, duration))
        shots.append({
            "id": str(item.get("id") or uuid.uuid4().hex),
            "order": index,
            "title": str(item.get("title") or f"컷 {index:02d}").strip()[:120],
            "method": method,
            "method_label": VIDEO_TEMPLATE_METHODS[method],
            "duration": duration,
            "reference_slot": clean_template_key(item.get("reference_slot"), ""),
            "prompt": str(item.get("prompt") or "").strip()[:12000],
            "camera": str(item.get("camera") or "").strip()[:2000],
            "transition": transition,
            "retry_prompt": str(item.get("retry_prompt") or "").strip()[:6000],
            "notes": str(item.get("notes") or "").strip()[:4000],
        })
    return shots[:240]


def normalize_video_template(item):
    item = dict(item or {})
    now = datetime.now(timezone.utc).isoformat()
    settings = item.get("settings") if isinstance(item.get("settings"), dict) else {}
    title = str(item.get("title") or "").strip()[:160]
    if not title:
        title = "새 영상 템플릿"
    aspect_ratio = valid_aspect_ratio(settings.get("aspect_ratio") or item.get("aspect_ratio") or "9:16", allow_source=True)
    resolution = str(settings.get("resolution") or item.get("resolution") or "720p").strip()
    if resolution not in {"480p", "720p"}:
        resolution = "720p"
    default_method = str(settings.get("default_method") or item.get("default_method") or "i2v").strip()
    if default_method not in VIDEO_TEMPLATE_METHODS:
        default_method = "i2v"
    variables = normalize_template_variables(item.get("variables"))
    slots = normalize_template_slots(item.get("slots"))
    shots = normalize_template_shots(item.get("shots"))
    total_duration = sum(float(shot.get("duration") or 0) for shot in shots)
    request_count = len(shots)
    try:
        target_duration = int(float(settings.get("target_duration") or item.get("target_duration") or max(total_duration, 60)))
    except (TypeError, ValueError):
        target_duration = int(max(total_duration, 60))
    try:
        default_shot_duration = float(settings.get("default_shot_duration") or item.get("default_shot_duration") or 6)
    except (TypeError, ValueError):
        default_shot_duration = 6
    return {
        "id": str(item.get("id") or uuid.uuid4().hex),
        "title": title,
        "description": str(item.get("description") or "").strip()[:3000],
        "genre": str(item.get("genre") or "").strip()[:80],
        "tags": normalize_prompt_tags(item.get("tags")),
        "favorite": bool(item.get("favorite")),
        "global_prompt": str(item.get("global_prompt") or "").strip()[:20000],
        "negative_prompt": str(item.get("negative_prompt") or "").strip()[:12000],
        "variables": variables,
        "slots": slots,
        "shots": shots,
        "settings": {
            "target_duration": max(1, target_duration),
            "aspect_ratio": aspect_ratio,
            "resolution": resolution,
            "default_method": default_method,
            "default_shot_duration": max(1, min(15, default_shot_duration)),
        },
        "stats": {
            "shot_count": len(shots),
            "total_duration": round(total_duration, 2),
            "request_count": request_count,
        },
        "created_at": item.get("created_at") or now,
        "updated_at": item.get("updated_at") or item.get("created_at") or now,
    }


def read_video_templates():
    try:
        data = json.loads(video_templates_path().read_text(encoding="utf-8"))
    except (json.JSONDecodeError, FileNotFoundError):
        data = []
    if not isinstance(data, list):
        data = []
    return [normalize_video_template(item) for item in data if isinstance(item, dict)]


def write_video_templates(items):
    target = video_templates_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    normalized = [normalize_video_template(item) for item in items if isinstance(item, dict)]
    temp = target.with_name(f"{target.name}.tmp")
    temp.write_text(json.dumps(normalized, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(target)


def video_template_response(item):
    return normalize_video_template(item)


def normalize_template_block(item):
    item = dict(item or {})
    now = datetime.now(timezone.utc).isoformat()
    source_shot_id = str(item.get("source_shot_id") or item.get("shot_id") or "").strip()
    shot_items = normalize_template_shots([{
        "id": source_shot_id,
        "title": item.get("title") or item.get("name"),
        "method": item.get("method"),
        "duration": item.get("duration"),
        "reference_slot": item.get("reference_slot"),
        "prompt": item.get("prompt"),
        "camera": item.get("camera"),
        "transition": item.get("transition"),
        "retry_prompt": item.get("retry_prompt"),
        "notes": item.get("notes"),
    }])
    shot = shot_items[0] if shot_items else normalize_template_shots([{}])[0]
    block_id = str(item.get("id") or uuid.uuid4().hex)
    created_at = item.get("created_at") or now
    updated_at = item.get("updated_at") or created_at
    source_template_id = str(item.get("source_template_id") or "").strip()[:120]
    source_template_title = str(item.get("source_template_title") or "").strip()[:160]
    return {
        "id": block_id,
        "title": shot.get("title") or "컷 블록",
        "method": shot.get("method") or "i2v",
        "method_label": VIDEO_TEMPLATE_METHODS.get(shot.get("method"), "이미지→영상"),
        "duration": shot.get("duration") or 6,
        "reference_slot": shot.get("reference_slot") or "",
        "prompt": shot.get("prompt") or "",
        "camera": shot.get("camera") or "",
        "transition": shot.get("transition") or "cut",
        "retry_prompt": shot.get("retry_prompt") or "",
        "notes": shot.get("notes") or "",
        "tags": normalize_prompt_tags(item.get("tags")),
        "favorite": bool(item.get("favorite")),
        "source_template_id": source_template_id,
        "source_template_title": source_template_title,
        "source_shot_id": source_shot_id,
        "created_at": created_at,
        "updated_at": updated_at,
    }


def read_template_blocks():
    try:
        data = json.loads(video_template_blocks_path().read_text(encoding="utf-8"))
    except (json.JSONDecodeError, FileNotFoundError):
        data = []
    if not isinstance(data, list):
        data = []
    return [normalize_template_block(item) for item in data if isinstance(item, dict)]


def write_template_blocks(items):
    target = video_template_blocks_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    normalized = [normalize_template_block(item) for item in items if isinstance(item, dict)]
    temp = target.with_name(f"{target.name}.tmp")
    temp.write_text(json.dumps(normalized, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(target)


def template_block_response(item):
    return normalize_template_block(item)


def read_usage():
    try:
        return json.loads(usage_path().read_text(encoding="utf-8"))
    except (json.JSONDecodeError, FileNotFoundError):
        return {"requests": 0, "tokens": 0, "cost_usd": 0, "last_usage": None}


def record_usage(usage):
    if not usage:
        return
    current = read_usage()
    total_tokens = int(usage.get("total_tokens") or usage.get("input_tokens") or 0)
    cost_ticks = int(usage.get("cost_in_usd_ticks") or 0)
    current["requests"] = int(current.get("requests") or 0) + 1
    current["tokens"] = int(current.get("tokens") or 0) + total_tokens
    current["cost_usd"] = round(float(current.get("cost_usd") or 0) + (cost_ticks / 10_000_000_000), 8)
    current["last_usage"] = usage
    usage_path().write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")


def read_oauth_token():
    try:
        return json.loads(oauth_token_path().read_text(encoding="utf-8"))
    except (json.JSONDecodeError, FileNotFoundError):
        return None


def write_oauth_token(token):
    expires_in = int(token.get("expires_in") or 3600)
    token["expires_at"] = int(time.time()) + expires_in
    oauth_token_path().write_text(json.dumps(token, ensure_ascii=False, indent=2), encoding="utf-8")


def clear_oauth_token():
    token_path = oauth_token_path()
    if token_path.exists():
        token_path.unlink()


def hermes_exe_candidates():
    exe_name = "hermes.exe" if os.name == "nt" else "hermes"
    candidates = []
    for env_name in ("WEBGORK_HERMES_EXE", "HERMES_EXE"):
        value = os.getenv(env_name)
        if value:
            candidates.append(Path(value).expanduser())
    candidates.extend([
        ROOT / ".hermes-venv" / "Scripts" / exe_name,
        ROOT / ".hermes-venv" / "bin" / exe_name,
        ROOT / "vendor" / "hermes-agent" / "venv" / "Scripts" / exe_name,
        ROOT / "vendor" / "hermes-agent" / "venv" / "bin" / exe_name,
    ])
    sibling_names = [
        ROOT.name.replace("-Version-3", "-Version-2"),
        ROOT.name.replace("-Version-3", ""),
    ]
    for name in dict.fromkeys(sibling_names):
        if not name or name == ROOT.name:
            continue
        sibling = ROOT.parent / name
        candidates.extend([
            sibling / ".hermes-venv" / "Scripts" / exe_name,
            sibling / ".hermes-venv" / "bin" / exe_name,
            sibling / "vendor" / "hermes-agent" / "venv" / "Scripts" / exe_name,
            sibling / "vendor" / "hermes-agent" / "venv" / "bin" / exe_name,
        ])
    discovered = shutil.which("hermes")
    if discovered:
        candidates.append(Path(discovered))
    return candidates


def hermes_exe_path():
    for candidate in hermes_exe_candidates():
        if candidate and candidate.exists():
            return candidate.resolve()
    return ROOT / ".hermes-venv" / "Scripts" / ("hermes.exe" if os.name == "nt" else "hermes")


def hermes_auth_path():
    return Path.home() / ".hermes" / "auth.json"


def hermes_xai_oauth_credentials():
    try:
        data = json.loads(hermes_auth_path().read_text(encoding="utf-8"))
    except (json.JSONDecodeError, FileNotFoundError):
        return []
    credentials = data.get("credential_pool", {}).get("xai-oauth") or []
    if not isinstance(credentials, list):
        return []
    return [item for item in credentials if isinstance(item, dict) and item.get("access_token")]


def hermes_xai_oauth_token():
    credentials = hermes_xai_oauth_credentials()
    if not credentials:
        return None
    preferred = [item for item in credentials if item.get("last_status") == "ok"]
    return (preferred or credentials)[0].get("access_token")


def hidden_process_kwargs():
    if os.name == "nt":
        return {"creationflags": subprocess.CREATE_NO_WINDOW}
    return {}


def hermes_auth_logged_in():
    exe = hermes_exe_path()
    if not exe.exists():
        return False, "Hermes 실행 파일을 찾을 수 없습니다."
    try:
        result = subprocess.run(
            [str(exe), "auth", "status", "xai-oauth"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=20,
            **hidden_process_kwargs(),
        )
    except Exception as exc:
        return False, str(exc)
    output = (result.stdout or "") + (result.stderr or "")
    return "logged out" not in output.lower(), output.strip()


def stop_tracked_hermes_proxy():
    global HERMES_PROXY_PROCESS
    process = HERMES_PROXY_PROCESS
    HERMES_PROXY_PROCESS = None
    if not process or process.poll() is not None:
        return False
    try:
        process.terminate()
        process.wait(timeout=5)
    except Exception:
        try:
            process.kill()
        except Exception:
            pass
    return True


def reset_hermes_login_state():
    with HERMES_LOGIN_LOCK:
        process = HERMES_LOGIN_STATE.get("process")
        if process and process.poll() is None:
            try:
                process.terminate()
            except Exception:
                pass
        HERMES_LOGIN_STATE["process"] = None
        HERMES_LOGIN_STATE["auth_url"] = ""
        HERMES_LOGIN_STATE["lines"] = []
        HERMES_LOGIN_STATE["started_at"] = None


def hermes_auth_logout_state():
    exe = hermes_exe_path()
    if not exe.exists():
        raise RuntimeError("Hermes 실행 파일을 찾을 수 없습니다.")
    reset_hermes_login_state()
    stopped_proxy = stop_tracked_hermes_proxy()
    result = subprocess.run(
        [str(exe), "auth", "logout", "xai-oauth"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
        **hidden_process_kwargs(),
    )
    output = ((result.stdout or "") + (result.stderr or "")).strip()
    if result.returncode != 0:
        raise RuntimeError(output or f"Hermes 로그아웃 명령이 실패했습니다. exit={result.returncode}")
    logged_in, detail = hermes_auth_logged_in()
    return {
        "logged_in": logged_in,
        "status": detail or output,
        "logout_output": output,
        "tracked_proxy_stopped": stopped_proxy,
        "proxy_running": port_open("127.0.0.1", 8645),
    }


def hermes_auth_reset_state():
    exe = hermes_exe_path()
    if not exe.exists():
        raise RuntimeError("Hermes 실행 파일을 찾을 수 없습니다.")
    reset_hermes_login_state()
    result = subprocess.run(
        [str(exe), "auth", "reset", "xai-oauth"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
        **hidden_process_kwargs(),
    )
    output = ((result.stdout or "") + (result.stderr or "")).strip()
    if result.returncode != 0:
        raise RuntimeError(output or f"Hermes 인증 상태 리셋 명령이 실패했습니다. exit={result.returncode}")
    logged_in, detail = hermes_auth_logged_in()
    proxy_started = False
    proxy_message = ""
    if logged_in:
        proxy_started, proxy_message = ensure_hermes_proxy_background()
    return {
        "logged_in": logged_in,
        "status": detail or output,
        "reset_output": output,
        "proxy_started": proxy_started,
        "proxy_message": proxy_message,
        "proxy_running": port_open("127.0.0.1", 8645),
    }


def port_open(host="127.0.0.1", port=8645):
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except OSError:
        return False


def ensure_hermes_proxy_background():
    global HERMES_PROXY_PROCESS
    if port_open("127.0.0.1", 8645):
        return True, "Hermes Proxy가 이미 실행 중입니다."
    exe = hermes_exe_path()
    if not exe.exists():
        return False, "Hermes 실행 파일을 찾을 수 없습니다."
    if HERMES_PROXY_PROCESS and HERMES_PROXY_PROCESS.poll() is None:
        return True, "Hermes Proxy 시작 대기 중입니다."
    try:
        HERMES_PROXY_PROCESS = subprocess.Popen(
            [str(exe), "proxy", "start", "--provider", "xai", "--host", "127.0.0.1", "--port", "8645"],
            cwd=str(ROOT),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            **hidden_process_kwargs(),
        )
    except Exception as exc:
        return False, str(exc)
    for _ in range(20):
        if port_open("127.0.0.1", 8645):
            return True, "Hermes Proxy가 실행되었습니다."
        time.sleep(0.25)
    return True, "Hermes Proxy를 백그라운드에서 시작했습니다."


def read_hermes_login_output(process):
    auth_url_re = re.compile(r"https?://\S+")
    for raw_line in iter(process.stdout.readline, ""):
        line = raw_line.rstrip()
        with HERMES_LOGIN_LOCK:
            HERMES_LOGIN_STATE["lines"].append(line)
            match = auth_url_re.search(line)
            if match and not HERMES_LOGIN_STATE.get("auth_url"):
                HERMES_LOGIN_STATE["auth_url"] = match.group(0)
            HERMES_LOGIN_STATE["lines"] = HERMES_LOGIN_STATE["lines"][-80:]


def hermes_login_snapshot():
    with HERMES_LOGIN_LOCK:
        process = HERMES_LOGIN_STATE.get("process")
        running = bool(process and process.poll() is None)
        return {
            "running": running,
            "auth_url": HERMES_LOGIN_STATE.get("auth_url") or "",
            "lines": list(HERMES_LOGIN_STATE.get("lines") or [])[-20:],
            "started_at": HERMES_LOGIN_STATE.get("started_at"),
        }


def oauth_discovery():
    cfg = config()
    try:
        response = requests.get(cfg["oauth_issuer"] + "/.well-known/openid-configuration", timeout=20)
        response.raise_for_status()
        return response.json()
    except requests.RequestException:
        return {
            "authorization_endpoint": cfg["oauth_issuer"] + "/oauth2/authorize",
            "token_endpoint": cfg["oauth_issuer"] + "/oauth2/token",
            "userinfo_endpoint": cfg["oauth_issuer"] + "/oauth2/userinfo",
        }


def pkce_pair():
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(64)).decode("ascii").rstrip("=")
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return verifier, challenge


def oauth_access_token():
    token = read_oauth_token()
    if not token:
        return None
    if int(token.get("expires_at") or 0) - 120 > int(time.time()):
        return token.get("access_token")
    refresh_token = token.get("refresh_token")
    if not refresh_token:
        return token.get("access_token")
    cfg = config()
    endpoints = oauth_discovery()
    response = requests.post(
        endpoints["token_endpoint"],
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": cfg["oauth_client_id"],
        },
        timeout=30,
    )
    response.raise_for_status()
    refreshed = response.json()
    if "refresh_token" not in refreshed:
        refreshed["refresh_token"] = refresh_token
    write_oauth_token(refreshed)
    return refreshed.get("access_token")


def oauth_exchange_code(code, verifier, redirect_uri):
    cfg = config()
    endpoints = oauth_discovery()
    response = requests.post(
        endpoints["token_endpoint"],
        data={
            "grant_type": "authorization_code",
            "code": code,
            "client_id": cfg["oauth_client_id"],
            "redirect_uri": redirect_uri,
            "code_verifier": verifier,
        },
        timeout=30,
    )
    response.raise_for_status()
    write_oauth_token(response.json())


class XaiOAuthCallbackHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        return

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path != "/callback":
            self.send_response(404)
            self.end_headers()
            return
        params = parse_qs(parsed.query)
        state = (params.get("state") or [""])[0]
        error = (params.get("error") or [""])[0]
        code = (params.get("code") or [""])[0]
        pending = OAUTH_PENDING.get(state)
        ok = False
        if error:
            message = f"OAuth 오류: {error}"
        elif not code or not pending:
            message = "OAuth state 검증에 실패했습니다. WebGUI.v3에서 다시 로그인해 주세요."
        else:
            try:
                oauth_exchange_code(code, pending["verifier"], pending["redirect_uri"])
                OAUTH_PENDING.pop(state, None)
                ok = True
                message = "Grok OAuth 로그인이 완료되었습니다. 이 창을 닫고 WebGUI.v3으로 돌아가세요."
            except Exception as exc:
                message = f"토큰 교환 실패: {exc}"
        body = f"""<!doctype html>
<html lang="ko">
<head><meta charset="utf-8"><title>Grok OAuth</title></head>
<body style="font-family:Arial,sans-serif;background:#101413;color:#f7f4ea;padding:40px">
<h1>{'로그인 완료' if ok else '로그인 실패'}</h1>
<p>{html.escape(message)}</p>
<p><a style="color:#5bc0be" href="http://127.0.0.1:7863">WebGUI.v3으로 돌아가기</a></p>
</body></html>"""
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body.encode("utf-8"))))
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))


def ensure_oauth_callback_server():
    global OAUTH_CALLBACK_SERVER
    if OAUTH_CALLBACK_SERVER:
        return
    OAUTH_CALLBACK_SERVER = ThreadingHTTPServer(("127.0.0.1", 56121), XaiOAuthCallbackHandler)
    thread = Thread(target=OAUTH_CALLBACK_SERVER.serve_forever, daemon=True)
    thread.start()


def add_metadata(kind, prompt, model, path, source_path=None, extra=None):
    if not path or not Path(path).exists():
        raise FileNotFoundError(f"결과 파일을 찾을 수 없습니다: {path}")
    item = {
        "id": uuid.uuid4().hex,
        "kind": kind,
        "prompt": prompt,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "model": model,
        "file_path": public_path(path),
        "source_path": public_path(source_path) if source_path else None,
        "favorite": False,
        "extra": extra or {},
    }
    items = read_metadata()
    items.insert(0, item)
    write_metadata(items)
    return item


def resolve_public_media_path(rel, allowed_suffixes=None):
    if not rel:
        return None
    rel = str(rel)
    if rel.startswith("/media-library/"):
        target = (media_root() / rel.replace("/media-library/", "", 1).lstrip("/")).resolve()
        root = media_root().resolve()
    else:
        target = (ROOT / rel.lstrip("/")).resolve()
        root = ROOT.resolve()
    if not ((target == root or root in target.parents) and target.exists() and target.is_file()):
        return None
    if allowed_suffixes and target.suffix.lower() not in allowed_suffixes:
        return None
    return target


def local_media_path_from_public(rel):
    target = resolve_public_media_path(rel)
    if not target:
        raise ValueError("파일을 찾을 수 없습니다.")
    return target


def find_library_item_by_id(item_id):
    if not item_id:
        return None
    for item in scanned_library_items():
        if item.get("id") == item_id:
            return item
    return None


def parse_request_bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def register_uploaded_image_source(path, used_for, original_name=None):
    return add_metadata(
        "image",
        f"Reference image for {used_for}: {original_name or Path(path).name}",
        "upload",
        path,
        extra={"origin": "upload", "used_for": used_for, "original_name": original_name},
    )


def file_sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def find_existing_image_by_bytes(blob):
    if not blob:
        return None, None
    target_hash = hashlib.sha256(blob).hexdigest()
    allowed = {".jpg", ".jpeg", ".png", ".webp"}
    for folder in (media_path("image"), media_path("uploads")):
        if not folder.exists():
            continue
        for path in folder.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in allowed:
                continue
            try:
                if path.stat().st_size == len(blob) and file_sha256(path) == target_hash:
                    return path, find_metadata_by_file_path(path)
            except OSError:
                continue
    return None, None


def read_uploaded_bytes(uploaded):
    blob = uploaded.stream.read()
    uploaded.stream.seek(0)
    return blob


def find_metadata_by_file_path(path):
    rel = public_path(path)
    for item in read_metadata():
        if item.get("file_path") == rel:
            return item
    return None


def i2v_reference_context(source_video):
    item = find_metadata_by_file_path(source_video)
    if not item:
        return None
    extra = item.get("extra") or {}
    start_image_rel = (
        extra.get("start_image_path")
        or extra.get("original_start_image_path")
        or (item.get("source_path") if extra.get("generation_type") == "i2v" else None)
    )
    start_image = resolve_public_media_path(start_image_rel, {".jpg", ".jpeg", ".png", ".webp", ".svg"})
    if not start_image:
        return None
    return {
        "source_item": item,
        "start_image": start_image,
        "start_image_path": public_path(start_image),
        "i2v_prompt": extra.get("i2v_prompt") or item.get("prompt"),
    }


def source_video_remote_url(source_video):
    item = find_metadata_by_file_path(source_video)
    if not item:
        return None
    extra = item.get("extra") or {}
    url = extra.get("remote_url")
    if isinstance(url, str) and url.startswith(("http://", "https://")):
        return url
    return None


def save_upload(field_name, folder="uploads", filename_note=None):
    uploaded = request.files.get(field_name)
    if not uploaded or not uploaded.filename:
        raise ValueError("이미지 파일을 업로드해 주세요.")
    filename = secure_filename(uploaded.filename) or "upload"
    suffix = Path(filename).suffix.lower()
    if suffix not in {".jpg", ".jpeg", ".png", ".webp"}:
        raise ValueError("jpg, png, webp 이미지만 업로드할 수 있습니다.")
    ensure_media_dirs()
    note = f"-{filename_note}" if filename_note else ""
    dest = media_path(folder, f"{now_stamp()}-{uuid.uuid4().hex}{note}{suffix}")
    uploaded.save(dest)
    return dest


def save_reference_image_or_library(field_name, used_for):
    library_image = resolve_library_image()
    if library_image:
        return library_image, None, True
    uploaded = request.files.get(field_name)
    original_name = uploaded.filename if uploaded and uploaded.filename else None
    if uploaded and uploaded.filename:
        blob = read_uploaded_bytes(uploaded)
        existing, existing_item = find_existing_image_by_bytes(blob)
        if existing:
            return existing, existing_item, False
    source = save_upload(field_name, folder="image", filename_note="reference")
    item = register_uploaded_image_source(source, used_for, original_name=original_name)
    return source, item, False


def save_video_upload(field_name):
    uploaded = request.files.get(field_name)
    if not uploaded or not uploaded.filename:
        raise ValueError("영상 파일을 업로드하거나 라이브러리에서 선택해 주세요.")
    filename = secure_filename(uploaded.filename) or "upload"
    suffix = Path(filename).suffix.lower()
    if suffix not in {".mp4", ".webm", ".mov"}:
        raise ValueError("mp4, webm, mov 영상만 업로드할 수 있습니다.")
    ensure_media_dirs()
    dest = media_path("uploads", f"{now_stamp()}-{uuid.uuid4().hex}{suffix}")
    uploaded.save(dest)
    return dest


def save_uploaded_frame(field_name):
    uploaded = request.files.get(field_name)
    if not uploaded or not uploaded.filename:
        return None
    filename = secure_filename(uploaded.filename) or "last-frame.png"
    suffix = Path(filename).suffix.lower()
    if suffix not in {".jpg", ".jpeg", ".png", ".webp"}:
        suffix = ".png"
    ensure_media_dirs()
    dest = media_path("image", f"{now_stamp()}-{uuid.uuid4().hex}-browser-frame{suffix}")
    uploaded.save(dest)
    return dest


def resolve_library_image():
    rel = (request.form.get("library_image_path") or "").strip()
    if not rel:
        return None
    if not rel.startswith("/media-library/"):
        raise ValueError("라이브러리 이미지 경로가 올바르지 않습니다.")
    target = (media_root() / rel.replace("/media-library/", "", 1).lstrip("/")).resolve()
    root = media_root().resolve()
    if not ((target == root or root in target.parents) and target.exists() and target.is_file()):
        raise ValueError("선택한 라이브러리 이미지를 찾을 수 없습니다.")
    if target.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp", ".svg"}:
        raise ValueError("선택한 파일은 이미지가 아닙니다.")
    return target


def resolve_library_image_path(rel):
    rel = (rel or "").strip()
    if not rel:
        return None
    if not rel.startswith("/media-library/"):
        raise ValueError("라이브러리 이미지 경로가 올바르지 않습니다.")
    target = (media_root() / rel.replace("/media-library/", "", 1).lstrip("/")).resolve()
    root = media_root().resolve()
    if not ((target == root or root in target.parents) and target.exists() and target.is_file()):
        raise ValueError("선택한 라이브러리 이미지를 찾을 수 없습니다.")
    if target.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp", ".svg"}:
        raise ValueError("선택한 파일은 이미지가 아닙니다.")
    return target


def save_reference_images_or_library(field_name, used_for, limit=3):
    sources = []
    source_items = []
    uploaded_files = iter(request.files.getlist(field_name))

    def save_uploaded_reference(uploaded):
        if not uploaded or not uploaded.filename:
            return None, None
        filename = secure_filename(uploaded.filename) or "upload"
        suffix = Path(filename).suffix.lower()
        if suffix not in {".jpg", ".jpeg", ".png", ".webp"}:
            raise ValueError("jpg, png, webp 이미지만 업로드할 수 있습니다.")
        ensure_media_dirs()
        blob = read_uploaded_bytes(uploaded)
        existing, existing_item = find_existing_image_by_bytes(blob)
        if existing:
            return existing, existing_item
        dest = media_path("image", f"{now_stamp()}-{uuid.uuid4().hex}-reference{suffix}")
        dest.write_bytes(blob)
        item = register_uploaded_image_source(dest, used_for, original_name=uploaded.filename)
        return dest, item

    order = request.form.getlist("image_source_order")
    if order:
        for marker in order:
            if len(sources) >= limit:
                break
            if marker == "file":
                source, item = save_uploaded_reference(next(uploaded_files, None))
                if source:
                    sources.append(source)
                    source_items.append(item)
            elif marker.startswith("library:"):
                library_image = resolve_library_image_path(marker.replace("library:", "", 1))
                if library_image:
                    sources.append(library_image)
                    source_items.append(None)
    else:
        for rel in request.form.getlist("library_image_paths"):
            if len(sources) >= limit:
                break
            library_image = resolve_library_image_path(rel)
            if library_image:
                sources.append(library_image)
                source_items.append(None)
        for uploaded in request.files.getlist(field_name):
            if len(sources) >= limit:
                break
            source, item = save_uploaded_reference(uploaded)
            if source:
                sources.append(source)
                source_items.append(item)
    if not sources:
        raise ValueError("이미지를 업로드하거나 라이브러리에서 선택해 주세요.")
    return sources, source_items


def stitched_reference_image(sources):
    if len(sources) <= 1:
        return sources[0]
    if any(source.suffix.lower() == ".svg" for source in sources):
        raise ValueError("여러 이미지를 합쳐 편집할 때는 jpg, png, webp 이미지만 사용할 수 있습니다. svg 이미지는 png로 변환해 주세요.")
    try:
        from PIL import Image, ImageOps
    except Exception as exc:
        raise RuntimeError("여러 이미지를 한 장으로 합치려면 Pillow 패키지가 필요합니다.") from exc

    opened = []
    try:
        for source in sources:
            image = Image.open(source)
            image = ImageOps.exif_transpose(image).convert("RGBA")
            opened.append(image)

        max_height = max(image.height for image in opened)
        target_height = min(max_height, 1280)
        gutter = 12
        resized = []
        for image in opened:
            scale = target_height / image.height
            width = max(1, int(image.width * scale))
            resized.append(image.resize((width, target_height), Image.LANCZOS))

        total_width = sum(image.width for image in resized) + gutter * (len(resized) - 1)
        if total_width > 4096:
            scale = 4096 / total_width
            target_height = max(1, int(target_height * scale))
            resized = [
                image.resize((max(1, int(image.width * scale)), target_height), Image.LANCZOS)
                for image in resized
            ]
            total_width = sum(image.width for image in resized) + gutter * (len(resized) - 1)

        canvas = Image.new("RGB", (total_width, target_height), (244, 244, 244))
        x = 0
        for image in resized:
            background = Image.new("RGBA", image.size, (244, 244, 244, 255))
            background.alpha_composite(image)
            canvas.paste(background.convert("RGB"), (x, 0))
            x += image.width + gutter

        ensure_media_dirs()
        dest = media_path("image", f"{now_stamp()}-{uuid.uuid4().hex}-stitched-reference.jpg")
        canvas.save(dest, format="JPEG", quality=92, optimize=True)
        return dest
    finally:
        for image in opened:
            try:
                image.close()
            except Exception:
                pass


def resolve_library_video():
    rel = (request.form.get("library_video_path") or "").strip()
    return resolve_library_video_path(rel)


def resolve_library_video_path(rel):
    rel = (rel or "").strip()
    if not rel:
        return None
    if not rel.startswith("/media-library/"):
        raise ValueError("라이브러리 영상 경로가 올바르지 않습니다.")
    target = (media_root() / rel.replace("/media-library/", "", 1).lstrip("/")).resolve()
    root = media_root().resolve()
    if not ((target == root or root in target.parents) and target.exists() and target.is_file()):
        raise ValueError("선택한 라이브러리 영상을 찾을 수 없습니다.")
    if target.suffix.lower() not in {".mp4", ".webm", ".mov"}:
        raise ValueError("선택한 파일은 영상이 아닙니다.")
    return target


def save_video_uploads_or_library_paths(field_name, limit=12):
    sources = []
    source_items = []
    source_order = request.form.getlist("video_source_order")

    def save_editor_upload(uploaded):
        if not uploaded or not uploaded.filename:
            return None, None
        filename = secure_filename(uploaded.filename) or "upload"
        suffix = Path(filename).suffix.lower()
        if suffix not in {".mp4", ".webm", ".mov"}:
            raise ValueError("mp4, webm, mov 영상만 업로드할 수 있습니다.")
        ensure_media_dirs()
        dest = media_path("uploads", f"{now_stamp()}-{uuid.uuid4().hex}{suffix}")
        uploaded.save(dest)
        item = add_metadata(
            "video",
            f"Uploaded video for editor: {uploaded.filename}",
            "upload",
            dest,
            extra={"origin": "upload", "used_for": "video-editor", "original_name": uploaded.filename},
        )
        return dest, item

    if source_order:
        uploads = iter(request.files.getlist(field_name))
        for token in source_order:
            if len(sources) >= limit:
                break
            token = str(token or "")
            if token == "file":
                source, item = save_editor_upload(next(uploads, None))
                if source:
                    sources.append(source)
                    source_items.append(item)
                continue
            if token.startswith("library:"):
                source = resolve_library_video_path(token.split("library:", 1)[1])
                if source:
                    sources.append(source)
                    source_items.append(find_metadata_by_file_path(source))
        if not sources:
            raise ValueError("편집할 영상을 업로드하거나 라이브러리에서 선택해 주세요.")
        return sources, source_items

    for rel in request.form.getlist("library_video_paths"):
        if len(sources) >= limit:
            break
        source = resolve_library_video_path(rel)
        if source:
            sources.append(source)
            source_items.append(find_metadata_by_file_path(source))
    for uploaded in request.files.getlist(field_name):
        if len(sources) >= limit:
            break
        if not uploaded or not uploaded.filename:
            continue
        source, item = save_editor_upload(uploaded)
        if source:
            sources.append(source)
            source_items.append(item)
    if not sources:
        raise ValueError("편집할 영상을 업로드하거나 라이브러리에서 선택해 주세요.")
    return sources, source_items


def save_upload_or_library(field_name):
    library_image = resolve_library_image()
    if library_image:
        return library_image
    return save_upload(field_name)


def save_video_upload_or_library(field_name):
    library_video = resolve_library_video()
    if library_video:
        return library_video
    return save_video_upload(field_name)


def data_uri(path):
    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def xai_headers(provider=None):
    return {**xai_auth_header(provider=provider), "Content-Type": "application/json"}


def xai_auth_header(provider=None):
    cfg = config()
    provider = provider or cfg["provider"]
    if provider in {"openai_api", "codex_proxy"}:
        raise RuntimeError("현재 Provider는 OpenAI 이미지 API입니다. 영상 기능은 Hermes/xAI Provider에서 실행해 주세요.")
    if provider == "hermes_proxy":
        return {"Authorization": f"Bearer {cfg['hermes_api_key']}"} if cfg.get("hermes_api_key") else {}
    token = oauth_access_token()
    if token:
        return {"Authorization": f"Bearer {token}"}
    key = cfg["api_key"]
    if not key:
        raise RuntimeError("Grok OAuth 로그인 또는 XAI_API_KEY 설정이 필요합니다.")
    return {"Authorization": f"Bearer {key}"}


def openai_auth_header():
    cfg = config()
    key = cfg.get("openai_api_key")
    if not key:
        raise RuntimeError("OPENAI_API_KEY 또는 설정의 OpenAI API 키가 필요합니다.")
    return {"Authorization": f"Bearer {key}"}


def extract_image_url(payload):
    data = payload.get("data") if isinstance(payload, dict) else None
    if not data:
        raise RuntimeError("API 응답에 이미지 데이터가 없습니다.")
    first = data[0] or {}
    return first.get("url"), first.get("b64_json"), first.get("mime_type", "image/jpeg"), first.get("revised_prompt", "")


def extract_response_text(payload):
    if payload.get("output_text"):
        return payload["output_text"]
    chunks = []
    for output in payload.get("output", []):
        for content in output.get("content", []):
            text = content.get("text") or content.get("output_text")
            if text:
                chunks.append(text)
    return "\n".join(chunks).strip()


def download_or_decode_image(url, b64_json, mime_type, dest_dir, filename_prefix=""):
    suffix = ".png" if "png" in mime_type else ".jpg"
    dest = dest_dir / f"{filename_prefix}{now_stamp()}-{uuid.uuid4().hex}{suffix}"
    if b64_json:
        dest.write_bytes(base64.b64decode(b64_json))
        return dest
    if not url:
        raise RuntimeError("API 응답에 저장할 이미지 URL이 없습니다.")
    response = requests.get(url, timeout=120)
    response.raise_for_status()
    dest.write_bytes(response.content)
    return dest


def openai_image_size(aspect_ratio):
    return {
        "1:1": "1024x1024",
        "2:3": "1024x1536",
        "9:16": "1024x1536",
        "3:2": "1536x1024",
        "16:9": "1536x1024",
    }.get(aspect_ratio or "auto", "auto")


def codex_image_size(aspect_ratio):
    return {
        "1:1": "1024x1024",
        "2:3": "1024x1536",
        "9:16": "1024x1536",
        "3:2": "1536x1024",
        "16:9": "1536x1024",
    }.get(aspect_ratio or "auto", "1024x1024")


def b64_image(path):
    return base64.b64encode(Path(path).read_bytes()).decode("ascii")


def codex_proxy_running(cfg=None):
    cfg = cfg or config()
    base = (cfg.get("codex_proxy_base_url") or "").rstrip("/")
    if not base:
        return False
    try:
        response = requests.get(base + "/api/health", timeout=3)
        return response.status_code < 500
    except requests.RequestException:
        return False


def codex_proxy_status_payload():
    cfg = config()
    base = (cfg.get("codex_proxy_base_url") or "").rstrip("/")
    payload = {
        "configured": bool(base),
        "base_url": base,
        "running": False,
        "provider": None,
        "oauth_status": None,
        "version": None,
        "detail": "",
    }
    if not base:
        return payload
    try:
        response = requests.get(base + "/api/health", timeout=5)
        payload["running"] = response.status_code < 500
        payload["detail"] = response.text[:1000]
        if response.headers.get("content-type", "").startswith("application/json"):
            data = response.json()
            payload["provider"] = data.get("provider")
            payload["version"] = data.get("version")
            runtime = data.get("runtime") or {}
            oauth = runtime.get("oauth") or {}
            payload["oauth_status"] = oauth.get("status")
            payload["oauth_url"] = oauth.get("url")
            payload["backend_url"] = (runtime.get("backend") or {}).get("url") or base
    except Exception as exc:
        payload["detail"] = str(exc)[:1000]
    return payload


def resolve_codex_proxy_command():
    local_ima2 = ROOT / "vendor" / "ima2-run" / "node_modules" / "ima2-gen" / "bin" / "ima2.js"
    for node_path in (
        Path(os.getenv("ProgramFiles", r"C:\Program Files")) / "nodejs" / "node.exe",
        Path(os.getenv("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "nodejs" / "node.exe",
        Path(shutil.which("node.exe") or ""),
        Path(shutil.which("node") or ""),
    ):
        if local_ima2.exists() and node_path.exists():
            return [str(node_path), str(local_ima2), "serve"]
    known_dirs = [
        Path(os.getenv("ProgramFiles", r"C:\Program Files")) / "nodejs",
        Path(os.getenv("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "nodejs",
        Path(os.getenv("APPDATA", "")) / "npm" if os.getenv("APPDATA") else None,
    ]
    for name in ("ima2.cmd", "ima2", "ima2-gen.cmd", "ima2-gen"):
        found = shutil.which(name)
        if found:
            return [found, "serve"]
        for folder in known_dirs:
            candidate = folder / name if folder else None
            if candidate and candidate.exists():
                return [str(candidate), "serve"]
    for name in ("npx.cmd", "npx"):
        found = shutil.which(name)
        if found:
            return [found, "-y", "ima2-gen", "serve"]
        for folder in known_dirs:
            candidate = folder / name if folder else None
            if candidate and candidate.exists():
                return [str(candidate), "-y", "ima2-gen", "serve"]
    return None


def codex_proxy_error(response):
    try:
        data = response.json()
        if isinstance(data, dict):
            parts = []
            for key in (
                "error",
                "message",
                "code",
                "upstreamCode",
                "upstreamType",
                "diagnosticReason",
                "eventTypes",
                "responseDiagnostics",
                "toolTypes",
                "toolChoiceKind",
                "requestId",
            ):
                value = data.get(key)
                if value not in (None, "", [], {}):
                    parts.append(f"{key}={value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)}")
            if parts:
                return "; ".join(parts)[:2000]
        return json.dumps(data, ensure_ascii=False)[:2000]
    except Exception:
        return response.text[:2000]


def codex_proxy_post_image(base, endpoint, headers, payload, timeout=300):
    response = requests.post(base + endpoint, headers=headers, json=payload, timeout=timeout)
    if response.status_code == 422 and payload.get("quality") != "low":
        retry_payload = {**payload, "quality": "low", "requestId": f"webgork-retry-{uuid.uuid4().hex}"}
        retry = requests.post(base + endpoint, headers=headers, json=retry_payload, timeout=timeout)
        if retry.status_code < 400:
            retry._webgork_retry = {"quality": "low", "reason": codex_proxy_error(response)}
            return retry
    return response


def codex_proxy_download_result(payload, dest_dir):
    image = payload.get("image")
    if not image and isinstance(payload.get("images"), list) and payload["images"]:
        first = payload["images"][0]
        image = first.get("image") if isinstance(first, dict) else first
    if not image:
        raise RuntimeError("Codex 프록시 응답에 이미지 데이터가 없습니다.")
    if isinstance(image, str) and image.startswith("data:"):
        header, b64_json = image.split(",", 1)
        mime_type = header.split(";")[0].replace("data:", "") or "image/png"
        return download_or_decode_image(None, b64_json, mime_type, dest_dir)
    if isinstance(image, str) and image.startswith("http"):
        return download_or_decode_image(image, None, "image/png", dest_dir)
    return download_or_decode_image(None, image, "image/png", dest_dir)


def codex_proxy_live_image(prompt, dest_dir, edit_sources=None, aspect_ratio="auto", model=None):
    cfg = config()
    base = cfg["codex_proxy_base_url"].rstrip("/")
    if not base:
        raise RuntimeError("Codex/ChatGPT OAuth 로컬 프록시 URL이 설정되지 않았습니다.")
    if not codex_proxy_running(cfg):
        started = start_codex_proxy_background()
        base = started.get("url") or base
        if not started.get("proxy_running"):
            raise RuntimeError(started.get("message") or "Codex OAuth 프록시가 실행 중이 아닙니다.")
    model = valid_codex_image_model(model, cfg)
    sources = list(edit_sources or [])
    common = {
        "prompt": prompt,
        "quality": "medium",
        "size": codex_image_size(aspect_ratio),
        "format": "png",
        "moderation": "low",
        "provider": "oauth",
        "model": model,
        "mode": "direct",
        "webSearchEnabled": False,
        "requestId": f"webgork-{uuid.uuid4().hex}",
    }
    headers = {"Content-Type": "application/json", "X-Ima2-Client": "webgork-studio-v2"}
    if len(sources) == 1:
        payload = {**common, "image": b64_image(sources[0])}
        endpoint = "/api/edit"
    else:
        payload = {**common, "references": [data_uri(source) for source in sources[:5]]}
        endpoint = "/api/generate"
    response = codex_proxy_post_image(base, endpoint, headers, payload, timeout=300)
    if response.status_code >= 400:
        raise RuntimeError(f"Codex OAuth 프록시 이미지 요청 실패: {response.status_code} {codex_proxy_error(response)}")
    payload = response.json()
    path = codex_proxy_download_result(payload, dest_dir)
    return path, {
        "provider": "codex_proxy",
        "image_model": model,
        "codex_proxy_url": base,
        "codex_filename": payload.get("filename"),
        "codex_request_id": payload.get("requestId"),
        "codex_elapsed": payload.get("elapsed"),
        "codex_size": common["size"],
        "codex_quality": getattr(response, "_webgork_retry", {}).get("quality") or common["quality"],
        "codex_retry": getattr(response, "_webgork_retry", None),
        "usage": payload.get("usage"),
        "revised_prompt": payload.get("revisedPrompt"),
    }


def openai_live_image(prompt, dest_dir, edit_sources=None, aspect_ratio="auto", model=None):
    cfg = config()
    model = valid_openai_image_model(model, cfg)
    sources = list(edit_sources or [])
    size = openai_image_size(aspect_ratio)
    if sources:
        data = {"model": model, "prompt": prompt}
        if size != "auto":
            data["size"] = size
        files = []
        handles = []
        try:
            field_name = "image[]" if len(sources) > 1 else "image"
            for source in sources[:16]:
                handle = open(source, "rb")
                handles.append(handle)
                files.append((field_name, (Path(source).name, handle, mimetypes.guess_type(Path(source).name)[0] or "image/png")))
            response = requests.post(
                cfg["openai_api_base"] + "/images/edits",
                headers=openai_auth_header(),
                data=data,
                files=files,
                timeout=240,
            )
        finally:
            for handle in handles:
                handle.close()
    else:
        body = {"model": model, "prompt": prompt}
        if size != "auto":
            body["size"] = size
        response = requests.post(
            cfg["openai_api_base"] + "/images/generations",
            headers={**openai_auth_header(), "Content-Type": "application/json"},
            json=body,
            timeout=240,
        )
    if response.status_code in (401, 403):
        raise RuntimeError(f"OpenAI 인증에 실패했습니다. API 키를 확인해 주세요. {response_error_detail(response)}")
    if response.status_code >= 400:
        raise RuntimeError(f"OpenAI 이미지 요청 실패: {response.status_code} {response_error_detail(response)}")
    payload = response.json()
    record_usage(payload.get("usage"))
    url, b64_json, mime_type, revised = extract_image_url(payload)
    path = download_or_decode_image(url, b64_json, mime_type, dest_dir)
    return path, {
        "provider": "openai_api",
        "image_model": model,
        "openai_size": size,
        "revised_prompt": revised,
        "remote_url": url,
    }


def ffmpeg_executable():
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


def ffmpeg_has_filter(name):
    ffmpeg = ffmpeg_executable()
    if not ffmpeg:
        return False
    try:
        completed = subprocess.run([ffmpeg, "-hide_banner", "-filters"], capture_output=True, text=True, timeout=30)
        return completed.returncode == 0 and f" {name} " in completed.stdout
    except Exception:
        return False


def image_dimensions(path):
    try:
        from PIL import Image

        with Image.open(path) as image:
            return image.size
    except Exception:
        pass
    try:
        with open(path, "rb") as handle:
            header = handle.read(32)
        if header.startswith(b"\x89PNG\r\n\x1a\n"):
            return struct.unpack(">II", header[16:24])
    except Exception:
        pass
    return None


def extract_last_frame(video_path):
    ensure_media_dirs()
    dest_dir = media_path("image")
    dest = dest_dir / f"{now_stamp()}-{uuid.uuid4().hex}-last-frame.png"
    ffmpeg = ffmpeg_executable()
    if ffmpeg:
        completed = subprocess.run(
            [
                ffmpeg,
                "-y",
                "-sseof",
                "-0.1",
                "-i",
                str(video_path),
                "-frames:v",
                "1",
                "-update",
                "1",
                str(dest),
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if completed.returncode == 0 and dest.exists():
            return dest
    try:
        import cv2

        capture = cv2.VideoCapture(str(video_path))
        if not capture.isOpened():
            raise RuntimeError("영상 파일을 열 수 없습니다.")
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        if frame_count > 1:
            capture.set(cv2.CAP_PROP_POS_FRAMES, frame_count - 1)
        ok, frame = capture.read()
        if not ok and frame_count > 2:
            capture.set(cv2.CAP_PROP_POS_FRAMES, frame_count - 2)
            ok, frame = capture.read()
        capture.release()
        if not ok:
            raise RuntimeError("마지막 프레임을 읽을 수 없습니다.")
        if not cv2.imwrite(str(dest), frame):
            raise RuntimeError("마지막 프레임을 저장할 수 없습니다.")
        return dest
    except ImportError as exc:
        raise RuntimeError("마지막 프레임 추출에는 ffmpeg, imageio-ffmpeg, 또는 opencv-python(cv2)이 필요합니다.") from exc


def target_short_edge(resolution):
    return 480 if resolution == "480p" else 720


def even_number(value):
    value = max(2, int(round(value)))
    return value if value % 2 == 0 else value + 1


def aspect_ratio_value(aspect_ratio, reference_path=None):
    if aspect_ratio and ":" in aspect_ratio:
        width, height = aspect_ratio.split(":", 1)
        try:
            return max(0.1, float(width) / float(height))
        except (TypeError, ValueError, ZeroDivisionError):
            pass
    dimensions = image_dimensions(reference_path) if reference_path else None
    if dimensions:
        width, height = dimensions
        if height:
            return max(0.1, width / height)
    return 16 / 9


def video_canvas_size(aspect_ratio, resolution, reference_path=None):
    short_edge = target_short_edge(resolution)
    ratio = aspect_ratio_value(aspect_ratio, reference_path)
    if ratio >= 1:
        width = even_number(short_edge * ratio)
        height = even_number(short_edge)
    else:
        width = even_number(short_edge)
        height = even_number(short_edge / ratio)
    return width, height


def video_canvas_size_from_reference(aspect_ratio, resolution, reference_path=None):
    if aspect_ratio in {"auto", "source"} and reference_path:
        dimensions = video_dimensions(reference_path)
        if dimensions:
            source_width, source_height = dimensions
            if source_width and source_height:
                short_edge = target_short_edge(resolution)
                if source_width >= source_height:
                    width = even_number(short_edge * (source_width / source_height))
                    height = even_number(short_edge)
                else:
                    width = even_number(short_edge)
                    height = even_number(short_edge * (source_height / source_width))
                return width, height
    return video_canvas_size(aspect_ratio, resolution, reference_path)


def ffprobe_executable():
    ffmpeg = ffmpeg_executable()
    if ffmpeg:
        ffprobe = Path(ffmpeg).with_name("ffprobe.exe" if os.name == "nt" else "ffprobe")
        if ffprobe.exists():
            return str(ffprobe)
    found = shutil.which("ffprobe")
    return found or None


def ffmpeg_probe_text(video_path):
    ffmpeg = ffmpeg_executable()
    if not ffmpeg:
        return ""
    try:
        completed = subprocess.run(
            [ffmpeg, "-hide_banner", "-i", str(video_path)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return (completed.stderr or "") + (completed.stdout or "")
    except Exception:
        return ""


def video_duration_seconds(video_path):
    probe_cmd = ffprobe_executable()
    if probe_cmd:
        try:
            completed = subprocess.run(
                [
                    probe_cmd,
                    "-v",
                    "error",
                    "-show_entries",
                    "format=duration",
                    "-of",
                    "default=noprint_wrappers=1:nokey=1",
                    str(video_path),
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if completed.returncode == 0 and completed.stdout.strip():
                return float(completed.stdout.strip())
        except Exception:
            pass
    probe_text = ffmpeg_probe_text(video_path)
    match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", probe_text)
    if match:
        hours, minutes, seconds = match.groups()
        return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    try:
        import cv2

        capture = cv2.VideoCapture(str(video_path))
        if not capture.isOpened():
            return None
        frames = float(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        fps = float(capture.get(cv2.CAP_PROP_FPS) or 0)
        capture.release()
        if frames > 0 and fps > 0:
            return frames / fps
    except Exception:
        pass
    return None


def video_dimensions(path):
    probe_cmd = ffprobe_executable()
    if probe_cmd:
        try:
            completed = subprocess.run(
                [
                    probe_cmd,
                    "-v",
                    "error",
                    "-select_streams",
                    "v:0",
                    "-show_entries",
                    "stream=width,height",
                    "-of",
                    "csv=s=x:p=0",
                    str(path),
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            text = completed.stdout.strip()
            if completed.returncode == 0 and "x" in text:
                width, height = [int(part) for part in text.split("x", 1)]
                if width and height:
                    return width, height
        except Exception:
            pass
    probe_text = ffmpeg_probe_text(path)
    match = re.search(r"Video:.*?(\d{2,5})x(\d{2,5})", probe_text)
    if match:
        width, height = int(match.group(1)), int(match.group(2))
        if width and height:
            return width, height
    return None


def video_has_audio(path):
    probe_cmd = ffprobe_executable()
    if probe_cmd:
        try:
            completed = subprocess.run(
                [
                    probe_cmd,
                    "-v",
                    "error",
                    "-select_streams",
                    "a:0",
                    "-show_entries",
                    "stream=index",
                    "-of",
                    "csv=p=0",
                    str(path),
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            return completed.returncode == 0 and bool(completed.stdout.strip())
        except Exception:
            pass
    return bool(re.search(r"Stream #\d+:\d+.*Audio:", ffmpeg_probe_text(path)))


def video_editor_canvas_size(aspect_ratio, resolution, reference_video):
    if resolution == "source":
        dimensions = video_dimensions(reference_video) or (1280, 720)
        return even_number(dimensions[0]), even_number(dimensions[1])
    if aspect_ratio == "source":
        dimensions = video_dimensions(reference_video)
        if dimensions:
            width, height = dimensions
            ratio = width / height
            short = target_short_edge(resolution)
            if ratio >= 1:
                return even_number(short * ratio), even_number(short)
            return even_number(short), even_number(short / ratio)
    return video_canvas_size(aspect_ratio if aspect_ratio != "source" else "16:9", resolution)


def edited_video_output_path():
    ensure_media_dirs()
    return media_path("video", f"{now_stamp()}-{uuid.uuid4().hex}-edited.mp4")


def parse_video_clip_settings(raw, count):
    try:
        data = json.loads(raw or "[]")
    except Exception:
        data = []
    if not isinstance(data, list):
        data = []
    settings = []
    for index in range(count):
        item = data[index] if index < len(data) and isinstance(data[index], dict) else {}
        start = max(0, float(item.get("start") or 0))
        end_value = item.get("end")
        end = None if end_value in (None, "") else max(0, float(end_value))
        settings.append({"start": start, "end": end})
    return settings


def normalized_clip_settings(video_paths, clip_settings):
    raw_durations = [video_duration_seconds(path) or 0 for path in video_paths]
    settings = clip_settings or [{} for _ in video_paths]
    normalized = []
    clip_durations = []
    for index, raw_duration in enumerate(raw_durations):
        item = settings[index] if index < len(settings) else {}
        start = max(0, float(item.get("start") or 0))
        if raw_duration:
            start = min(start, max(0, raw_duration - 0.1))
        end = item.get("end")
        if end is None:
            end = raw_duration if raw_duration else None
        else:
            end = max(0, float(end))
            if raw_duration:
                end = min(end, raw_duration)
        if end is not None and end <= start + 0.05:
            raise ValueError(f"{index + 1}번 클립의 끝 시간이 시작 시간보다 커야 합니다.")
        duration = max(0, (end - start) if end is not None else max(0, raw_duration - start))
        if duration <= 0:
            raise ValueError(f"{index + 1}번 클립의 길이를 확인해 주세요.")
        normalized.append({"start": start, "end": end})
        clip_durations.append(duration)
    return normalized, raw_durations, clip_durations


def trim_filter(kind, start, end):
    name = "atrim" if kind == "audio" else "trim"
    parts = [f"{name}=start={start:.3f}"]
    if end is not None:
        parts.append(f"end={end:.3f}")
    return ":".join(parts)


def edit_merge_videos(video_paths, fade_in=0, fade_out=0, transition="cut", crossfade=0, aspect_ratio="source", resolution="source", mute=True, clip_settings=None):
    ffmpeg = ffmpeg_executable()
    if not ffmpeg:
        raise RuntimeError("영상 편집에는 ffmpeg 또는 imageio-ffmpeg가 필요합니다.")
    if not video_paths:
        raise ValueError("편집할 영상이 없습니다.")
    if len(video_paths) > 12:
        raise ValueError("한 번에 최대 12개 영상까지 편집할 수 있습니다.")
    fade_in = max(0, min(float(fade_in or 0), 10))
    fade_out = max(0, min(float(fade_out or 0), 10))
    crossfade = max(0, min(float(crossfade or 0), 5))
    transition = transition if transition in {"cut", "crossfade"} else "cut"
    requested_transition = transition
    transition_fallback_reason = None
    if transition == "crossfade" and not ffmpeg_has_filter("xfade"):
        transition = "cut"
        transition_fallback_reason = "현재 ffmpeg 빌드가 xfade 필터를 제공하지 않아 일반 병합으로 처리했습니다."
    width, height = video_editor_canvas_size(aspect_ratio, resolution, video_paths[0])
    clip_settings, source_durations, durations = normalized_clip_settings(video_paths, clip_settings)
    if transition == "crossfade" and len(video_paths) > 1 and crossfade > 0:
        shortest = min(durations)
        crossfade = min(crossfade, max(0, shortest / 2))
        if crossfade < 0.05:
            transition = "cut"
            transition_fallback_reason = "클립 길이가 너무 짧아 일반 병합으로 처리했습니다."
    dest = edited_video_output_path()
    inputs = []
    for path in video_paths:
        inputs.extend(["-i", str(path)])

    base_filters = []
    for index, duration in enumerate(durations):
        clip = clip_settings[index]
        filters = [
            trim_filter("video", clip["start"], clip["end"]),
            "fps=24",
            f"scale={width}:{height}:force_original_aspect_ratio=decrease",
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2",
            "setsar=1",
            "settb=AVTB",
            "setpts=PTS-STARTPTS",
            "format=yuv420p",
        ]
        if fade_in > 0:
            filters.append(f"fade=t=in:st=0:d={fade_in:.3f}")
        if fade_out > 0 and duration > 0:
            start = max(0, duration - fade_out)
            filters.append(f"fade=t=out:st={start:.3f}:d={fade_out:.3f}")
        base_filters.append(f"[{index}:v:0]{','.join(filters)}[v{index}]")

    output_label = "v"
    if transition == "crossfade" and len(video_paths) > 1 and crossfade > 0:
        chain = base_filters[:]
        current = "v0"
        elapsed = durations[0] if durations[0] else 0
        for index in range(1, len(video_paths)):
            next_duration = durations[index] if durations[index] else 0
            offset = max(0.1, elapsed - crossfade)
            out_label = f"xf{index}" if index < len(video_paths) - 1 else output_label
            chain.append(f"[{current}][v{index}]xfade=transition=fade:duration={crossfade:.3f}:offset={offset:.3f}[{out_label}]")
            current = out_label
            elapsed = max(0, elapsed + next_duration - crossfade)
        filter_complex = ";".join(chain)
    else:
        filter_complex = ";".join(base_filters + [f"{''.join(f'[v{i}]' for i in range(len(video_paths)))}concat=n={len(video_paths)}:v=1:a=0[{output_label}]"])

    audio_args = ["-an"]
    preserve_audio = not mute and any(video_has_audio(path) for path in video_paths)
    if preserve_audio:
        audio_filters = []
        for index, path in enumerate(video_paths):
            clip = clip_settings[index]
            duration = durations[index]
            if video_has_audio(path):
                audio_filters.append(
                    f"[{index}:a:0]{trim_filter('audio', clip['start'], clip['end'])},"
                    "asetpts=PTS-STARTPTS,aresample=44100,"
                    "aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo"
                    f"[a{index}]"
                )
            else:
                audio_filters.append(
                    "anullsrc=channel_layout=stereo:sample_rate=44100,"
                    f"atrim=0:{duration:.3f},asetpts=PTS-STARTPTS[a{index}]"
                )
        audio_filters.append(f"{''.join(f'[a{i}]' for i in range(len(video_paths)))}concat=n={len(video_paths)}:v=0:a=1[a]")
        filter_complex = ";".join([filter_complex, *audio_filters])
        audio_args = ["-map", "[a]", "-c:a", "aac", "-b:a", "160k", "-shortest"]

    command = [
        ffmpeg,
        "-y",
        *inputs,
        "-filter_complex",
        filter_complex,
        "-map",
        f"[{output_label}]",
        *audio_args,
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "18",
        "-movflags",
        "+faststart",
        str(dest),
    ]
    completed = subprocess.run(command, capture_output=True, text=True, timeout=900)
    if completed.returncode != 0:
        fallback = command.copy()
        if "libx264" in fallback:
            fallback[fallback.index("libx264")] = "mpeg4"
        for token in ("-preset", "veryfast", "-crf", "18"):
            if token in fallback:
                fallback.pop(fallback.index(token))
        completed = subprocess.run(fallback, capture_output=True, text=True, timeout=900)
    if completed.returncode != 0 or not dest.exists():
        detail = (completed.stderr or completed.stdout or "").strip()
        raise RuntimeError(f"영상 편집에 실패했습니다. {detail[:900]}")
    return dest, {
        "canvas_width": width,
        "canvas_height": height,
        "source_count": len(video_paths),
        "source_video_paths": [public_path(path) for path in video_paths],
        "source_durations": source_durations,
        "clip_settings": clip_settings,
        "clip_durations": durations,
        "fade_in": fade_in,
        "fade_out": fade_out,
        "transition": transition,
        "requested_transition": requested_transition,
        "transition_fallback_reason": transition_fallback_reason,
        "crossfade": crossfade if transition == "crossfade" else 0,
        "muted": bool(mute) or not preserve_audio,
        "requested_mute": bool(mute),
        "audio_preserved": bool(preserve_audio),
        "resolution": resolution,
        "aspect_ratio": aspect_ratio,
        "generation_type": "video_edit",
    }


def trim_video_for_extension(source_video, connect_time):
    source_duration = video_duration_seconds(source_video)
    if connect_time is None:
        if not source_duration or source_duration <= 15:
            return source_video, {
                "connect_time": None,
                "trimmed_for_connect_time": False,
                "auto_trimmed_to_last_15s": False,
                "trim_start": 0,
                "trim_end": None,
                "trim_duration": None,
            }
        connect_time = source_duration
        auto_trimmed = True
    else:
        auto_trimmed = False
    if source_duration and connect_time > source_duration:
        raise ValueError(f"연결 지점이 원본 영상 길이({source_duration:.1f}초)를 초과했습니다.")
    end_time = connect_time
    if end_time < 2:
        raise ValueError("공식 연장 연결 지점은 최소 2.0초 이상이어야 합니다.")
    start_time = max(0, end_time - 15)
    clip_duration = end_time - start_time
    if clip_duration < 2:
        raise ValueError("공식 연장 입력 클립은 최소 2초 이상이어야 합니다.")
    ffmpeg = ffmpeg_executable()
    if not ffmpeg:
        raise RuntimeError("연결 지점 지정에는 ffmpeg 또는 imageio-ffmpeg가 필요합니다.")
    ensure_media_dirs()
    dest = media_path("uploads", f"{now_stamp()}-{uuid.uuid4().hex}-official-connect.mp4")
    has_audio = video_has_audio(source_video)
    command = [
        ffmpeg,
        "-y",
        "-ss",
        f"{start_time:.1f}",
        "-i",
        str(source_video),
        "-t",
        f"{clip_duration:.1f}",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "18",
        *(["-c:a", "aac", "-b:a", "192k"] if has_audio else ["-an"]),
        "-movflags",
        "+faststart",
        str(dest),
    ]
    completed = subprocess.run(command, capture_output=True, text=True, timeout=300)
    if completed.returncode != 0 or not dest.exists():
        detail = (completed.stderr or completed.stdout or "").strip()
        raise RuntimeError(f"연결 지점 클립 생성에 실패했습니다. {detail[:600]}")
    return dest, {
        "connect_time": connect_time,
        "trimmed_for_connect_time": True,
        "auto_trimmed_to_last_15s": auto_trimmed,
        "trim_start": start_time,
        "trim_end": end_time,
        "trim_duration": clip_duration,
        "trim_source_has_audio": has_audio,
    }


def trim_video_segment(source_video, start_time, duration, suffix):
    ffmpeg = ffmpeg_executable()
    if not ffmpeg:
        raise RuntimeError("영상 구간 추출에는 ffmpeg 또는 imageio-ffmpeg가 필요합니다.")
    ensure_media_dirs()
    dest = media_path("uploads", f"{now_stamp()}-{uuid.uuid4().hex}-{suffix}.mp4")
    has_audio = video_has_audio(source_video)
    command = [
        ffmpeg,
        "-y",
        "-ss",
        f"{max(0, start_time):.1f}",
        "-i",
        str(source_video),
        "-t",
        f"{duration:.1f}",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "18",
        *(["-c:a", "aac", "-b:a", "192k"] if has_audio else ["-an"]),
        "-movflags",
        "+faststart",
        str(dest),
    ]
    completed = subprocess.run(command, capture_output=True, text=True, timeout=300)
    if completed.returncode != 0 or not dest.exists():
        detail = (completed.stderr or completed.stdout or "").strip()
        raise RuntimeError(f"영상 구간 추출에 실패했습니다. {detail[:600]}")
    return dest


def compose_official_connected_result(original_video, official_result, trim_extra, aspect_ratio, resolution):
    if not trim_extra.get("trimmed_for_connect_time"):
        return official_result, {"combined_by": "official_api", "stitched_after_connect_time": False}
    connect_time = trim_extra["connect_time"]
    if connect_time <= 0:
        return official_result, {"combined_by": "official_api", "stitched_after_connect_time": False}
    prefix_duration = trim_extra.get("trim_start") or 0
    if prefix_duration < 0.2:
        return official_result, {"combined_by": "official_api_last_15s_direct", "stitched_after_connect_time": False}
    prefix = trim_video_segment(original_video, 0, prefix_duration, "official-prefix")
    path, concat_extra = concat_videos(
        prefix,
        official_result,
        aspect_ratio,
        resolution,
        reference_path=None,
        mute_audio=False,
    )
    concat_extra.update({
        "combined_by": "official_api_prefix_plus_extended_result",
        "stitched_after_connect_time": True,
        "prefix_path": public_path(prefix),
        "prefix_duration": prefix_duration,
        "removed_duplicate_seconds": 0,
        "official_result_includes_reference_clip": True,
    })
    return path, concat_extra


def concat_videos(source_video, extension_video, aspect_ratio, resolution, reference_path=None, mute_audio=True):
    ffmpeg = ffmpeg_executable()
    if not ffmpeg:
        raise RuntimeError("원본 영상과 연장 영상을 이어붙이려면 ffmpeg 또는 imageio-ffmpeg가 필요합니다.")
    ensure_media_dirs()
    width, height = video_canvas_size_from_reference(aspect_ratio, resolution, reference_path or source_video)
    dest = media_path("video", f"{now_stamp()}-{uuid.uuid4().hex}-extended.mp4")
    fit = (
        f"fps=24,scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,format=yuv420p"
    )
    source_duration = video_duration_seconds(source_video) or 0
    extension_duration = video_duration_seconds(extension_video) or 0
    source_has_audio = video_has_audio(source_video)
    extension_has_audio = video_has_audio(extension_video)
    preserve_audio = not mute_audio and (source_has_audio or extension_has_audio) and (source_duration > 0 or extension_duration > 0)
    if preserve_audio:
        audio_graph_parts = []
        audio_labels = []
        if source_duration > 0:
            source_audio = (
                f"[0:a:0]aformat=sample_rates=44100:channel_layouts=stereo,apad,"
                f"atrim=0:{source_duration:.3f},asetpts=PTS-STARTPTS[a0];"
                if source_has_audio
                else f"anullsrc=channel_layout=stereo:sample_rate=44100,atrim=0:{source_duration:.3f},asetpts=PTS-STARTPTS[a0];"
            )
            audio_graph_parts.append(source_audio)
            audio_labels.append("[a0]")
        if extension_duration > 0:
            extension_audio = (
                f"[1:a:0]aformat=sample_rates=44100:channel_layouts=stereo,apad,"
                f"atrim=0:{extension_duration:.3f},asetpts=PTS-STARTPTS[a1];"
                if extension_has_audio
                else f"anullsrc=channel_layout=stereo:sample_rate=44100,atrim=0:{extension_duration:.3f},asetpts=PTS-STARTPTS[a1];"
            )
            audio_graph_parts.append(extension_audio)
            audio_labels.append("[a1]")
        if len(audio_labels) > 1:
            audio_graph = f"{''.join(audio_graph_parts)}{''.join(audio_labels)}concat=n={len(audio_labels)}:v=0:a=1[a]"
        else:
            audio_graph = f"{''.join(audio_graph_parts)}{audio_labels[0]}anull[a]"
        filter_complex = f"[0:v:0]{fit}[v0];[1:v:0]{fit}[v1];[v0][v1]concat=n=2:v=1:a=0[v];{audio_graph}"
    else:
        filter_complex = f"[0:v:0]{fit}[v0];[1:v:0]{fit}[v1];[v0][v1]concat=n=2:v=1:a=0[v]"
    command = [
        ffmpeg,
        "-y",
        "-i",
        str(source_video),
        "-i",
        str(extension_video),
        "-filter_complex",
        filter_complex,
        "-map",
        "[v]",
        *(["-map", "[a]", "-c:a", "aac", "-b:a", "192k"] if preserve_audio else ["-an"]),
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "18",
        "-movflags",
        "+faststart",
        str(dest),
    ]
    completed = subprocess.run(command, capture_output=True, text=True, timeout=600)
    if completed.returncode != 0:
        fallback = command.copy()
        codec_index = fallback.index("libx264")
        fallback[codec_index] = "mpeg4"
        for token in ("-preset", "veryfast", "-crf", "18"):
            if token in fallback:
                idx = fallback.index(token)
                fallback.pop(idx)
        completed = subprocess.run(fallback, capture_output=True, text=True, timeout=600)
    if completed.returncode != 0 or not dest.exists():
        detail = (completed.stderr or completed.stdout or "").strip()
        raise RuntimeError(f"영상 이어붙이기에 실패했습니다. {detail[:600]}")
    return dest, {
        "canvas_width": width,
        "canvas_height": height,
        "muted": bool(mute_audio) or not preserve_audio,
        "requested_mute": bool(mute_audio),
        "source_audio_preserved": preserve_audio and source_has_audio,
        "extension_audio_preserved": preserve_audio and extension_has_audio,
        "source_has_audio": source_has_audio,
        "extension_has_audio": extension_has_audio,
    }


def should_upscale_frame(frame_path, resolution):
    dimensions = image_dimensions(frame_path)
    if not dimensions:
        return False, None
    width, height = dimensions
    return min(width, height) < int(target_short_edge(resolution) * 0.85), {"width": width, "height": height}


def maybe_upscale_frame(frame_path, prompt, aspect_ratio, resolution):
    needs_upscale, dimensions = should_upscale_frame(frame_path, resolution)
    if not needs_upscale:
        return frame_path, False, dimensions, None
    cfg = config()
    if cfg["mode"] != "live":
        return frame_path, False, dimensions, "mock 모드에서는 업스케일을 건너뜁니다."
    upscale_prompt = (
        f"이 이미지를 영상 생성의 첫 프레임으로 쓰기 좋게 선명하게 업스케일해 주세요. "
        f"원본 구도, 색감, 피사체, 마지막 프레임의 연속성을 유지하고 짧은 변이 최소 {target_short_edge(resolution)}px 이상이 되도록 보강하세요. "
        f"후속 영상 프롬프트: {prompt}"
    )
    upscaled, extra = live_image(upscale_prompt, media_path("image"), edit_source=frame_path, aspect_ratio=aspect_ratio)
    return upscaled, True, dimensions, extra


def frame_upscale_prompt(prompt):
    return (
        "Upscale this extracted last frame to 2K quality for use as the first frame of a continuation video. "
        "Preserve the exact composition, identity, pose, clothing, lighting, color, camera angle, and background. "
        "Do not add, remove, crop, reinterpret, or apply motion. "
        f"Continuation prompt for context only: {prompt}"
    )


def upscale_frame_to_2k(frame_path, prompt):
    dimensions = image_dimensions(frame_path)
    cfg = config()
    if cfg["mode"] != "live":
        return frame_path, False, dimensions, "mock 모드에서는 업스케일을 건너뜁니다."
    upscale_prompt = frame_upscale_prompt(prompt)
    upscaled, extra = live_image(
        upscale_prompt,
        media_path("image"),
        edit_source=frame_path,
        aspect_ratio="auto",
        resolution="2k",
    )
    if isinstance(extra, dict):
        extra["upscale_prompt"] = upscale_prompt
    return upscaled, True, dimensions, extra


def upscale_i2v_sources_to_2k(sources, video_prompt=None):
    upscale_prompt = (
        "Upscale this image to 2K quality for image-to-video generation. "
        "Preserve the exact composition, subject identity, pose, clothing, lighting, colors, background, text if present, and camera angle. "
        "Do not add, remove, crop, reinterpret objects, or apply the later video motion prompt as an image edit instruction."
    )
    upscaled_sources = []
    details = []
    for source in sources:
        upscaled, extra = live_image(
            upscale_prompt,
            media_path("image"),
            edit_source=source,
            aspect_ratio="auto",
            resolution="2k",
        )
        upscaled_sources.append(upscaled)
        details.append({
            "original_path": public_path(source),
            "upscaled_path": public_path(upscaled),
            "extra": extra,
        })
    return upscaled_sources, details


def mock_svg(dest_dir, title, prompt, filename_prefix=""):
    safe_title = title.replace("&", "&amp;").replace("<", "&lt;")
    safe_prompt = prompt[:180].replace("&", "&amp;").replace("<", "&lt;")
    dest = dest_dir / f"{filename_prefix}{now_stamp()}-{uuid.uuid4().hex}.svg"
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="768" viewBox="0 0 1280 768">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop stop-color="#183a37"/>
      <stop offset=".45" stop-color="#f2c14e"/>
      <stop offset="1" stop-color="#c44536"/>
    </linearGradient>
  </defs>
  <rect width="1280" height="768" fill="url(#bg)"/>
  <circle cx="1010" cy="160" r="92" fill="#f7f4ea" opacity=".82"/>
  <rect x="96" y="112" width="760" height="424" rx="8" fill="#101820" opacity=".82"/>
  <text x="140" y="210" fill="#f7f4ea" font-family="Arial" font-size="56" font-weight="700">{safe_title}</text>
  <text x="140" y="294" fill="#f7f4ea" font-family="Arial" font-size="28">{safe_prompt}</text>
  <text x="140" y="472" fill="#f2c14e" font-family="Arial" font-size="24">Mock mode preview</text>
</svg>"""
    dest.write_text(svg, encoding="utf-8")
    return dest


def live_image(prompt, dest_dir, edit_source=None, edit_sources=None, aspect_ratio="auto", resolution="auto", image_model=None, image_provider=None):
    cfg = config()
    sources = edit_sources or ([edit_source] if edit_source else [])
    provider = image_provider or cfg["provider"]
    if provider == "openai_api":
        return openai_live_image(prompt, dest_dir, edit_sources=sources, aspect_ratio=aspect_ratio, model=image_model)
    if provider == "codex_proxy":
        return codex_proxy_live_image(prompt, dest_dir, edit_sources=sources, aspect_ratio=aspect_ratio, model=image_model)
    endpoint = "/images/edits" if sources else "/images/generations"
    model = valid_image_model(image_model, cfg)
    body = {"model": model, "prompt": prompt}
    if not sources:
        body["response_format"] = "b64_json"
    if aspect_ratio != "auto":
        body["aspect_ratio"] = aspect_ratio
    if resolution != "auto":
        body["resolution"] = resolution
    if sources:
        if len(sources) == 1:
            body["image"] = {"url": data_uri(sources[0]), "type": "image_url"}
        else:
            body["images"] = [{"url": data_uri(source), "type": "image_url"} for source in sources[:3]]
    api_base = cfg["hermes_base_url"] if provider == "hermes_proxy" and cfg.get("hermes_base_url") else cfg["api_base"]
    response = requests.post(api_base + endpoint, headers=xai_headers(provider=provider), json=body, timeout=240)
    if response.status_code in (401, 403):
        raise RuntimeError(f"xAI 인증에 실패했습니다. API 키를 확인해 주세요. {response_error_detail(response)}")
    if response.status_code >= 400:
        raise RuntimeError(f"이미지 요청 실패: {response.status_code} {response_error_detail(response)}")
    payload = response.json()
    record_usage(payload.get("usage"))
    url, b64_json, mime_type, revised = extract_image_url(payload)
    path = download_or_decode_image(url, b64_json, mime_type, dest_dir)
    return path, {"revised_prompt": revised, "remote_url": url, "image_model": model}


def edit_image_with_config(prompt, source_path, dest_dir, cfg, auth_header, aspect_ratio="auto", filename_prefix="", resolution="auto"):
    body = {
        "model": cfg["image_model"],
        "prompt": prompt,
        "image": {"url": data_uri(source_path), "type": "image_url"},
    }
    if aspect_ratio != "auto":
        body["aspect_ratio"] = aspect_ratio
    if resolution != "auto":
        body["resolution"] = resolution
    response = requests.post(
        cfg["api_base"] + "/images/edits",
        headers={**auth_header, "Content-Type": "application/json"},
        json=body,
        timeout=240,
    )
    if response.status_code in (401, 403):
        raise RuntimeError(f"xAI 인증에 실패했습니다. API 키를 확인해 주세요. {response_error_detail(response)}")
    if response.status_code >= 400:
        raise RuntimeError(f"이미지 요청 실패: {response.status_code} {response_error_detail(response)}")
    payload = response.json()
    record_usage(payload.get("usage"))
    url, b64_json, mime_type, revised = extract_image_url(payload)
    path = download_or_decode_image(url, b64_json, mime_type, dest_dir, filename_prefix=filename_prefix)
    return path, {"revised_prompt": revised, "remote_url": url, "image_resolution": resolution}


def edit_image_sources_with_config(prompt, source_paths, dest_dir, cfg, auth_header, aspect_ratio="auto", filename_prefix="", resolution="auto"):
    sources = [Path(source) for source in source_paths if source]
    if not sources:
        raise ValueError("편집할 이미지가 없습니다.")
    body = {
        "model": cfg["image_model"],
        "prompt": prompt,
    }
    if aspect_ratio != "auto":
        body["aspect_ratio"] = aspect_ratio
    if resolution != "auto":
        body["resolution"] = resolution
    if len(sources) == 1:
        body["image"] = {"url": data_uri(sources[0]), "type": "image_url"}
    else:
        body["images"] = [{"url": data_uri(source), "type": "image_url"} for source in sources[:3]]
    response = requests.post(
        cfg["api_base"] + "/images/edits",
        headers={**auth_header, "Content-Type": "application/json"},
        json=body,
        timeout=240,
    )
    if response.status_code in (401, 403):
        raise RuntimeError(f"xAI 인증에 실패했습니다. API 키를 확인해 주세요. {response_error_detail(response)}")
    if response.status_code >= 400:
        raise RuntimeError(f"이미지 요청 실패: {response.status_code} {response_error_detail(response)}")
    payload = response.json()
    record_usage(payload.get("usage"))
    url, b64_json, mime_type, revised = extract_image_url(payload)
    path = download_or_decode_image(url, b64_json, mime_type, dest_dir, filename_prefix=filename_prefix)
    return path, {
        "revised_prompt": revised,
        "remote_url": url,
        "image_model": cfg["image_model"],
        "image_resolution": resolution,
        "source_count": len(sources),
    }


def live_video(prompt, image_path, duration, aspect_ratio="source", resolution="720p", video_model=None):
    cfg = config()
    model = valid_video_model(video_model, cfg)
    payload = {
        "model": model,
        "prompt": prompt,
        "image": {"url": data_uri(image_path)},
        "duration": duration,
        "resolution": resolution,
    }
    if aspect_ratio not in {"auto", "source"}:
        payload["aspect_ratio"] = aspect_ratio
    start = requests.post(
        cfg["api_base"] + "/videos/generations",
        headers=xai_headers(),
        json=payload,
        timeout=120,
    )
    if start.status_code >= 400:
        raise RuntimeError(f"영상 생성 요청 실패: {start.status_code} {response_error_detail(start)}")
    request_id = (start.json() or {}).get("request_id")
    if not request_id:
        raise RuntimeError("영상 생성 요청 ID를 받지 못했습니다.")
    path, extra = poll_video_request(request_id)
    extra["video_model"] = model
    return path, extra


def live_video_from_reference_images(prompt, reference_paths, duration, aspect_ratio="source", resolution="720p", video_model=None):
    cfg = config()
    model = valid_video_model(video_model, cfg)
    references = []
    seen = set()
    for path in reference_paths:
        if not path:
            continue
        resolved = Path(path).resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        references.append({"url": data_uri(resolved)})
    if not references:
        raise RuntimeError("참조 이미지가 없습니다.")
    payload = {
        "model": model,
        "prompt": prompt,
        "reference_images": references[:7],
        "duration": min(10, duration),
        "resolution": resolution,
    }
    if aspect_ratio not in {"auto", "source"}:
        payload["aspect_ratio"] = aspect_ratio
    start = requests.post(
        cfg["api_base"] + "/videos/generations",
        headers=xai_headers(),
        json=payload,
        timeout=120,
    )
    if start.status_code >= 400:
        raise RuntimeError(f"참조 이미지 기반 영상 생성 요청 실패: {start.status_code} {response_error_detail(start)}")
    request_id = (start.json() or {}).get("request_id")
    if not request_id:
        raise RuntimeError("참조 이미지 기반 영상 생성 요청 ID를 받지 못했습니다.")
    path, extra = poll_video_request(request_id)
    extra["video_model"] = model
    extra["reference_image_count"] = len(references[:7])
    if duration > 10:
        extra["requested_duration"] = duration
        extra["duration_clamped_to"] = 10
    return path, extra


def live_video_with_reference_context(prompt, image_path, duration, aspect_ratio="source", resolution="720p", reference_context=None, video_model=None):
    if not reference_context:
        return live_video(prompt, image_path, duration, aspect_ratio=aspect_ratio, resolution=resolution, video_model=video_model)
    original_start = reference_context.get("start_image")
    reference_prompt = (
        f"{prompt}\n\n"
        f"Use <IMAGE_1> as the final frame of the previous clip and continue the motion from that moment. "
        f"Use <IMAGE_2> only as the original visual reference for identity, palette, subjects, clothing, environment, and style. "
        f"Do not infer or reuse any prior prompt text; follow the user's continuation prompt above."
    ).strip()
    path, extra = live_video_from_reference_images(
        reference_prompt,
        [image_path, original_start],
        duration,
        aspect_ratio=aspect_ratio,
        resolution=resolution,
        video_model=video_model,
    )
    extra["used_last_frame_and_original_image_references"] = True
    extra["original_start_image_path"] = reference_context.get("start_image_path")
    return path, extra


def response_error_detail(response):
    try:
        return json.dumps(response.json(), ensure_ascii=False)[:1200]
    except Exception:
        return (response.text or "")[:1200]


def clean_planned_prompt(text):
    prompt = (text or "").strip()
    prompt = re.sub(r"^```(?:text|prompt|json)?\s*", "", prompt, flags=re.IGNORECASE)
    prompt = re.sub(r"\s*```$", "", prompt)
    prompt = re.sub(r"^\s*(final\s+prompt|planned\s+prompt|prompt|프롬프트)\s*:\s*", "", prompt, flags=re.IGNORECASE)
    return prompt.strip().strip('"').strip()


def prompt_planner_request_metadata(source, effective_prompt):
    getter = source.get if isinstance(source, dict) else source.get
    enabled = checked(getter("prompt_planner_enabled") or getter("use_prompt_planner"))
    original = (getter("original_prompt") or "").strip()
    planned = (getter("planned_prompt") or effective_prompt or "").strip()
    model = (getter("prompt_planner_model") or "").strip()
    context = (getter("prompt_planner_context") or "").strip()
    if not enabled and not original and not model:
        return {}
    return {
        "prompt_planner_enabled": bool(enabled or original or model),
        "prompt_planner_applied": bool(original and planned and original != planned),
        "original_prompt": original or effective_prompt,
        "planned_prompt": planned or effective_prompt,
        "prompt_planner_model": model,
        "prompt_planner_context": context,
    }


def prompt_planner_base_and_headers():
    cfg = config()
    hermes_base = (cfg.get("hermes_base_url") or "").strip().rstrip("/")
    if hermes_base:
        if "127.0.0.1:8645" in hermes_base or "localhost:8645" in hermes_base:
            ensure_hermes_proxy_background()
        return hermes_base, xai_headers(provider="hermes_proxy")
    if cfg["provider"] in {"direct", "hermes_proxy"}:
        return cfg["api_base"], xai_headers()
    raise RuntimeError("Grok 4.2 프롬프트 플래너를 사용하려면 Hermes xAI OAuth 프록시를 연결해 주세요.")


def plan_generation_prompt(prompt, context):
    cfg = config()
    model = cfg.get("prompt_planner_model") or "grok-4.20-0309-reasoning"
    task = (context.get("task") or "generation").strip()
    target_model = (context.get("target_model") or "").strip()
    aspect_ratio = (context.get("aspect_ratio") or "").strip()
    resolution = (context.get("resolution") or "").strip()
    duration = (context.get("duration") or "").strip()
    source_count = (context.get("source_count") or "").strip()
    system_prompt = (
        "You are a prompt planner for downstream image and video generation models. "
        "You do not generate images or videos. You rewrite the user's intent into one clear, concrete execution prompt. "
        "Preserve the user's requested subject, style, language, continuity, identity, composition, and constraints. "
        "Do not add policy-evasion wording, do not mention safety systems, and do not invent disallowed details. "
        "Return only the final downstream prompt, with no markdown, explanation, labels, JSON, or quotes."
    )
    user_prompt = (
        f"Operation: {task}\n"
        f"Target model: {target_model or 'unspecified'}\n"
        f"Aspect ratio: {aspect_ratio or 'unspecified'}\n"
        f"Resolution: {resolution or 'unspecified'}\n"
        f"Duration seconds: {duration or 'unspecified'}\n"
        f"Reference image/video count: {source_count or 'unspecified'}\n\n"
        "User prompt:\n"
        f"{prompt}\n\n"
        "Rewrite it as a detailed execution prompt for the downstream generator. "
        "If the user wrote Korean, keep important Korean text exactly when it is meant to appear in the output, "
        "but the descriptive visual instructions may be written in natural English if that is clearer for the generator."
    )
    payload = {
        "model": model,
        "stream": False,
        "temperature": 0.2,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    base, headers = prompt_planner_base_and_headers()
    response = requests.post(base.rstrip("/") + "/chat/completions", headers=headers, json=payload, timeout=90)
    if response.status_code >= 400:
        raise RuntimeError(f"프롬프트 플래너 요청 실패: {response.status_code} {response_error_detail(response)}")
    data = response.json() or {}
    record_usage(data.get("usage"))
    content = ""
    choices = data.get("choices") or []
    if choices:
        message = choices[0].get("message") or {}
        content = message.get("content") or ""
    if not content:
        content = extract_response_text(data)
    planned = clean_planned_prompt(content)
    if not planned:
        raise RuntimeError("프롬프트 플래너가 빈 프롬프트를 반환했습니다.")
    return planned, {"model": model, "usage": data.get("usage"), "base_url": base}


def xai_upload_file(path):
    cfg = config()
    if not path.exists():
        raise RuntimeError("업로드할 파일을 찾을 수 없습니다.")
    if path.stat().st_size > 48 * 1024 * 1024:
        raise RuntimeError("xAI Files API 업로드 한도(48MB)를 초과했습니다. 더 짧거나 작은 mp4를 사용해 주세요.")
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    with path.open("rb") as handle:
        response = requests.post(
            cfg["api_base"] + "/files",
            headers=xai_auth_header(),
            data={"purpose": "assistants"},
            files={"file": (path.name, handle, mime)},
            timeout=240,
        )
    if response.status_code >= 400:
        raise RuntimeError(f"xAI 파일 업로드 실패: {response.status_code} {response_error_detail(response)}")
    payload = response.json() or {}
    file_id = payload.get("id")
    if not file_id:
        raise RuntimeError(f"xAI 파일 업로드 응답에 file id가 없습니다: {payload}")
    return file_id, payload


def live_video_extension(prompt, video_path, duration, video_url=None, video_model=None):
    cfg = config()
    model = valid_video_model(video_model, cfg)
    file_id, file_payload = xai_upload_file(video_path)
    payload = {
        "model": model,
        "prompt": prompt,
        "video": {"file_id": file_id},
        "duration": min(10, duration),
    }
    start = requests.post(
        cfg["api_base"] + "/videos/extensions",
        headers=xai_headers(),
        json=payload,
        timeout=120,
    )
    if start.status_code >= 400:
        raise RuntimeError(f"영상 연장 요청 실패: {start.status_code} {response_error_detail(start)}")
    request_id = (start.json() or {}).get("request_id")
    if not request_id:
        raise RuntimeError("영상 연장 요청 ID를 받지 못했습니다.")
    path, extra = poll_video_request(request_id)
    extra["video_model"] = model
    extra["extension_api"] = True
    extra["input_video_url"] = video_url
    extra["input_mode"] = "file_id"
    extra["input_file_id"] = file_id
    extra["input_file"] = file_payload
    if duration > 10:
        extra["requested_duration"] = duration
        extra["duration_clamped_to"] = 10
    return path, extra


def poll_video_request(request_id):
    cfg = config()
    for _ in range(90):
        poll = requests.get(cfg["api_base"] + f"/videos/{request_id}", headers=xai_auth_header(), timeout=60)
        if poll.status_code >= 400:
            raise RuntimeError(f"영상 상태 조회 실패: {poll.status_code} {response_error_detail(poll)}")
        data = poll.json() or {}
        record_usage(data.get("usage"))
        status = data.get("status")
        if status == "done":
            url = ((data.get("video") or {}).get("url"))
            if not url:
                raise RuntimeError("완료 응답에 영상 URL이 없습니다.")
            dest = media_path("video", f"{now_stamp()}-{uuid.uuid4().hex}.mp4")
            video = requests.get(url, timeout=240)
            video.raise_for_status()
            dest.write_bytes(video.content)
            return dest, {"request_id": request_id, "remote_url": url}
        if status in {"failed", "expired"}:
            detail = data.get("error") or data.get("message") or data.get("detail") or data
            raise RuntimeError(f"영상 요청이 {status} 상태로 종료되었습니다: {json.dumps(detail, ensure_ascii=False)[:1200]}")
        time.sleep(5)
    raise RuntimeError("영상 생성 대기 시간이 초과되었습니다.")

def cents_value(obj):
    if isinstance(obj, dict):
        return int(obj.get("val") or 0)
    return int(obj or 0)


def management_headers():
    cfg = config()
    if not cfg["management_key"]:
        raise RuntimeError("Management API 키가 설정되지 않았습니다.")
    return {"Authorization": f"Bearer {cfg['management_key']}", "Content-Type": "application/json"}


def prepaid_balance():
    cfg = config()
    if not cfg["management_key"] or not cfg["team_id"]:
        return None
    response = requests.get(
        cfg["management_base"] + f"/v1/billing/teams/{cfg['team_id']}/prepaid/balance",
        headers=management_headers(),
        timeout=30,
    )
    response.raise_for_status()
    data = response.json() or {}
    cents = abs(cents_value(data.get("total")))
    return {"cents": cents, "usd": round(cents / 100, 2), "raw": data}


def grok_oauth_quota():
    token = hermes_xai_oauth_token() or oauth_access_token()
    if not token:
        return {
            "available_via_api": False,
            "usage_url": "https://grok.com/?_s=usage",
            "message": "Hermes xAI OAuth 또는 Grok OAuth 로그인이 필요합니다.",
        }
    response = requests.get(
        "https://cli-chat-proxy.grok.com/v1/billing",
        headers={"Authorization": f"Bearer {token}"},
        timeout=20,
    )
    response.raise_for_status()
    data = response.json() or {}
    cfg = data.get("config") or {}

    def value_of(obj):
        if isinstance(obj, dict):
            return int(obj.get("val") or 0)
        return int(obj or 0)

    monthly_limit = value_of(cfg.get("monthlyLimit"))
    used = value_of(cfg.get("used"))
    remaining = max(0, monthly_limit - used) if monthly_limit else 0
    used_percent = round((used / monthly_limit) * 100, 1) if monthly_limit else None
    remaining_percent = round((remaining / monthly_limit) * 100, 1) if monthly_limit else None
    return {
        "available_via_api": True,
        "usage_url": "https://grok.com/?_s=usage",
        "monthly_limit": monthly_limit,
        "used": used,
        "remaining": remaining,
        "used_percent": used_percent,
        "remaining_percent": remaining_percent,
        "raw_config_keys": sorted(cfg.keys()),
        "source": "cli-chat-proxy.grok.com",
    }


def validate_inference_key():
    cfg = config()
    response = requests.get(
        cfg["api_base"] + "/models",
        headers={"Authorization": xai_headers()["Authorization"]},
        timeout=30,
    )
    response.raise_for_status()
    return True


@app.get("/")
def index():
    response = make_response(render_template("index.html"))
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    return response


@app.get("/settings")
def settings_page():
    response = make_response(render_template("index.html"))
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    return response


@app.get("/health")
def health():
    cfg = config()
    usage = read_usage()
    oauth_token = read_oauth_token()
    hermes_logged_in = False
    hermes_proxy_running = False
    if cfg["provider"] == "hermes_proxy":
        hermes_logged_in, _ = hermes_auth_logged_in()
        hermes_proxy_running = port_open("127.0.0.1", 8645)
    codex_running = codex_proxy_running(cfg)
    return jsonify({
        "ok": True,
        "mode": cfg["mode"],
        "provider": cfg["provider"],
        "hermes_configured": bool(cfg["hermes_base_url"]),
        "hermes_base_url": cfg["hermes_base_url"],
        "openai_configured": bool(cfg["openai_api_key"]),
        "codex_proxy_configured": bool(cfg["codex_proxy_base_url"]),
        "codex_proxy_base_url": cfg["codex_proxy_base_url"],
        "codex_proxy_running": codex_running,
        "hermes_logged_in": hermes_logged_in,
        "hermes_proxy_running": hermes_proxy_running,
        "api_key_configured": bool(cfg["api_key"]),
        "oauth_configured": bool(oauth_token and oauth_token.get("access_token")),
        "oauth_expires_at": oauth_token.get("expires_at") if oauth_token else None,
        "authenticated": bool(
            (cfg["provider"] == "hermes_proxy" and hermes_logged_in and hermes_proxy_running)
            or (cfg["provider"] == "openai_api" and cfg["openai_api_key"])
            or (cfg["provider"] == "codex_proxy" and codex_running)
            or session.get("xai_api_key")
        ),
        "management_configured": bool(cfg["management_key"] and cfg["team_id"]),
        "media_root": str(media_root()),
        "usage": usage,
        "models": {
            "image": cfg["image_model"],
            "openai_image": cfg["openai_image_model"],
            "codex_image": cfg["codex_image_model"],
            "video": cfg["video_model"],
            "vision": cfg["vision_model"],
        },
        "last_error": LAST_ERROR,
    })


@app.get("/api/error-log")
def error_log():
    return jsonify({"ok": True, "last_error": LAST_ERROR})


@app.get("/api/oauth/quota")
def oauth_quota():
    try:
        return jsonify({"ok": True, "quota": grok_oauth_quota()})
    except requests.HTTPError as exc:
        detail = exc.response.text if exc.response is not None else str(exc)
        return safe_error(f"Grok OAuth billing 조회에 실패했습니다: {detail}", status=502)
    except Exception as exc:
        return safe_error(f"Grok OAuth billing 조회에 실패했습니다: {exc}", status=502)


@app.post("/api/auth/login")
def auth_login():
    data = request.get_json(silent=True) or {}
    api_key = (data.get("api_key") or "").strip()
    management_key = (data.get("management_key") or "").strip()
    team_id = (data.get("team_id") or "").strip()
    if not api_key:
        return safe_error("xAI API 키를 입력해 주세요.")
    session["xai_api_key"] = api_key
    session["xai_management_key"] = management_key
    session["xai_team_id"] = team_id
    session["webgork_mode"] = "live"
    return jsonify({"ok": True, "status": auth_status_payload(include_balance=True)})


@app.get("/api/auth/xai/start")
def auth_xai_start():
    return redirect("https://console.x.ai/team/default/api-keys", code=302)


@app.get("/api/auth/oauth/start")
def oauth_start():
    cfg = config()
    if not cfg["oauth_client_id"]:
        return safe_error("직접 OAuth Client ID가 설정되어 있지 않습니다. Version 3에서는 Hermes Agent Proxy 사용을 권장합니다.", status=400)
    endpoints = oauth_discovery()
    ensure_oauth_callback_server()
    verifier, challenge = pkce_pair()
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    session["xai_oauth_state"] = state
    session["xai_oauth_verifier"] = verifier
    session["xai_oauth_nonce"] = nonce
    OAUTH_PENDING[state] = {
        "verifier": verifier,
        "redirect_uri": cfg["oauth_redirect_uri"],
        "created_at": int(time.time()),
    }
    params = {
        "response_type": "code",
        "client_id": cfg["oauth_client_id"],
        "redirect_uri": cfg["oauth_redirect_uri"],
        "scope": cfg["oauth_scope"],
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "state": state,
        "nonce": nonce,
        "plan": "generic",
        "referrer": "webgork-studio",
    }
    return redirect(endpoints["authorization_endpoint"] + "?" + urlencode(params), code=302)


@app.get("/api/auth/oauth/callback")
def oauth_callback():
    error = request.args.get("error")
    if error:
        return render_template("oauth_result.html", ok=False, message=f"OAuth 오류: {error}")
    state = request.args.get("state")
    code = request.args.get("code")
    if not code or state != session.get("xai_oauth_state"):
        return render_template("oauth_result.html", ok=False, message="OAuth state 검증에 실패했습니다.")
    try:
        oauth_exchange_code(code, session.get("xai_oauth_verifier"), config()["oauth_redirect_uri"])
    except Exception as exc:
        return render_template("oauth_result.html", ok=False, message=f"토큰 교환 실패: {exc}")
    session["webgork_mode"] = "live"
    for key in ("xai_oauth_state", "xai_oauth_verifier", "xai_oauth_nonce"):
        session.pop(key, None)
    return render_template("oauth_result.html", ok=True, message="Grok OAuth 로그인이 완료되었습니다. 이제 이 창을 닫고 WebGUI.v3으로 돌아가세요.")


@app.post("/api/auth/logout")
def auth_logout():
    for key in ("xai_api_key", "xai_management_key", "xai_team_id", "webgork_mode"):
        session.pop(key, None)
    clear_oauth_token()
    return jsonify({"ok": True})


def auth_status_payload(include_balance=False):
    cfg = config()
    payload = {
        "authenticated": bool(
            cfg["provider"] == "hermes_proxy" and cfg["hermes_base_url"]
            or cfg["provider"] == "openai_api" and cfg["openai_api_key"]
            or cfg["provider"] == "codex_proxy" and cfg["codex_proxy_base_url"]
            or cfg["api_key"]
            or read_oauth_token()
        ),
        "session_login": bool(session.get("xai_api_key")),
        "api_key_configured": bool(cfg["api_key"]),
        "provider": cfg["provider"],
        "hermes_configured": bool(cfg["hermes_base_url"]),
        "hermes_base_url": cfg["hermes_base_url"],
        "openai_configured": bool(cfg["openai_api_key"]),
        "codex_proxy_configured": bool(cfg["codex_proxy_base_url"]),
        "codex_proxy_base_url": cfg["codex_proxy_base_url"],
        "codex_proxy_running": codex_proxy_running(cfg),
        "oauth_configured": bool(read_oauth_token()),
        "management_configured": bool(cfg["management_key"] and cfg["team_id"]),
        "mode": cfg["mode"],
        "media_root": str(media_root()),
        "models": {
            "image": cfg["image_model"],
            "openai_image": cfg["openai_image_model"],
            "codex_image": cfg["codex_image_model"],
            "video": cfg["video_model"],
            "vision": cfg["vision_model"],
        },
        "usage": read_usage(),
        "balance": None,
        "balance_error": None,
    }
    if include_balance and payload["management_configured"]:
        try:
            payload["balance"] = prepaid_balance()
        except Exception as exc:
            payload["balance_error"] = str(exc)[:300]
    return payload


@app.get("/api/auth/status")
def auth_status():
    return jsonify({"ok": True, **auth_status_payload(include_balance=True)})


@app.post("/api/hermes/auth/start")
def hermes_auth_start():
    exe = hermes_exe_path()
    if not exe.exists():
        return safe_error("Hermes 실행 파일을 찾을 수 없습니다. V3 Hermes 설치를 먼저 확인해 주세요.", status=400)
    logged_in, detail = hermes_auth_logged_in()
    if logged_in:
        ensure_hermes_proxy_background()
        return jsonify({"ok": True, "already_logged_in": True, "status": detail, **hermes_login_snapshot()})
    with HERMES_LOGIN_LOCK:
        existing = HERMES_LOGIN_STATE.get("process")
        if existing and existing.poll() is None:
            return jsonify({"ok": True, "already_running": True, **hermes_login_snapshot()})
        HERMES_LOGIN_STATE["lines"] = []
        HERMES_LOGIN_STATE["auth_url"] = ""
        HERMES_LOGIN_STATE["started_at"] = time.time()
        try:
            process = subprocess.Popen(
                [str(exe), "auth", "add", "xai-oauth", "--type", "oauth", "--manual-paste", "--no-browser"],
                cwd=str(ROOT),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                **hidden_process_kwargs(),
            )
        except Exception as exc:
            return safe_error("Hermes 인증 프로세스를 시작하지 못했습니다.", detail=str(exc), status=500)
        HERMES_LOGIN_STATE["process"] = process
        Thread(target=read_hermes_login_output, args=(process,), daemon=True).start()
    for _ in range(40):
        snapshot = hermes_login_snapshot()
        if snapshot["auth_url"]:
            return jsonify({"ok": True, **snapshot})
        if not snapshot["running"]:
            break
        time.sleep(0.25)
    return jsonify({"ok": True, **hermes_login_snapshot()})


@app.get("/api/hermes/auth/status")
def hermes_auth_ui_status():
    logged_in, detail = hermes_auth_logged_in()
    proxy_ok = port_open("127.0.0.1", 8645)
    return jsonify({
        "ok": True,
        "logged_in": logged_in,
        "status": detail,
        "proxy_running": proxy_ok,
        **hermes_login_snapshot(),
    })


@app.post("/api/hermes/auth/submit")
def hermes_auth_submit():
    data = request.get_json(force=True, silent=True) or {}
    code = (data.get("code") or "").strip()
    if not code:
        return safe_error("인증 코드를 입력해 주세요.")
    with HERMES_LOGIN_LOCK:
        process = HERMES_LOGIN_STATE.get("process")
    if not process or process.poll() is not None or not process.stdin:
        return safe_error("진행 중인 Hermes 인증이 없습니다. 인증 시작을 다시 눌러 주세요.", status=400)
    try:
        process.stdin.write(code + "\n")
        process.stdin.flush()
    except Exception as exc:
        return safe_error("Hermes 인증 코드 전달에 실패했습니다.", detail=str(exc), status=500)
    deadline = time.time() + 45
    while time.time() < deadline and process.poll() is None:
        time.sleep(0.5)
    logged_in, detail = hermes_auth_logged_in()
    proxy_started = False
    proxy_message = ""
    if logged_in:
        proxy_started, proxy_message = ensure_hermes_proxy_background()
    return jsonify({
        "ok": logged_in,
        "logged_in": logged_in,
        "status": detail,
        "proxy_started": proxy_started,
        "proxy_message": proxy_message,
        **hermes_login_snapshot(),
    })


@app.post("/api/hermes/auth/logout")
def hermes_auth_logout():
    try:
        result = hermes_auth_logout_state()
        return jsonify({"ok": True, **result, **hermes_login_snapshot()})
    except Exception as exc:
        return safe_error("Hermes OAuth 로그아웃에 실패했습니다.", exc, 502)


@app.post("/api/hermes/auth/reset")
def hermes_auth_reset():
    try:
        result = hermes_auth_reset_state()
        return jsonify({"ok": True, **result, **hermes_login_snapshot()})
    except Exception as exc:
        return safe_error("Hermes OAuth 상태 리셋에 실패했습니다.", exc, 502)


@app.post("/api/hermes/proxy/start")
def hermes_proxy_start():
    ok, message = ensure_hermes_proxy_background()
    if not ok:
        return safe_error("Hermes Proxy 시작에 실패했습니다.", detail=message, status=500)
    return jsonify({"ok": True, "message": message, "proxy_running": port_open("127.0.0.1", 8645)})


@app.get("/api/settings")
def get_settings():
    return jsonify({"ok": True, "settings": {**read_settings(), "media_root": str(media_root())}})


@app.post("/api/settings/provider")
def set_provider_settings():
    data = request.get_json(silent=True) or {}
    provider = (data.get("provider") or "direct").strip().lower()
    if provider not in {"direct", "hermes_proxy", "openai_api", "codex_proxy"}:
        return safe_error("지원하지 않는 provider입니다.")
    settings = read_settings()
    settings["provider"] = provider
    settings["hermes_base_url"] = (data.get("hermes_base_url") or "").strip().rstrip("/")
    hermes_key = (data.get("hermes_api_key") or "").strip()
    if hermes_key:
        settings["hermes_api_key"] = hermes_key
    elif data.get("clear_hermes_api_key"):
        settings.pop("hermes_api_key", None)
    openai_key = (data.get("openai_api_key") or "").strip()
    if openai_key:
        settings["openai_api_key"] = openai_key
    elif data.get("clear_openai_api_key"):
        settings.pop("openai_api_key", None)
    codex_base = (data.get("codex_proxy_base_url") or "").strip().rstrip("/")
    if codex_base:
        settings["codex_proxy_base_url"] = codex_base
    elif data.get("clear_codex_proxy_base_url"):
        settings.pop("codex_proxy_base_url", None)
    write_settings(settings)
    return jsonify({"ok": True, "settings": {
        **settings,
        "hermes_api_key": bool(settings.get("hermes_api_key")),
        "openai_api_key": bool(settings.get("openai_api_key")),
        "codex_proxy_base_url": settings.get("codex_proxy_base_url") or "",
    }})


@app.post("/api/codex-proxy/start")
def codex_proxy_start():
    result = start_codex_proxy_background()
    if not result.get("ok"):
        return safe_error(result.get("error") or "Codex OAuth 프록시를 시작하지 못했습니다.", result.get("detail"), result.get("status", 500))
    return jsonify(result)


def start_codex_proxy_background():
    global CODEX_PROXY_PROCESS
    cfg = config()
    if codex_proxy_running(cfg):
        return {"ok": True, "message": "Codex OAuth 프록시가 이미 실행 중입니다.", "proxy_running": True, "url": cfg["codex_proxy_base_url"]}
    if CODEX_PROXY_PROCESS and CODEX_PROXY_PROCESS.poll() is None:
        return {"ok": True, "message": "Codex OAuth 프록시 시작 대기 중입니다.", "proxy_running": False, "url": cfg["codex_proxy_base_url"]}
    command = resolve_codex_proxy_command()
    if not command:
        return {
            "ok": False,
            "error": "Codex OAuth 프록시 실행 파일을 찾을 수 없습니다.",
            "detail": "npm/npx가 포함된 Node.js를 설치하거나, 별도 터미널에서 npx ima2-gen serve를 실행한 뒤 Codex OAuth Proxy URL에 해당 주소를 넣어 주세요.",
            "status": 400,
        }
    try:
        ima2_config_dir = ensure_codex_proxy_oauth_config()
        env = os.environ.copy()
        env["IMA2_CONFIG_DIR"] = str(ima2_config_dir)
        env["IMA2_GENERATED_DIR"] = str(media_path("image"))
        env["IMA2_ADVERTISE_FILE"] = str(ima2_config_dir / "server.json")
        node_dir = str(Path(os.getenv("ProgramFiles", r"C:\Program Files")) / "nodejs")
        env["PATH"] = node_dir + os.pathsep + env.get("PATH", "")
        CODEX_PROXY_PROCESS = subprocess.Popen(
            command,
            cwd=str(ROOT),
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
    except Exception as exc:
        return {"ok": False, "error": "Codex OAuth 프록시를 시작하지 못했습니다.", "detail": error_detail_text(exc), "status": 500}
    for _ in range(20):
        time.sleep(0.5)
        refreshed = {**cfg, "codex_proxy_base_url": discover_codex_proxy_url() or cfg["codex_proxy_base_url"]}
        if codex_proxy_running(refreshed):
            settings = read_settings()
            if refreshed["codex_proxy_base_url"]:
                settings["codex_proxy_base_url"] = refreshed["codex_proxy_base_url"]
                write_settings(settings)
            return {"ok": True, "message": "Codex OAuth 프록시가 실행되었습니다.", "proxy_running": True, "url": refreshed["codex_proxy_base_url"]}
    return {"ok": True, "message": "Codex OAuth 프록시를 백그라운드에서 시작했습니다. Codex 로그인이 필요하면 npx @openai/codex login을 먼저 진행해 주세요.", "proxy_running": False, "url": cfg["codex_proxy_base_url"]}


@app.get("/api/codex-proxy/status")
def codex_proxy_status():
    return jsonify({"ok": True, **codex_proxy_status_payload()})


@app.post("/api/settings/hermes-test")
def hermes_test():
    cfg = config()
    if cfg["provider"] != "hermes_proxy" or not cfg["hermes_base_url"]:
        return safe_error("Hermes Proxy Base URL을 먼저 설정해 주세요.")
    headers = xai_auth_header()
    candidates = ["/health", "/v1/models", "/models"]
    errors = []
    for path in candidates:
        url = cfg["hermes_base_url"].rstrip("/") + path
        try:
            response = requests.get(url, headers=headers, timeout=15)
            if response.status_code < 500:
                return jsonify({
                    "ok": response.status_code < 400,
                    "status_code": response.status_code,
                    "url": url,
                    "detail": response.text[:700],
                })
            errors.append(f"{url}: {response.status_code}")
        except Exception as exc:
            errors.append(f"{url}: {str(exc)[:160]}")
    return safe_error("Hermes Proxy 연결 테스트에 실패했습니다.", "; ".join(errors), 502)


@app.post("/api/settings/media-root")
def set_media_root():
    data = request.get_json(silent=True) or {}
    raw_path = (data.get("media_root") or "").strip()
    if not raw_path:
        return safe_error("저장 경로를 입력해 주세요.")
    target = Path(raw_path).expanduser().resolve()
    try:
        target.mkdir(parents=True, exist_ok=True)
        probe = target / ".webgork-write-test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except OSError as exc:
        return safe_error("저장 경로를 만들거나 쓸 수 없습니다.", exc, 400)
    old_root = media_root()
    try:
        merge_copy_tree(old_root, target)
        ensure_media_dirs_for(target)
    except OSError as exc:
        return safe_error("저장 경로로 기존 라이브러리를 옮기지 못했습니다.", exc, 500)
    settings = read_settings()
    settings["media_root"] = str(target)
    write_settings(settings)
    return jsonify({"ok": True, "media_root": str(media_root())})


@app.post("/api/settings/browse-media-root")
def browse_media_root():
    try:
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        selected = filedialog.askdirectory(
            title="WebGUI.v3 결과물 저장 폴더 선택",
            initialdir=str(media_root()),
        )
        root.destroy()
    except Exception as exc:
        selected_path = str(media_root()).replace("'", "''")
        script = (
            "Add-Type -AssemblyName System.Windows.Forms; "
            "$d = New-Object System.Windows.Forms.FolderBrowserDialog; "
            "$d.Description = 'WebGUI.v3 결과물 저장 폴더 선택'; "
            f"$d.SelectedPath = '{selected_path}'; "
            "if ($d.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) { "
            "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; "
            "Write-Output $d.SelectedPath }"
        )
        try:
            completed = subprocess.run(
                ["powershell.exe", "-NoProfile", "-STA", "-Command", script],
                capture_output=True,
                text=True,
                timeout=300,
            )
            if completed.returncode != 0:
                return safe_error("Windows 폴더 선택 창을 열 수 없습니다.", completed.stderr or exc, 500)
            selected = completed.stdout.strip()
        except Exception as fallback_exc:
            return safe_error("Windows 폴더 선택 창을 열 수 없습니다.", fallback_exc, 500)
    if not selected:
        return jsonify({"ok": True, "cancelled": True, "media_root": str(media_root())})
    target = Path(selected).expanduser().resolve()
    try:
        target.mkdir(parents=True, exist_ok=True)
        probe = target / ".webgork-write-test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except OSError as exc:
        return safe_error("선택한 저장 경로에 쓸 수 없습니다.", exc, 400)
    old_root = media_root()
    try:
        merge_copy_tree(old_root, target)
        ensure_media_dirs_for(target)
    except OSError as exc:
        return safe_error("저장 경로로 기존 라이브러리를 옮기지 못했습니다.", exc, 500)
    settings = read_settings()
    settings["media_root"] = str(target)
    write_settings(settings)
    return jsonify({"ok": True, "media_root": str(media_root())})


@app.post("/api/prompt-plan")
def prompt_plan():
    payload = request.get_json(silent=True) or {}
    prompt = (payload.get("prompt") or "").strip()
    if not prompt:
        return safe_error("플래너에 보낼 프롬프트를 입력해 주세요.")
    context = {
        "task": (payload.get("task") or payload.get("endpoint") or "generation").strip(),
        "target_model": (payload.get("target_model") or "").strip(),
        "aspect_ratio": (payload.get("aspect_ratio") or "").strip(),
        "resolution": (payload.get("resolution") or "").strip(),
        "duration": str(payload.get("duration") or "").strip(),
        "source_count": str(payload.get("source_count") or "").strip(),
    }
    try:
        planned, extra = plan_generation_prompt(prompt, context)
        return jsonify({
            "ok": True,
            "original_prompt": prompt,
            "planned_prompt": planned,
            "changed": planned != prompt,
            "context": context,
            **extra,
        })
    except Exception as exc:
        return safe_error("프롬프트 플래너 실행에 실패했습니다.", exc, 502)


@app.get("/api/prompts")
def prompt_library():
    items = [prompt_item_response(item) for item in read_prompts()]
    items.sort(key=lambda item: (bool(item.get("favorite")), item.get("updated_at") or ""), reverse=True)
    tags = sorted({tag for item in items for tag in item.get("tags", [])}, key=str.lower)
    return jsonify({"ok": True, "items": items, "tags": tags, "tasks": PROMPT_TASKS})


@app.post("/api/prompts")
def save_prompt_item():
    payload = request.get_json(silent=True) or {}
    prompt = str(payload.get("prompt") or "").strip()
    structured = normalize_prompt_structure(payload.get("structured"))
    if not prompt and structured:
        prompt = "\n".join(value for value in structured.values() if value).strip()
    if not prompt:
        return safe_error("저장할 프롬프트를 입력해 주세요.")

    item_id = str(payload.get("id") or "").strip()
    items = read_prompts()
    now = datetime.now(timezone.utc).isoformat()
    incoming = normalize_prompt_item({
        "id": item_id or uuid.uuid4().hex,
        "title": payload.get("title"),
        "task": payload.get("task"),
        "prompt": prompt,
        "structured": structured,
        "tags": payload.get("tags"),
        "favorite": parse_request_bool(payload.get("favorite")),
        "created_at": now,
        "updated_at": now,
        "source_item_id": payload.get("source_item_id"),
        "source_file_path": payload.get("source_file_path"),
    })

    for index, item in enumerate(items):
        if item.get("id") != item_id:
            continue
        previous = normalize_prompt_item(item)
        versions = list(previous.get("versions") or [])
        changed = (
            previous.get("prompt") != incoming.get("prompt")
            or previous.get("structured") != incoming.get("structured")
            or previous.get("title") != incoming.get("title")
            or previous.get("tags") != incoming.get("tags")
        )
        if changed:
            versions.append({
                "at": previous.get("updated_at") or now,
                "title": previous.get("title"),
                "prompt": previous.get("prompt"),
                "structured": previous.get("structured"),
                "tags": previous.get("tags"),
            })
        incoming["created_at"] = previous.get("created_at") or now
        incoming["usage_count"] = previous.get("usage_count") or 0
        incoming["last_used_at"] = previous.get("last_used_at")
        incoming["source_item_id"] = incoming.get("source_item_id") or previous.get("source_item_id")
        incoming["source_file_path"] = incoming.get("source_file_path") or previous.get("source_file_path")
        incoming["versions"] = versions[-30:]
        items[index] = incoming
        write_prompts(items)
        return jsonify({"ok": True, "item": prompt_item_response(incoming), "created": False})

    items.insert(0, incoming)
    write_prompts(items)
    return jsonify({"ok": True, "item": prompt_item_response(incoming), "created": True})


@app.post("/api/prompts/favorite")
def favorite_prompt_item():
    payload = request.get_json(silent=True) or {}
    item_id = str(payload.get("id") or "").strip()
    favorite = parse_request_bool(payload.get("favorite"))
    if not item_id:
        return safe_error("프롬프트를 찾을 수 없습니다.", status=404)
    items = read_prompts()
    for item in items:
        if item.get("id") == item_id:
            item["favorite"] = favorite
            item["updated_at"] = datetime.now(timezone.utc).isoformat()
            write_prompts(items)
            return jsonify({"ok": True, "id": item_id, "favorite": favorite})
    return safe_error("프롬프트를 찾을 수 없습니다.", status=404)


@app.post("/api/prompts/use")
def use_prompt_item():
    payload = request.get_json(silent=True) or {}
    item_id = str(payload.get("id") or "").strip()
    items = read_prompts()
    now = datetime.now(timezone.utc).isoformat()
    for item in items:
        if item.get("id") == item_id:
            item["usage_count"] = int(item.get("usage_count") or 0) + 1
            item["last_used_at"] = now
            item["updated_at"] = now
            write_prompts(items)
            return jsonify({"ok": True, "item": prompt_item_response(item)})
    return safe_error("프롬프트를 찾을 수 없습니다.", status=404)


@app.post("/api/prompts/delete")
def delete_prompt_items():
    payload = request.get_json(silent=True) or {}
    ids = set(str(item) for item in (payload.get("ids") or []) if item)
    if not ids:
        return safe_error("삭제할 프롬프트를 선택해 주세요.")
    items = read_prompts()
    keep = [item for item in items if item.get("id") not in ids]
    write_prompts(keep)
    return jsonify({"ok": True, "deleted": len(items) - len(keep)})


@app.post("/api/prompts/from-library")
def save_prompt_from_library():
    payload = request.get_json(silent=True) or {}
    item = find_library_item_by_id(payload.get("id"))
    if not item:
        return safe_error("라이브러리 항목을 찾을 수 없습니다.", status=404)
    prompt = str(item.get("prompt") or "").strip()
    if not prompt or prompt.startswith("("):
        return safe_error("저장할 프롬프트가 없는 라이브러리 항목입니다.")
    kind = item.get("kind") or "general"
    task = "video" if kind == "video" else ("edit" if kind == "edit" else "image")
    title = str(payload.get("title") or prompt[:60] or "라이브러리 프롬프트").strip()
    now = datetime.now(timezone.utc).isoformat()
    prompt_item = normalize_prompt_item({
        "title": title,
        "task": task,
        "prompt": prompt,
        "tags": ["library", task],
        "favorite": False,
        "created_at": now,
        "updated_at": now,
        "source_item_id": item.get("id"),
        "source_file_path": item.get("file_path"),
    })
    items = read_prompts()
    items.insert(0, prompt_item)
    write_prompts(items)
    return jsonify({"ok": True, "item": prompt_item_response(prompt_item)})


@app.get("/api/video-templates")
def video_template_library():
    items = [video_template_response(item) for item in read_video_templates()]
    items.sort(key=lambda item: (bool(item.get("favorite")), item.get("updated_at") or ""), reverse=True)
    tags = sorted({tag for item in items for tag in item.get("tags", [])}, key=str.lower)
    return jsonify({
        "ok": True,
        "items": items,
        "tags": tags,
        "methods": VIDEO_TEMPLATE_METHODS,
    })


@app.post("/api/video-templates")
def save_video_template():
    payload = request.get_json(silent=True) or {}
    item_id = str(payload.get("id") or "").strip()
    items = read_video_templates()
    now = datetime.now(timezone.utc).isoformat()
    incoming = normalize_video_template({
        **payload,
        "id": item_id or uuid.uuid4().hex,
        "created_at": now,
        "updated_at": now,
    })

    for index, item in enumerate(items):
        if item.get("id") != item_id:
            continue
        previous = normalize_video_template(item)
        incoming["created_at"] = previous.get("created_at") or now
        incoming["updated_at"] = now
        items[index] = incoming
        write_video_templates(items)
        return jsonify({"ok": True, "item": video_template_response(incoming), "created": False})

    items.insert(0, incoming)
    write_video_templates(items)
    return jsonify({"ok": True, "item": video_template_response(incoming), "created": True})


@app.post("/api/video-templates/delete")
def delete_video_templates():
    payload = request.get_json(silent=True) or {}
    ids = set(str(item) for item in (payload.get("ids") or []) if item)
    if not ids:
        return safe_error("삭제할 템플릿을 선택해 주세요.")
    items = read_video_templates()
    keep = [item for item in items if item.get("id") not in ids]
    write_video_templates(keep)
    return jsonify({"ok": True, "deleted": len(items) - len(keep)})


@app.get("/api/video-template-blocks")
def video_template_block_library():
    items = [template_block_response(item) for item in read_template_blocks()]
    items.sort(key=lambda item: (bool(item.get("favorite")), item.get("updated_at") or ""), reverse=True)
    tags = sorted({tag for item in items for tag in item.get("tags", [])}, key=str.lower)
    return jsonify({
        "ok": True,
        "items": items,
        "tags": tags,
        "methods": VIDEO_TEMPLATE_METHODS,
    })


@app.post("/api/video-template-blocks")
def save_video_template_block():
    payload = request.get_json(silent=True) or {}
    item_id = str(payload.get("id") or "").strip()
    items = read_template_blocks()
    now = datetime.now(timezone.utc).isoformat()
    incoming = normalize_template_block({
        **payload,
        "id": item_id or uuid.uuid4().hex,
        "created_at": now,
        "updated_at": now,
    })

    for index, item in enumerate(items):
        if item.get("id") != item_id:
            continue
        previous = normalize_template_block(item)
        incoming["created_at"] = previous.get("created_at") or now
        incoming["updated_at"] = now
        items[index] = incoming
        write_template_blocks(items)
        return jsonify({"ok": True, "item": template_block_response(incoming), "created": False})

    items.insert(0, incoming)
    write_template_blocks(items)
    return jsonify({"ok": True, "item": template_block_response(incoming), "created": True})


@app.post("/api/video-template-blocks/delete")
def delete_video_template_blocks():
    payload = request.get_json(silent=True) or {}
    ids = set(str(item) for item in (payload.get("ids") or []) if item)
    if not ids:
        return safe_error("삭제할 블록을 선택해 주세요.")
    items = read_template_blocks()
    keep = [item for item in items if item.get("id") not in ids]
    write_template_blocks(keep)
    return jsonify({"ok": True, "deleted": len(items) - len(keep)})


@app.post("/api/t2i")
def t2i():
    payload = request.get_json(silent=True) or {}
    prompt = (payload.get("prompt") or request.form.get("prompt") or "").strip()
    aspect_ratio = valid_aspect_ratio(payload.get("aspect_ratio") or request.form.get("aspect_ratio"))
    image_resolution = valid_image_resolution(payload.get("image_resolution") or request.form.get("image_resolution"))
    cfg = config()
    if not prompt:
        return safe_error("프롬프트를 입력해 주세요.")
    try:
        image_provider, image_model = selected_image_backend(payload.get("image_model") or request.form.get("image_model"), cfg)
        if cfg["mode"] == "live":
            path, extra = live_image(
                prompt,
                media_path("image"),
                aspect_ratio=aspect_ratio,
                resolution=image_resolution,
                image_model=image_model,
                image_provider=image_provider,
            )
        else:
            path, extra = mock_svg(media_path("image"), "Text to Image", prompt), {"aspect_ratio": aspect_ratio, "image_resolution": image_resolution, "image_model": image_model, "image_provider": image_provider}
        extra.update(prompt_planner_request_metadata(payload, prompt))
        item = add_metadata("image", prompt, image_model, path, extra=extra)
        return jsonify({"ok": True, "item": item})
    except ValueError as exc:
        return safe_error(str(exc), status=400)
    except Exception as exc:
        return safe_error("이미지 생성에 실패했습니다.", exc, 502)


@app.post("/api/i2i")
def i2i():
    prompt = (request.form.get("prompt") or "").strip()
    aspect_ratio = valid_aspect_ratio(request.form.get("aspect_ratio"))
    image_resolution = valid_image_resolution(request.form.get("image_resolution"))
    edit_input_mode = valid_edit_input_mode(request.form.get("edit_input_mode"))
    manga_edit = (request.form.get("manga_edit") or "false").strip().lower() in {"1", "true", "on", "yes"}
    cfg = config()
    if not prompt:
        return safe_error("편집 프롬프트를 입력해 주세요.")
    try:
        image_provider, image_model = selected_image_backend(request.form.get("image_model"), cfg)
        sources, source_items = save_reference_images_or_library("image", "i2i", limit=3)
        edit_source = stitched_reference_image(sources) if edit_input_mode == "stitch" else sources[0]
        edit_sources = sources if edit_input_mode == "multi" and len(sources) > 1 else None
        output_dir = media_path("manga_trans") if manga_edit else media_path("image")
        source_name = Path(sources[0]).name
        if source_items and source_items[0]:
            source_name = (source_items[0].get("extra") or {}).get("original_name") or source_items[0].get("file_path") or source_name
        source_name = re.split(r"[\\/]", str(source_name))[-1]
        manga_prefix = f"grok_trans_{safe_output_stem(source_name, 1)}_" if manga_edit else ""
        if cfg["mode"] == "live":
            path, extra = live_image(
                prompt,
                output_dir,
                edit_source=None if edit_sources else edit_source,
                edit_sources=edit_sources,
                aspect_ratio=aspect_ratio,
                resolution=image_resolution,
                image_model=image_model,
                image_provider=image_provider,
            )
            if manga_prefix:
                path = prefixed_output_path(path, manga_prefix)
        else:
            path, extra = mock_svg(output_dir, "Image Edit", prompt, filename_prefix=manga_prefix), {
                "aspect_ratio": aspect_ratio,
                "image_resolution": image_resolution,
                "image_model": image_model,
                "image_provider": image_provider,
                "source_count": len(sources),
                "edit_input_mode": edit_input_mode,
            }
        extra.update({
            "source_image_path": public_path(sources[0]),
            "source_image_paths": [public_path(source) for source in sources],
            "image_provider": image_provider,
            "image_resolution": image_resolution,
            "experimental_image_resolution": image_resolution != "auto",
            "edit_input_mode": edit_input_mode,
            "api_multi_image_edit": bool(edit_sources),
            "stitched_source_path": public_path(edit_source) if edit_input_mode == "stitch" and edit_source != sources[0] else None,
            "stitched_before_edit": edit_input_mode == "stitch" and len(sources) > 1,
            "source_image_ids": [item.get("id") if item else None for item in source_items],
            "source_count": len(sources),
            "multi_image_edit": len(sources) > 1,
            "manga_edit": manga_edit,
            "manga_output_folder": "manga_trans" if manga_edit else None,
            "manga_filename_prefix": manga_prefix or None,
            "generation_type": "manga_live_translate" if manga_edit else extra.get("generation_type"),
        })
        extra.update(prompt_planner_request_metadata(request.form, prompt))
        item = add_metadata("edit", prompt, image_model, path, source_path=sources[0], extra=extra)
        return jsonify({"ok": True, "item": item})
    except ValueError as exc:
        return safe_error(str(exc), status=400)
    except Exception as exc:
        return safe_error("이미지 편집에 실패했습니다.", exc, 502)


def manga_batch_builtin_prompt(mode, target_language):
    if mode == "panel_realize":
        return manga_panel_realize_prompt()
    base = []
    if mode in {"live_translate", "live"}:
        base.append(
            "Convert the uploaded manga/comic page into a realistic live-action cinematic image. "
            "Preserve the original panel composition, character identities, poses, clothing, camera angle, scene layout, and emotional tone."
        )
    if mode in {"live_translate", "translate"}:
        base.append(
            f"Translate all visible comic text, speech bubbles, captions, and sound-effect text into {target_language}. "
            "Remove the original text cleanly and typeset the translated text back into the same bubbles or text areas. "
            "Keep the reading order natural, line breaks balanced, and lettering clean."
        )
    return "\n\n".join(base).strip()


def manga_batch_prompt(mode, target_language, extra_prompt, use_builtin_prompt=True, builtin_prompt_override=""):
    base = []
    override = (builtin_prompt_override or "").strip()
    if use_builtin_prompt:
        base_prompt = override or manga_batch_builtin_prompt(mode, target_language)
        if base_prompt:
            base.append(base_prompt)
    if extra_prompt:
        base.append(extra_prompt)
    return "\n\n".join(base).strip()


def safe_output_stem(name, index):
    stem = Path(name or "").stem or f"page-{index:03d}"
    safe = "".join("_" if char in '<>:"/\\|?*' or ord(char) < 32 else char for char in stem)
    safe = "_".join(safe.strip().split())
    safe = safe.strip("._")[:80]
    return safe or f"page-{index:03d}"


def manga_panel_realize_prompt(extra_prompt=""):
    base = (
        "Convert the first uploaded image, which is a single manga/comic panel crop, into a realistic live-action cinematic image. "
        "Preserve the panel's composition, camera angle, pose, body language, emotional tone, background layout, and story beat. "
        "If additional reference images are provided, use them only as character and style references for face shape, hair color, eye color, clothing colors, outfit details, and overall visual consistency. "
        "Do not copy the reference image composition unless it matches the manga panel. "
        "Do not add new characters or remove existing characters. "
        "Remove all visible text, speech bubbles, dialogue balloons, captions, sound-effect lettering, watermarks, and comic UI marks from the panel. "
        "Do not translate, rewrite, or invent any text. "
        "Cleanly inpaint the removed speech-bubble and text regions so the background, clothing, hair, skin, props, and lighting continue naturally with no blank balloon shapes or readable lettering left behind."
    )
    return f"{base}\n\nAdditional direction: {extra_prompt}".strip() if extra_prompt else base


def save_manga_reference_uploads():
    references = []
    ensure_media_dirs()
    for index, uploaded in enumerate(request.files.getlist("references"), start=1):
        if len(references) >= MANGA_PANEL_REFERENCE_LIMIT:
            break
        if not uploaded or not uploaded.filename:
            continue
        filename = secure_filename(uploaded.filename) or f"reference-{index}.png"
        suffix = Path(filename).suffix.lower()
        if suffix not in {".jpg", ".jpeg", ".png", ".webp"}:
            raise ValueError("레퍼런스는 jpg, png, webp 이미지만 업로드할 수 있습니다.")
        dest = media_path("uploads", f"{now_stamp()}-{index:03d}-{uuid.uuid4().hex}-manga-reference{suffix}")
        uploaded.save(dest)
        references.append({"index": index, "path": dest, "name": uploaded.filename})
    return references


def projection_bands(mask_values, threshold=0.965, min_width=3):
    bands = []
    start = None
    for index, ratio in enumerate(mask_values):
        if ratio >= threshold:
            if start is None:
                start = index
        elif start is not None:
            if index - start >= min_width:
                bands.append((start, index))
            start = None
    if start is not None and len(mask_values) - start >= min_width:
        bands.append((start, len(mask_values)))
    return bands


def best_panel_split_for_rect(gray, rect):
    left, top, right, bottom = rect
    width = right - left
    height = bottom - top
    if width < 260 or height < 260:
        return None
    crop = gray.crop(rect)
    sample = crop.copy()
    sample.thumbnail((720, 720))
    sw, sh = sample.size
    if sw < 80 or sh < 80:
        return None
    pixels = sample.load()

    col_ratios = []
    for x in range(sw):
        white = 0
        for y in range(sh):
            if pixels[x, y] >= 245:
                white += 1
        col_ratios.append(white / max(1, sh))

    row_ratios = []
    for y in range(sh):
        white = 0
        for x in range(sw):
            if pixels[x, y] >= 245:
                white += 1
        row_ratios.append(white / max(1, sw))

    candidates = []
    min_gutter = max(8, min(width, height) * 0.012)
    for axis, bands, total_sample, total_original in (
        ("vertical", projection_bands(col_ratios), sw, width),
        ("horizontal", projection_bands(row_ratios), sh, height),
    ):
        for start, end in bands:
            if start <= total_sample * 0.025 or end >= total_sample * 0.975:
                continue
            gutter_size = (end - start) / total_sample * total_original
            if gutter_size < min_gutter:
                continue
            split_at = int((start + end) / 2 / total_sample * total_original)
            if split_at < total_original * 0.18 or split_at > total_original * 0.82:
                continue
            candidates.append((gutter_size / total_original, gutter_size, axis, split_at))

    if not candidates:
        return None
    _, _, axis, split_at = max(candidates, key=lambda item: (item[0], item[1]))
    if axis == "vertical":
        x = left + split_at
        return [(left, top, x, bottom), (x, top, right, bottom)]
    y = top + split_at
    return [(left, top, right, y), (left, y, right, bottom)]


def overlap_ratio(box_a, box_b):
    left = max(box_a[0], box_b[0])
    top = max(box_a[1], box_b[1])
    right = min(box_a[2], box_b[2])
    bottom = min(box_a[3], box_b[3])
    if right <= left or bottom <= top:
        return 0
    inter = (right - left) * (bottom - top)
    area_a = max(1, (box_a[2] - box_a[0]) * (box_a[3] - box_a[1]))
    area_b = max(1, (box_b[2] - box_b[0]) * (box_b[3] - box_b[1]))
    return inter / min(area_a, area_b)


def detect_border_panel_rects(image):
    width, height = image.size
    gray = image.convert("L")
    sample = gray.copy()
    sample.thumbnail((1000, 1000))
    sw, sh = sample.size
    if sw < 120 or sh < 120:
        return []
    pixels = sample.load()
    visited = bytearray(sw * sh)
    candidates = []

    def offset(x, y):
        return y * sw + x

    for y in range(sh):
        for x in range(sw):
            idx = offset(x, y)
            if visited[idx] or pixels[x, y] > 82:
                visited[idx] = 1
                continue
            stack = [(x, y)]
            visited[idx] = 1
            min_x = max_x = x
            min_y = max_y = y
            count = 0
            while stack:
                cx, cy = stack.pop()
                count += 1
                if cx < min_x:
                    min_x = cx
                if cx > max_x:
                    max_x = cx
                if cy < min_y:
                    min_y = cy
                if cy > max_y:
                    max_y = cy
                for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
                    if nx < 0 or ny < 0 or nx >= sw or ny >= sh:
                        continue
                    nidx = offset(nx, ny)
                    if visited[nidx]:
                        continue
                    if pixels[nx, ny] <= 82:
                        visited[nidx] = 1
                        stack.append((nx, ny))
                    else:
                        visited[nidx] = 1
            bw = max_x - min_x + 1
            bh = max_y - min_y + 1
            if bw < sw * 0.16 or bh < sh * 0.10:
                continue
            fill_ratio = count / max(1, bw * bh)
            if fill_ratio > 0.35:
                continue
            min_pixels = max(45, int((bw + bh) * 0.35))
            if count < min_pixels:
                continue
            pad_x = max(2, int(sw * 0.003))
            pad_y = max(2, int(sh * 0.003))
            box = (
                int(max(0, min_x - pad_x) / sw * width),
                int(max(0, min_y - pad_y) / sh * height),
                int(min(sw, max_x + pad_x + 1) / sw * width),
                int(min(sh, max_y + pad_y + 1) / sh * height),
            )
            area = (box[2] - box[0]) * (box[3] - box[1])
            if area < width * height * 0.03:
                continue
            candidates.append(box)

    deduped = []
    for box in sorted(candidates, key=lambda item: (item[1], item[0], -(item[2] - item[0]) * (item[3] - item[1]))):
        if any(overlap_ratio(box, existing) > 0.82 for existing in deduped):
            continue
        deduped.append(box)
    return deduped[:48]


def detect_manga_panel_rects(image):
    width, height = image.size
    border_rects = detect_border_panel_rects(image)
    if len(border_rects) >= 2:
        return sorted(border_rects, key=lambda box: (box[1] // max(1, height // 20), box[0]))
    gray = image.convert("L")
    full_rect = (0, 0, width, height)
    min_area = width * height * 0.035

    def split_recursive(rect, depth=0):
        left, top, right, bottom = rect
        if depth >= 6 or (right - left) * (bottom - top) < min_area:
            return [rect]
        split = best_panel_split_for_rect(gray, rect)
        if not split:
            return [rect]
        return [child for part in split for child in split_recursive(part, depth + 1)]

    rects = split_recursive(full_rect)
    cleaned = []
    for left, top, right, bottom in rects[:48]:
        pad = max(2, int(min(width, height) * 0.002))
        box = (
            max(0, left + pad),
            max(0, top + pad),
            min(width, right - pad),
            min(height, bottom - pad),
        )
        if box[2] - box[0] >= 160 and box[3] - box[1] >= 160:
            cleaned.append(box)
    if not cleaned:
        cleaned = [full_rect]
    return sorted(cleaned, key=lambda box: (box[1] // max(1, height // 20), box[0]))


def extract_manga_panel_crops(page_path, page_index, original_name):
    try:
        from PIL import Image, ImageOps
    except Exception as exc:
        raise RuntimeError("컷 분리에는 Pillow 패키지가 필요합니다.") from exc

    with Image.open(page_path) as raw:
        image = ImageOps.exif_transpose(raw).convert("RGB")
        rects = detect_manga_panel_rects(image)
        panels = []
        stem = safe_output_stem(original_name, page_index)
        for panel_index, rect in enumerate(rects, start=1):
            crop = image.crop(rect)
            dest = media_path("manga_panels", f"{now_stamp()}-p{page_index:03d}-c{panel_index:03d}-{uuid.uuid4().hex}.png")
            dest.parent.mkdir(parents=True, exist_ok=True)
            crop.save(dest)
            panels.append({
                "index": panel_index,
                "path": dest,
                "name": f"{stem}_p{page_index:03d}_c{panel_index:03d}.png",
                "page_index": page_index,
                "panel_index": panel_index,
                "source_page_path": page_path,
                "source_page_name": original_name,
                "crop_box": rect,
            })
        return panels


def prefixed_output_path(path, prefix):
    path = Path(path)
    if not prefix:
        return path
    safe_prefix = "".join("_" if char in '<>:"/\\|?*' or ord(char) < 32 else char for char in prefix)
    safe_prefix = "_".join(safe_prefix.strip().split())
    safe_prefix = safe_prefix[:120]
    target = path.with_name(f"{safe_prefix}{path.name}")
    if target.exists():
        target = path.with_name(f"{safe_prefix}{uuid.uuid4().hex[:8]}-{path.name}")
    path.replace(target)
    return target


def manga_job_snapshot(job_id):
    with MANGA_BATCH_LOCK:
        job = MANGA_BATCH_JOBS.get(job_id)
        if not job:
            return None
        snapshot = {key: value for key, value in job.items() if key not in {"cfg", "auth_header", "sources", "references"}}
        snapshot["items"] = sorted(snapshot.get("items") or [], key=lambda item: (item.get("extra") or {}).get("batch_index") or 0)
        snapshot["failures"] = sorted(snapshot.get("failures") or [], key=lambda item: item.get("index") or 0)
        return snapshot


def update_manga_job(job_id, **patch):
    with MANGA_BATCH_LOCK:
        job = MANGA_BATCH_JOBS.get(job_id)
        if not job:
            return
        for key, value in patch.items():
            if key in {"items", "failures"}:
                job.setdefault(key, []).append(value)
            else:
                job[key] = value
        done_count = int(job.get("completed") or 0) + int(job.get("failed") or 0)
        job["done_count"] = done_count
        total = int(job.get("total") or 0)
        if total and done_count >= total and job.get("status") == "running":
            job["status"] = "done"
            job["finished_at"] = datetime.now(timezone.utc).isoformat()


def run_manga_batch_job(job_id):
    with MANGA_BATCH_LOCK:
        job = MANGA_BATCH_JOBS.get(job_id)
        if not job:
            return
        sources = list(job["sources"])
        cfg = dict(job["cfg"])
        auth_header = dict(job.get("auth_header") or {})
        prompt = job["prompt"]
        prompt_planner_metadata = dict(job.get("prompt_planner") or {})
        aspect_ratio = job["aspect_ratio"]
        image_resolution = job.get("image_resolution") or "auto"
        parallel = job["parallel"]
        mode = job["mode"]
        target_language = job["target_language"]
        use_builtin_prompt = bool(job.get("use_builtin_prompt", True))
        builtin_prompt_overridden = bool(job.get("builtin_prompt_overridden"))
        reference_paths = [Path(item["path"]) for item in job.get("references") or []]
    update_manga_job(job_id, status="running", started_at=datetime.now(timezone.utc).isoformat())
    try:
        if cfg["mode"] == "live" and mode == "panel_realize":
            with ThreadPoolExecutor(max_workers=parallel) as executor:
                future_map = {}
                for source in sources:
                    prefix = (
                        f"grok_panel_{safe_output_stem(source.get('source_page_name') or source['name'], source.get('page_index') or source['index'])}"
                        f"_p{source.get('page_index', 1):03d}_c{source.get('panel_index', source['index']):03d}_"
                    )
                    edit_sources = [source["path"], *reference_paths[:MANGA_PANEL_REFERENCE_LIMIT]]
                    future = executor.submit(
                        edit_image_sources_with_config,
                        prompt,
                        edit_sources,
                        media_path("manga_trans"),
                        cfg,
                        auth_header,
                        aspect_ratio,
                        prefix,
                        image_resolution,
                    )
                    future_map[future] = source
                for future in as_completed(future_map):
                    source = future_map[future]
                    try:
                        path, extra = future.result()
                        extra.update({
                            "generation_type": "manga_panel_realize",
                            "batch_mode": mode,
                            "target_language": target_language,
                            "batch_index": source["index"],
                            "batch_total": len(sources),
                            "parallel": parallel,
                            "image_resolution": image_resolution,
                            "use_builtin_prompt": use_builtin_prompt,
                            "builtin_prompt_overridden": builtin_prompt_overridden,
                            "source_original_name": source["name"],
                            "source_panel_path": public_path(source["path"]),
                            "source_page_path": public_path(source.get("source_page_path")),
                            "source_page_name": source.get("source_page_name"),
                            "page_index": source.get("page_index"),
                            "panel_index": source.get("panel_index"),
                            "crop_box": source.get("crop_box"),
                            "reference_paths": [public_path(path) for path in reference_paths[:MANGA_PANEL_REFERENCE_LIMIT]],
                        })
                        extra.update(prompt_planner_metadata)
                        item = add_metadata("edit", prompt, cfg["image_model"], path, source_path=source["path"], extra=extra)
                        with MANGA_BATCH_LOCK:
                            MANGA_BATCH_JOBS[job_id]["items"].append(item)
                            MANGA_BATCH_JOBS[job_id]["completed"] += 1
                    except Exception as exc:
                        with MANGA_BATCH_LOCK:
                            MANGA_BATCH_JOBS[job_id]["failures"].append({
                                "index": source["index"],
                                "name": source["name"],
                                "error": str(exc)[:700],
                            })
                            MANGA_BATCH_JOBS[job_id]["failed"] += 1
                    update_manga_job(job_id)
        elif cfg["mode"] == "live":
            with ThreadPoolExecutor(max_workers=parallel) as executor:
                future_map = {}
                for source in sources:
                    prefix = f"grok_trans_{safe_output_stem(source['name'], source['index'])}_"
                    future = executor.submit(
                        edit_image_with_config,
                        prompt,
                        source["path"],
                        media_path("manga_trans"),
                        cfg,
                        auth_header,
                        aspect_ratio,
                        prefix,
                        image_resolution,
                    )
                    future_map[future] = source
                for future in as_completed(future_map):
                    source = future_map[future]
                    try:
                        path, extra = future.result()
                        extra.update({
                            "generation_type": "manga_live_translate",
                            "batch_mode": mode,
                            "target_language": target_language,
                            "batch_index": source["index"],
                            "batch_total": len(sources),
                            "parallel": parallel,
                            "image_resolution": image_resolution,
                            "use_builtin_prompt": use_builtin_prompt,
                            "builtin_prompt_overridden": builtin_prompt_overridden,
                            "source_original_name": source["name"],
                            "source_image_path": public_path(source["path"]),
                        })
                        extra.update(prompt_planner_metadata)
                        item = add_metadata("edit", prompt, cfg["image_model"], path, source_path=source["path"], extra=extra)
                        with MANGA_BATCH_LOCK:
                            MANGA_BATCH_JOBS[job_id]["items"].append(item)
                            MANGA_BATCH_JOBS[job_id]["completed"] += 1
                    except Exception as exc:
                        with MANGA_BATCH_LOCK:
                            MANGA_BATCH_JOBS[job_id]["failures"].append({
                                "index": source["index"],
                                "name": source["name"],
                                "error": str(exc)[:700],
                            })
                            MANGA_BATCH_JOBS[job_id]["failed"] += 1
                    update_manga_job(job_id)
        else:
            for source in sources:
                if mode == "panel_realize":
                    prefix = (
                        f"grok_panel_{safe_output_stem(source.get('source_page_name') or source['name'], source.get('page_index') or source['index'])}"
                        f"_p{source.get('page_index', 1):03d}_c{source.get('panel_index', source['index']):03d}_"
                    )
                else:
                    prefix = f"grok_trans_{safe_output_stem(source['name'], source['index'])}_"
                path = mock_svg(media_path("manga_trans"), "Manga Batch", f"{mode} #{source['index']}", filename_prefix=prefix)
                extra = {
                    "mock_image": True,
                    "generation_type": "manga_panel_realize" if mode == "panel_realize" else "manga_live_translate",
                    "batch_mode": mode,
                    "target_language": target_language,
                    "batch_index": source["index"],
                    "batch_total": len(sources),
                    "image_resolution": image_resolution,
                    "source_original_name": source["name"],
                    "use_builtin_prompt": use_builtin_prompt,
                    "builtin_prompt_overridden": builtin_prompt_overridden,
                    "source_image_path": public_path(source["path"]),
                    "source_panel_path": public_path(source["path"]) if mode == "panel_realize" else None,
                    "source_page_path": public_path(source.get("source_page_path")) if mode == "panel_realize" else None,
                    "source_page_name": source.get("source_page_name") if mode == "panel_realize" else None,
                    "page_index": source.get("page_index") if mode == "panel_realize" else None,
                    "panel_index": source.get("panel_index") if mode == "panel_realize" else None,
                    "crop_box": source.get("crop_box") if mode == "panel_realize" else None,
                    "reference_paths": [public_path(path) for path in reference_paths[:MANGA_PANEL_REFERENCE_LIMIT]] if mode == "panel_realize" else [],
                }
                extra.update(prompt_planner_metadata)
                item = add_metadata("edit", prompt, cfg["image_model"], path, source_path=source["path"], extra=extra)
                with MANGA_BATCH_LOCK:
                    MANGA_BATCH_JOBS[job_id]["items"].append(item)
                    MANGA_BATCH_JOBS[job_id]["completed"] += 1
                update_manga_job(job_id)
        update_manga_job(job_id, status="done", finished_at=datetime.now(timezone.utc).isoformat())
    except Exception as exc:
        update_manga_job(job_id, status="failed", error=str(exc)[:900], finished_at=datetime.now(timezone.utc).isoformat())


@app.get("/api/manga-builtin-prompt")
def manga_builtin_prompt():
    mode = (request.args.get("mode") or "live_translate").strip()
    if mode not in {"live_translate", "live", "translate", "panel_realize"}:
        mode = "live_translate"
    target_language = (request.args.get("target_language") or "Korean").strip()
    return jsonify({"ok": True, "prompt": manga_batch_builtin_prompt(mode, target_language), "mode": mode})


@app.post("/api/manga-batch")
def manga_batch():
    uploads = [item for item in request.files.getlist("images") if item and item.filename]
    mode = (request.form.get("mode") or "live_translate").strip()
    if mode not in {"live_translate", "live", "translate", "panel_realize"}:
        mode = "live_translate"
    target_language = (request.form.get("target_language") or "Korean").strip()
    extra_prompt = (request.form.get("prompt") or "").strip()
    raw_use_builtin_prompt = request.form.get("use_builtin_prompt")
    use_builtin_prompt = True if raw_use_builtin_prompt is None else raw_use_builtin_prompt.strip().lower() in {"1", "true", "on", "yes"}
    builtin_prompt_override = (request.form.get("builtin_prompt_override") or "").strip()
    aspect_ratio = valid_aspect_ratio(request.form.get("aspect_ratio"))
    image_resolution = valid_image_resolution(request.form.get("image_resolution"))
    try:
        parallel = max(1, min(MANGA_BATCH_MAX_PARALLEL, int(request.form.get("parallel") or MANGA_BATCH_MAX_PARALLEL)))
    except (TypeError, ValueError):
        parallel = MANGA_BATCH_MAX_PARALLEL
    if not uploads:
        return safe_error("처리할 망가 이미지를 업로드해 주세요.")
    if len(uploads) > MANGA_BATCH_MAX_UPLOADS:
        return safe_error(f"한 번에 최대 {MANGA_BATCH_MAX_UPLOADS}장까지 처리할 수 있습니다.")
    prompt = manga_batch_prompt(mode, target_language, extra_prompt, use_builtin_prompt, builtin_prompt_override)
    if not prompt:
        return safe_error("처리 프롬프트를 구성할 수 없습니다. 내장 프롬프트를 끈 경우 추가 지시를 입력해 주세요.")
    try:
        ensure_media_dirs()
        sources = []
        for index, uploaded in enumerate(uploads, start=1):
            original_name = uploaded.filename or f"page-{index}.png"
            safe_name = secure_filename(original_name) or f"page-{index}.png"
            suffix = Path(safe_name).suffix.lower()
            if suffix not in {".jpg", ".jpeg", ".png", ".webp"}:
                raise ValueError("jpg, png, webp 이미지만 업로드할 수 있습니다.")
            dest = media_path("uploads", f"{now_stamp()}-{index:03d}-{uuid.uuid4().hex}-manga-source{suffix}")
            uploaded.save(dest)
            sources.append({"index": index, "path": dest, "name": original_name})
        references = save_manga_reference_uploads() if mode == "panel_realize" else []
        if mode == "panel_realize":
            panel_sources = []
            for page in sources:
                panels = extract_manga_panel_crops(page["path"], page["index"], page["name"])
                for panel in panels:
                    panel["index"] = len(panel_sources) + 1
                    panel_sources.append(panel)
                    if len(panel_sources) > MANGA_PANEL_MAX_CROPS:
                        raise ValueError(f"컷 분리 결과가 너무 많습니다. 한 번에 최대 {MANGA_PANEL_MAX_CROPS}컷까지 처리할 수 있습니다.")
            if not panel_sources:
                raise ValueError("분리할 컷을 찾지 못했습니다.")
            sources = panel_sources
        cfg = config()
        auth_header = xai_auth_header() if cfg["mode"] == "live" else {}
        job_id = uuid.uuid4().hex
        with MANGA_BATCH_LOCK:
            MANGA_BATCH_JOBS[job_id] = {
                "id": job_id,
                "status": "queued",
                "total": len(sources),
                "completed": 0,
                "failed": 0,
                "done_count": 0,
                "items": [],
                "failures": [],
                "prompt": prompt,
                "prompt_planner": prompt_planner_request_metadata(request.form, prompt),
                "mode": mode,
                "target_language": target_language,
                "use_builtin_prompt": use_builtin_prompt,
                "builtin_prompt_overridden": bool(builtin_prompt_override),
                "aspect_ratio": aspect_ratio,
                "image_resolution": image_resolution,
                "parallel": parallel,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "cfg": cfg,
                "auth_header": auth_header,
                "sources": sources,
                "references": references,
                "reference_count": len(references),
            }
        Thread(target=run_manga_batch_job, args=(job_id,), daemon=True).start()
        return jsonify({"ok": True, "job_id": job_id, "total": len(sources), "prompt": prompt})
    except ValueError as exc:
        return safe_error(str(exc))
    except Exception as exc:
        return safe_error("망가 배치 처리 시작에 실패했습니다.", exc, 502)


@app.get("/api/manga-batch/<job_id>")
def manga_batch_status(job_id):
    snapshot = manga_job_snapshot(job_id)
    if not snapshot:
        return safe_error("배치 작업을 찾을 수 없습니다.", status=404)
    return jsonify({"ok": True, **snapshot})


@app.post("/api/manga-batch-sync")
def manga_batch_sync_legacy():
    return manga_batch()


@app.post("/api/i2v")
def i2v():
    prompt = (request.form.get("prompt") or "").strip()
    duration = valid_duration(request.form.get("duration"))
    aspect_ratio = valid_aspect_ratio(request.form.get("aspect_ratio"), allow_source=True)
    resolution = valid_video_resolution(request.form.get("resolution"))
    cfg = config()
    video_model = valid_video_model(request.form.get("video_model"), cfg)
    upscale_source = checked(request.form.get("upscale_source"))
    if not prompt:
        return safe_error("영상 프롬프트를 입력해 주세요.")
    try:
        source_limit = 1 if video_model_single_reference_only(video_model) else 3
        sources, source_items = save_reference_images_or_library("image", "i2v", limit=source_limit)
        if video_model_single_reference_only(video_model) and len(sources) > 1:
            sources = sources[:1]
            source_items = source_items[:1]
        original_sources = sources
        video_sources = sources
        upscale_details = []
        if cfg["mode"] == "live" and upscale_source:
            video_sources, upscale_details = upscale_i2v_sources_to_2k(sources, prompt)
        source = video_sources[0]
        if cfg["mode"] == "live":
            if len(video_sources) > 1:
                reference_prompt = (
                    f"{prompt}\n\n"
                    f"Use IMAGE_1 as the primary starting image. "
                    f"Use the additional reference images to preserve identity, outfit, environment, palette, style, and target visual details."
                ).strip()
                path, extra = live_video_from_reference_images(reference_prompt, video_sources, duration, aspect_ratio=aspect_ratio, resolution=resolution, video_model=video_model)
            else:
                path, extra = live_video(prompt, source, duration, aspect_ratio=aspect_ratio, resolution=resolution, video_model=video_model)
        else:
            path, extra = mock_svg(media_path("video"), "Image to Video", prompt), {
                "mock_video": True,
                "duration": duration,
                "aspect_ratio": aspect_ratio,
                "resolution": resolution,
                "source_count": len(sources),
                "upscale_before_video": upscale_source,
                "video_model": video_model,
            }
        extra.update({
            "generation_type": "i2v",
            "i2v_prompt": prompt,
            "duration": duration,
            "aspect_ratio": aspect_ratio,
            "resolution": resolution,
            "requested_resolution": resolution,
            "start_image_path": public_path(source),
            "original_start_image_path": public_path(original_sources[0]) if upscale_source else None,
            "start_image_id": source_items[0].get("id") if source_items and source_items[0] else None,
            "reference_image_paths": [public_path(item) for item in video_sources],
            "original_reference_image_paths": [public_path(item) for item in original_sources] if upscale_source else None,
            "reference_image_ids": [item.get("id") if item else None for item in source_items],
            "reference_image_count": len(video_sources),
            "multi_image_i2v": len(video_sources) > 1,
            "upscale_before_video": upscale_source,
            "upscale_resolution": "2k" if upscale_source else None,
            "upscaled_reference_images": upscale_details,
            "video_model": video_model,
        })
        extra.update(prompt_planner_request_metadata(request.form, prompt))
        item = add_metadata("video", prompt, video_model, path, source_path=source, extra=extra)
        return jsonify({"ok": True, "item": item})
    except ValueError as exc:
        return safe_error(str(exc))
    except Exception as exc:
        return safe_error("영상 생성에 실패했습니다.", exc, 502)


@app.post("/api/v2v-extend")
def v2v_extend():
    return handle_v2v_extend("official")


@app.post("/api/v2v-frame-extend")
def v2v_frame_extend():
    return handle_v2v_extend("frame")


@app.post("/api/video-edit")
def video_edit():
    try:
        sources, source_items = save_video_uploads_or_library_paths("videos", limit=12)
        if len(sources) < 1:
            return safe_error("편집할 영상을 선택해 주세요.")
        title = (request.form.get("title") or "").strip() or "영상 편집"
        fade_in = float(request.form.get("fade_in") or 0)
        fade_out = float(request.form.get("fade_out") or 0)
        transition = (request.form.get("transition") or "cut").strip()
        crossfade = float(request.form.get("crossfade") or 0)
        aspect_ratio = valid_aspect_ratio(request.form.get("aspect_ratio"), allow_source=True)
        resolution = (request.form.get("resolution") or "source").strip()
        if resolution not in {"source", "480p", "720p"}:
            resolution = "source"
        mute = (request.form.get("mute") or "true") != "false"
        clip_settings = parse_video_clip_settings(request.form.get("video_clip_settings"), len(sources))
        path, extra = edit_merge_videos(
            sources,
            fade_in=fade_in,
            fade_out=fade_out,
            transition=transition,
            crossfade=crossfade,
            aspect_ratio=aspect_ratio,
            resolution=resolution,
            mute=mute,
            clip_settings=clip_settings,
        )
        extra["source_video_ids"] = [item.get("id") if item else None for item in source_items]
        item = add_metadata("video", title, "ffmpeg-video-editor", path, source_path=sources[0], extra=extra)
        return jsonify({"ok": True, "item": item})
    except ValueError as exc:
        return safe_error(str(exc))
    except Exception as exc:
        return safe_error("영상 편집에 실패했습니다.", exc, 502)


def handle_v2v_extend(strategy):
    prompt = (request.form.get("prompt") or "").strip()
    duration = valid_duration(request.form.get("duration"))
    connect_time = valid_connect_time(request.form.get("connect_time"))
    aspect_ratio = valid_aspect_ratio(request.form.get("aspect_ratio"), allow_source=True)
    resolution = valid_video_resolution(request.form.get("resolution"))
    mute = (request.form.get("mute") or "true") != "false"
    upscale_frame = (request.form.get("upscale_frame") or "true") != "false"
    cfg = config()
    video_model = valid_video_model(request.form.get("video_model"), cfg)
    if not prompt:
        return safe_error("연장할 영상 프롬프트를 입력해 주세요.")
    try:
        source_video = save_video_upload_or_library("video")
        reference_context = i2v_reference_context(source_video)
        extension_prompt = prompt
        frame = save_uploaded_frame("last_frame") if strategy == "official" else None
        prepared_frame = frame
        upscaled = False
        frame_dimensions = image_dimensions(frame) if frame else None
        upscale_extra = None
        generated_segment_path = None
        concat_extra = None
        if cfg["mode"] == "live" and strategy == "official":
            if source_video.suffix.lower() != ".mp4":
                raise ValueError("공식 영상 연장 API는 mp4 원본 영상만 사용할 수 있습니다. 프레임 기반 연장을 사용해 주세요.")
            remote_url = source_video_remote_url(source_video)
            extension_source, trim_extra = trim_video_for_extension(source_video, connect_time)
            official_path, extra = live_video_extension(extension_prompt, extension_source, duration, video_url=remote_url if not trim_extra.get("trimmed_for_connect_time") else None, video_model=video_model)
            source_duration = video_duration_seconds(extension_source)
            official_output_duration = video_duration_seconds(official_path)
            path, stitch_extra = compose_official_connected_result(
                source_video,
                official_path,
                trim_extra,
                aspect_ratio,
                resolution,
            )
            output_duration = video_duration_seconds(path)
            extra.update(trim_extra)
            extra["original_source_duration"] = video_duration_seconds(source_video)
            extra["extension_source_path"] = public_path(extension_source)
            extra["official_result_path"] = public_path(official_path)
            extra["official_output_duration"] = official_output_duration
            extra.update(stitch_extra)
            extra["combined"] = True
            extra["source_duration"] = source_duration
            extra["output_duration"] = output_duration
        elif cfg["mode"] == "live":
            frame = extract_last_frame(source_video)
            if upscale_frame:
                prepared_frame, upscaled, frame_dimensions, upscale_extra = upscale_frame_to_2k(
                    frame,
                    extension_prompt,
                )
            else:
                prepared_frame = frame
                upscaled = False
                frame_dimensions = image_dimensions(frame)
                upscale_extra = {"skipped": True, "reason": "사용자가 마지막 프레임 2K 업스케일을 껐습니다."}
            generated_segment_path, extra = live_video(
                extension_prompt,
                prepared_frame,
                duration,
                aspect_ratio=aspect_ratio,
                resolution=resolution,
                video_model=video_model,
            )
            path, concat_extra = concat_videos(
                source_video,
                generated_segment_path,
                aspect_ratio,
                resolution,
                reference_path=prepared_frame,
                mute_audio=mute,
            )
            extra["combined"] = True
            extra["combined_by"] = "frame_capture_local_concat"
            extra["concat"] = concat_extra
            extra["used_last_frame_only"] = True
        else:
            path, extra = mock_svg(media_path("video"), "Video Extend", prompt), {
                "mock_video": True,
                "duration": duration,
                "aspect_ratio": aspect_ratio,
                "resolution": resolution,
            }
            extra["combined"] = False
        extra.update({
            "generation_type": "v2v_extend",
            "extension_strategy": strategy,
            "duration": duration,
            "connect_time": connect_time,
            "aspect_ratio": aspect_ratio,
            "resolution": resolution,
            "requested_resolution": resolution,
            "mute": mute,
            "source_video_path": public_path(source_video),
            "generated_segment_path": public_path(generated_segment_path) if generated_segment_path else None,
            "extracted_frame_path": public_path(frame) if frame else None,
            "prepared_frame_path": public_path(prepared_frame) if prepared_frame else None,
            "frame_dimensions": frame_dimensions,
            "upscaled": upscaled,
            "upscale_extra": upscale_extra,
            "frame_upscale_requested": upscale_frame if strategy == "frame" else None,
            "frame_upscale_prompt": frame_upscale_prompt(extension_prompt) if strategy == "frame" and upscale_frame else None,
            "original_start_image_path": reference_context.get("start_image_path") if reference_context else None,
            "original_i2v_prompt": reference_context.get("i2v_prompt") if reference_context else None,
            "used_i2v_start_image_reference": bool(reference_context),
            "effective_prompt": extension_prompt,
            "video_model": video_model,
        })
        extra.update(prompt_planner_request_metadata(request.form, prompt))
        item = add_metadata("video", prompt, video_model, path, source_path=prepared_frame, extra=extra)
        return jsonify({"ok": True, "item": item, "frame_path": public_path(prepared_frame) if prepared_frame else None, "upscaled": upscaled})
    except ValueError as exc:
        return safe_error(str(exc))
    except Exception as exc:
        return safe_error("영상 연장에 실패했습니다.", exc, 502)


@app.post("/api/reverse-prompt")
def reverse_prompt():
    try:
        source, source_item, source_from_library = save_reference_image_or_library("image", "reverse-prompt")
        cfg = config()
        if cfg["mode"] == "live":
            body = {
                "model": cfg["vision_model"],
                "input": [{
                    "role": "user",
                    "content": [
                        {"type": "input_image", "image_url": data_uri(source), "detail": "high"},
                        {"type": "input_text", "text": "이 이미지를 재생성하기 좋은 한국어 생성 프롬프트로 요약해 주세요. 스타일, 피사체, 구도, 조명, 색감을 포함하세요."},
                    ],
                }],
            }
            response = requests.post(cfg["api_base"] + "/responses", headers=xai_headers(), json=body, timeout=240)
            response.raise_for_status()
            data = response.json() or {}
            record_usage(data.get("usage"))
            prompt = extract_response_text(data) or "이미지의 피사체, 배경, 조명, 색감, 구도를 살린 상세 생성 프롬프트"
        else:
            prompt = "업로드한 이미지를 바탕으로, 중심 피사체를 선명하게 배치하고 자연스러운 조명과 풍부한 질감을 살린 고해상도 장면"
        return jsonify({
            "ok": True,
            "prompt": prompt,
            "source_path": public_path(source),
            "source_item": source_item,
            "source_from_library": source_from_library,
        })
    except ValueError as exc:
        return safe_error(str(exc))
    except Exception as exc:
        return safe_error("프롬프트 추출에 실패했습니다.", exc, 502)


@app.get("/api/library")
def library():
    return jsonify({"ok": True, "items": scanned_library_items()})


@app.post("/api/library/favorite")
def favorite_library_item():
    data = request.get_json(silent=True) or {}
    item_id = str(data.get("id") or "").strip()
    favorite = parse_request_bool(data.get("favorite"))
    if not item_id:
        return safe_error("라이브러리 항목을 찾을 수 없습니다.", status=404)

    items = read_metadata()
    for item in items:
        if item.get("id") == item_id:
            item["favorite"] = favorite
            write_metadata(items)
            return jsonify({"ok": True, "id": item_id, "favorite": favorite})

    item = find_library_item_by_id(item_id)
    if not item:
        return safe_error("라이브러리 항목을 찾을 수 없습니다.", status=404)
    if not item_id.startswith("scan-"):
        return safe_error("즐겨찾기 상태를 저장할 수 없습니다.", status=400)
    if not favorite:
        return jsonify({"ok": True, "id": item_id, "favorite": False})

    try:
        local_media_path_from_public(item.get("file_path"))
    except ValueError as exc:
        return safe_error(str(exc), status=404)

    promoted = {
        "id": uuid.uuid4().hex,
        "kind": item.get("kind") or "image",
        "prompt": item.get("prompt") or "(저장 경로에서 발견된 파일)",
        "created_at": item.get("created_at") or datetime.now(timezone.utc).isoformat(),
        "model": item.get("model") or "scanned",
        "file_path": item.get("file_path"),
        "source_path": item.get("source_path"),
        "favorite": favorite,
        "extra": {**(item.get("extra") or {}), "scanned": True, "promoted_from_scan": item_id},
    }
    items.insert(0, promoted)
    write_metadata(items)
    return jsonify({"ok": True, "id": promoted["id"], "old_id": item_id, "favorite": favorite, "item": promoted})


@app.get("/api/video-thumbnail")
def video_thumbnail():
    rel = (request.args.get("path") or "").strip()
    try:
        return redirect(video_thumbnail_public_path(rel), code=302)
    except Exception as exc:
        return safe_error("영상 썸네일 생성에 실패했습니다.", exc, 404)


@app.post("/api/library/open-folder")
def open_library_folder():
    try:
        target = media_root().resolve()
        if os.name == "nt":
            subprocess.Popen(["explorer.exe", str(target)])
        else:
            opener = "open" if sys.platform == "darwin" else "xdg-open"
            subprocess.Popen([opener, str(target)])
        return jsonify({"ok": True, "path": str(target)})
    except Exception as exc:
        return safe_error("저장 폴더를 열 수 없습니다.", exc, 500)


@app.post("/api/library/item-path")
def library_item_path():
    data = request.get_json(silent=True) or {}
    item = find_library_item_by_id(data.get("id"))
    if not item:
        return safe_error("라이브러리 항목을 찾을 수 없습니다.", status=404)
    try:
        target = local_media_path_from_public(item.get("file_path"))
        return jsonify({"ok": True, "path": str(target)})
    except ValueError as exc:
        return safe_error(str(exc), status=404)


@app.post("/api/library/open-file")
def open_library_file():
    data = request.get_json(silent=True) or {}
    item = find_library_item_by_id(data.get("id"))
    if not item:
        return safe_error("라이브러리 항목을 찾을 수 없습니다.", status=404)
    try:
        target = local_media_path_from_public(item.get("file_path"))
        if os.name == "nt":
            os.startfile(str(target))  # pylint: disable=no-member
        else:
            opener = "open" if sys.platform == "darwin" else "xdg-open"
            subprocess.Popen([opener, str(target)])
        return jsonify({"ok": True, "path": str(target)})
    except ValueError as exc:
        return safe_error(str(exc), status=404)
    except Exception as exc:
        return safe_error("파일을 기본 앱으로 열 수 없습니다.", exc, 500)


@app.post("/api/library/copy-file")
def copy_library_file():
    data = request.get_json(silent=True) or {}
    item = find_library_item_by_id(data.get("id"))
    if not item:
        return safe_error("라이브러리 항목을 찾을 수 없습니다.", status=404)
    try:
        target = local_media_path_from_public(item.get("file_path"))
        if os.name != "nt":
            return jsonify({"ok": True, "path": str(target), "clipboard_supported": False})
        clipboard_path = str(target).replace("'", "''")
        script = (
            "Add-Type -AssemblyName System.Windows.Forms; "
            "Add-Type -AssemblyName System.Collections.Specialized; "
            "$files = New-Object System.Collections.Specialized.StringCollection; "
            f"$files.Add('{clipboard_path}') | Out-Null; "
            "[System.Windows.Forms.Clipboard]::SetFileDropList($files);"
        )
        completed = subprocess.run(
            ["powershell.exe", "-NoProfile", "-STA", "-Command", script],
            capture_output=True,
            text=True,
            timeout=20,
        )
        if completed.returncode != 0:
            raise RuntimeError(completed.stderr or completed.stdout or "clipboard failed")
        return jsonify({"ok": True, "path": str(target), "clipboard_supported": True})
    except Exception as exc:
        return safe_error("파일을 클립보드에 복사할 수 없습니다.", exc, 500)


@app.post("/api/library/delete")
def delete_library_items():
    data = request.get_json(silent=True) or {}
    ids = set(data.get("ids") or [])
    if not ids:
        return safe_error("삭제할 항목을 선택해 주세요.")
    items = read_metadata()
    scanned_delete_paths = []
    keep = []
    deleted = 0
    for item in items:
        if item.get("id") not in ids:
            keep.append(item)
            continue
        deleted += 1
        for key in ("file_path",):
            rel = item.get(key)
            if not rel:
                continue
            target = (media_root() / rel.replace("/media-library/", "", 1).lstrip("/")).resolve() if rel.startswith("/media-library/") else (ROOT / rel.lstrip("/")).resolve()
            root = media_root().resolve()
            if (target == root or root in target.parents) and target.exists():
                try:
                    target.unlink()
                except OSError:
                    pass
    if any(item_id.startswith("scan-") for item_id in ids):
        for folder, extensions in (("image", {".png", ".jpg", ".jpeg", ".webp", ".svg"}), ("video", {".mp4", ".webm", ".mov"})):
            directory = media_path(folder)
            if not directory.exists():
                continue
            for path in directory.rglob("*"):
                if path.is_file() and path.suffix.lower() in extensions:
                    scan_id = "scan-" + hashlib.sha1(str(path.resolve()).encode("utf-8")).hexdigest()
                    if scan_id in ids:
                        scanned_delete_paths.append(path)
        for target in scanned_delete_paths:
            try:
                target.unlink()
                deleted += 1
            except OSError:
                pass
    write_metadata(keep)
    return jsonify({"ok": True, "deleted": deleted})


@app.get("/media-library/<path:name>")
def media(name):
    return send_from_directory(media_root(), name)


@app.get("/sw.js")
def service_worker():
    response = send_from_directory(app.static_folder, "service-worker.js", mimetype="application/javascript")
    response.headers["Service-Worker-Allowed"] = "/"
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    return response


if __name__ == "__main__":
    if getattr(sys, "frozen", False) and (sys.stdout is None or sys.stderr is None):
        log_file = open(ROOT / "webgork-runtime.log", "a", encoding="utf-8", buffering=1)
        sys.stdout = log_file
        sys.stderr = log_file
    port = int(os.getenv("WEBGORK_PORT", "7863"))
    if os.getenv("WEBGORK_OPEN_BROWSER", "1") == "1":
        Thread(target=lambda: (time.sleep(1.2), webbrowser.open(f"http://127.0.0.1:{port}")), daemon=True).start()
    app.run(host="127.0.0.1", port=port, debug=False)
