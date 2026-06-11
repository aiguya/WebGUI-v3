import base64
import hashlib
import html
import json
import math
import mimetypes
import os
import re
import secrets
import shutil
import socket
import ssl
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
from urllib.parse import parse_qs, quote, urlparse
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
HERMES_IMAGE_MODEL_CANDIDATES = [
    "grok-imagine-image-quality",
    "grok-imagine-image-pro",
    "grok-imagine-image-quality-latest",
    "grok-imagine-image",
]
HERMES_VIDEO_MODEL_CANDIDATES = [
    "grok-imagine-video",
    "grok-imagine-video-1.5-preview",
]
GROK_OFFICIAL_IMAGE_MODEL_CANDIDATES = [
    "official:imagine-x-1",
    "official:imagine_h_1",
]
GROK_OFFICIAL_VIDEO_MODEL_CANDIDATES = [
    "grok-imagine-video",
]
GROK_OFFICIAL_IMAGE_MODEL_NAMES = {
    "official:imagine-x-1": "imagine-x-1",
    "official:imagine_h_1": "imagine_h_1",
}
GROK_OFFICIAL_PRO_MODELS = {
    "grok-imagine-image-quality",
    "grok-imagine-image-pro",
    "grok-imagine-image-quality-latest",
    "official:imagine_h_1",
}
HERMES_PROBE_IMAGE_DATA_URI = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMB/axC8S0AAAAASUVORK5CYII="
)


def model_id_valid(value):
    return bool(re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", str(value or "").strip()))


def unique_model_ids(values):
    result = []
    for value in values or []:
        model = str(value or "").strip()
        if model_id_valid(model) and model not in result:
            result.append(model)
    return result


def request_model_id_list(value):
    if isinstance(value, str):
        return re.split(r"[\s,]+", value)
    if isinstance(value, (list, tuple, set)):
        return list(value)
    return []


def hermes_model_candidates_payload(cfg):
    return {
        "image": cfg["image_model"],
        "openai_image": cfg["openai_image_model"],
        "codex_image": cfg["codex_image_model"],
        "video": cfg["video_model"],
        "vision": cfg["vision_model"],
        "hermes_image_candidates": unique_model_ids(
            HERMES_IMAGE_MODEL_CANDIDATES + cfg.get("hermes_discovered_image_models", [])
        ),
        "hermes_video_candidates": unique_model_ids(
            HERMES_VIDEO_MODEL_CANDIDATES + cfg.get("hermes_discovered_video_models", [])
        ),
        "grok_official_image_candidates": unique_model_ids(GROK_OFFICIAL_IMAGE_MODEL_CANDIDATES),
        "grok_official_video_candidates": unique_model_ids(GROK_OFFICIAL_VIDEO_MODEL_CANDIDATES),
        "hermes_discovered_image": cfg.get("hermes_discovered_image_models", []),
        "hermes_discovered_video": cfg.get("hermes_discovered_video_models", []),
    }


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
    projects = root / "projects.json"
    video_templates = root / "video-templates.json"
    video_template_blocks = root / "video-template-blocks.json"
    usage = root / "usage.json"
    if not meta.exists():
        meta.write_text("[]", encoding="utf-8")
    if not prompts.exists():
        prompts.write_text("[]", encoding="utf-8")
    if not projects.exists():
        projects.write_text("[]", encoding="utf-8")
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


def projects_path():
    return media_path("projects.json")


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
GROK_OFFICIAL_PROGRESS = {
    "status": "idle",
    "stage": "idle",
    "message": "Grok 공식홈 요청 대기 중",
    "updated_at": None,
}
GROK_OFFICIAL_PROGRESS_LOCK = Lock()
GROK_CHROME_UA_CACHE = {"value": "", "expires_at": 0.0}
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
    if provider not in {"direct", "hermes_proxy", "grok_official", "openai_api", "codex_proxy"}:
        provider = "direct"
    hermes_base = (settings.get("hermes_base_url") or os.getenv("HERMES_PROXY_BASE_URL") or "").strip().rstrip("/")
    hermes_key = (settings.get("hermes_api_key") or os.getenv("HERMES_PROXY_API_KEY") or "").strip()
    openai_key = (settings.get("openai_api_key") or os.getenv("OPENAI_API_KEY") or "").strip()
    codex_base = (settings.get("codex_proxy_base_url") or os.getenv("CODEX_IMAGE_PROXY_BASE_URL") or discover_codex_proxy_url() or "http://127.0.0.1:3333").strip().rstrip("/")
    mode = "live" if (
        (provider == "hermes_proxy" and hermes_base)
        or provider == "grok_official"
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
        "hermes_discovered_image_models": unique_model_ids(settings.get("hermes_discovered_image_models") or []),
        "hermes_discovered_video_models": unique_model_ids(settings.get("hermes_discovered_video_models") or []),
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
    if model_id_valid(model):
        return model
    return fallback


def grok_official_image_model_name(model):
    return GROK_OFFICIAL_IMAGE_MODEL_NAMES.get(str(model or "").strip(), "")


def grok_official_image_model_is_experimental(model):
    return bool(grok_official_image_model_name(model))


def grok_official_image_enable_pro(model):
    return str(model or "").strip() in GROK_OFFICIAL_PRO_MODELS


def grok_official_image_resolution_name(resolution):
    resolution = str(resolution or "").strip().lower()
    if resolution == "2k":
        return "2mp"
    return ""


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


def selected_image_backend(value, cfg=None, provider_override=None):
    cfg = cfg or config()
    requested = (value or "").strip()
    provider = provider_override if provider_override in {"direct", "hermes_proxy", "grok_official"} else (
        cfg["provider"] if cfg["provider"] in {"direct", "hermes_proxy", "grok_official"} else ("hermes_proxy" if cfg.get("hermes_base_url") else "direct")
    )
    if requested.startswith("gpt-image-") or (not requested and cfg["provider"] == "openai_api"):
        raise ValueError("OpenAI API 모델은 현재 UI에서 사용하지 않습니다. Codex/ChatGPT OAuth 모델(gpt-5 계열)을 선택해 주세요.")
    if requested.startswith("gpt-5.") or (not requested and cfg["provider"] == "codex_proxy"):
        model = valid_codex_image_model(requested, cfg)
        if requested and model != requested:
            raise ValueError(f"지원하지 않는 Codex 이미지 모델입니다: {requested}")
        return "codex_proxy", model
    if grok_official_image_model_is_experimental(requested) and provider != "grok_official":
        raise ValueError(f"Grok 공식홈 전용 이미지 모델은 요청 경로를 Grok 공식홈 Quota로 선택해야 합니다: {requested}")
    model = valid_image_model(requested, cfg)
    if requested and model != requested:
        raise ValueError(f"지원하지 않는 Grok 이미지 모델입니다: {requested}")
    return provider, model


def selected_image_model(value, cfg=None):
    return selected_image_backend(value, cfg)[1]


def valid_edit_input_mode(value):
    mode = (value or "stitch").strip().lower()
    return mode if mode in {"stitch", "multi"} else "stitch"


def checked(value):
    return str(value or "").strip().lower() in {"1", "true", "on", "yes"}


def request_provider_override(source=None):
    getter = source.get if source is not None else request.values.get
    value = (
        getter("request_provider")
        or getter("request_route")
        or getter("image_provider")
        or getter("provider_route")
        or ""
    )
    value = str(value).strip().lower()
    return value if value in {"direct", "hermes_proxy", "grok_official"} else None


def valid_video_resolution(value):
    resolution = (value or "720p").strip()
    return resolution if resolution in {"480p", "720p"} else "720p"


def valid_video_model(value, cfg=None):
    fallback = (cfg or config())["video_model"]
    model = (value or fallback).strip()
    if model_id_valid(model):
        return model
    return fallback


def video_model_single_reference_only(model):
    return "1.5" in (model or "")


def video_model_retry_candidates(model, cfg=None):
    cfg = cfg or config()
    requested = valid_video_model(model, cfg)
    fallbacks = {
        "grok-imagine-video-latest": ["grok-imagine-video"],
        "grok-imagine-video-1.5-latest": ["grok-imagine-video-1.5-preview", "grok-imagine-video-1.5", "grok-imagine-video"],
    }
    candidates = [requested, *fallbacks.get(requested, [])]
    if requested.endswith("-latest"):
        candidates.append(requested[:-7])
    return unique_model_ids(candidates)


def video_model_not_found_response(response):
    if response.status_code != 404:
        return False
    detail = response_error_detail(response).lower()
    return (
        "model" in detail
        and (
            "does not exist" in detail
            or "does not have access" in detail
            or "requested entity was not found" in detail
            or "not found" in detail
        )
    )


def post_video_with_model_fallback(url, headers, payload, requested_model, timeout=120):
    last_response = None
    attempts = []
    for model in video_model_retry_candidates(requested_model):
        body = {**payload, "model": model}
        response = requests.post(url, headers=headers, json=body, timeout=timeout)
        attempts.append({"model": model, "status": response.status_code})
        if response.status_code < 400:
            return response, model, attempts
        last_response = response
        if not video_model_not_found_response(response):
            return response, model, attempts
    return last_response, attempts[-1]["model"] if attempts else requested_model, attempts


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


def normalize_project(item):
    item = dict(item or {})
    now = datetime.now(timezone.utc).isoformat()
    title = str(item.get("title") or "").strip()[:160]
    if not title:
        title = "새 프로젝트"
    return {
        "id": str(item.get("id") or uuid.uuid4().hex),
        "title": title,
        "description": str(item.get("description") or "").strip()[:3000],
        "tags": normalize_prompt_tags(item.get("tags")),
        "favorite": bool(item.get("favorite")),
        "created_at": item.get("created_at") or now,
        "updated_at": item.get("updated_at") or item.get("created_at") or now,
    }


def read_projects():
    try:
        data = json.loads(projects_path().read_text(encoding="utf-8"))
    except (json.JSONDecodeError, FileNotFoundError):
        data = []
    if not isinstance(data, list):
        data = []
    return [normalize_project(item) for item in data if isinstance(item, dict)]


def write_projects(items):
    target = projects_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    normalized = [normalize_project(item) for item in items if isinstance(item, dict)]
    temp = target.with_name(f"{target.name}.tmp")
    temp.write_text(json.dumps(normalized, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(target)


def find_project(project_id):
    project_id = str(project_id or "").strip()
    if not project_id:
        return None
    for item in read_projects():
        if item.get("id") == project_id:
            return item
    return None


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
VIDEO_TEMPLATE_FORMAT_VERSION = 1
TEMPLATE_BLOCK_FORMAT_VERSION = 1


def clean_template_key(value, fallback="var"):
    key = re.sub(r"[^a-zA-Z0-9_]+", "_", str(value or "").strip()).strip("_").lower()
    return (key or fallback)[:48]


def normalize_template_reference_slots(item, limit=3):
    raw = item.get("reference_slots") if isinstance(item, dict) else None
    values = []
    primary = item.get("reference_slot") if isinstance(item, dict) else None
    if primary:
        values.append(primary)
    if isinstance(raw, list):
        values.extend(raw)
    elif isinstance(raw, str):
        values.append(raw)
    seen = set()
    slots = []
    for value in values:
        key = clean_template_key(value, "")
        if not key or key in seen:
            continue
        seen.add(key)
        slots.append(key)
        if len(slots) >= limit:
            break
    return slots


def parse_template_format_version(value, default=1):
    try:
        version = int(value)
    except (TypeError, ValueError):
        version = default
    return max(1, version)


def migrate_video_template_format(item):
    migrated = dict(item or {})
    source_version = parse_template_format_version(migrated.get("format_version"), default=1)
    migrated["_source_format_version"] = source_version
    # Version 1 is the first persisted format. Future upgrades should add
    # sequential transforms here, e.g. if source_version < 2: ...
    migrated["format_version"] = min(source_version, VIDEO_TEMPLATE_FORMAT_VERSION)
    return migrated


def migrate_template_block_format(item):
    migrated = dict(item or {})
    source_version = parse_template_format_version(migrated.get("format_version"), default=1)
    migrated["_source_format_version"] = source_version
    # Version 1 is the first persisted reusable block format.
    migrated["format_version"] = min(source_version, TEMPLATE_BLOCK_FORMAT_VERSION)
    return migrated


def clean_template_model(value):
    model = str(value or "").strip()
    if re.fullmatch(r"[A-Za-z0-9._:-]{1,96}", model):
        return model
    return ""


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
            selected_path = str(item.get("selected_path") or item.get("default_path") or "").strip()[:1000]
            selected_label = str(item.get("selected_label") or "").strip()[:160]
            selected_kind = str(item.get("selected_kind") or kind).strip().lower()
        else:
            key = clean_template_key(item, f"slot_{index}")
            label = key
            kind = "image"
            note = ""
            selected_path = ""
            selected_label = ""
            selected_kind = kind
        if kind not in {"image", "video", "text"}:
            kind = "image"
        if selected_kind not in {"image", "video"}:
            selected_kind = "video" if kind == "video" else "image"
        if selected_path and not selected_path.startswith("/media-library/"):
            selected_path = ""
        if key in seen:
            continue
        seen.add(key)
        slots.append({
            "key": key,
            "label": label or key,
            "kind": kind,
            "note": note,
            "selected_path": selected_path,
            "selected_kind": selected_kind if selected_path else "",
            "selected_label": selected_label if selected_path else "",
        })
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
        request_provider = str(item.get("request_provider") or item.get("provider_route") or "").strip().lower()
        if request_provider not in {"direct", "hermes_proxy", "grok_official"}:
            request_provider = ""
        try:
            duration = float(item.get("duration") or 6)
        except (TypeError, ValueError):
            duration = 6
        duration = max(1, min(15, duration))
        reference_slots = normalize_template_reference_slots(item)
        reference_slot = reference_slots[0] if reference_slots else clean_template_key(item.get("reference_slot"), "")
        shots.append({
            "id": str(item.get("id") or uuid.uuid4().hex),
            "order": index,
            "title": str(item.get("title") or f"컷 {index:02d}").strip()[:120],
            "method": method,
            "method_label": VIDEO_TEMPLATE_METHODS[method],
            "duration": duration,
            "reference_slot": reference_slot,
            "reference_slots": reference_slots,
            "output_slot": clean_template_key(item.get("output_slot"), ""),
            "image_model": clean_template_model(item.get("image_model")),
            "image_resolution": valid_image_resolution(item.get("image_resolution")),
            "edit_input_mode": valid_edit_input_mode(item.get("edit_input_mode") or "multi"),
            "video_model": clean_template_model(item.get("video_model")),
            "request_provider": request_provider,
            "prompt": str(item.get("prompt") or "").strip()[:12000],
            "camera": str(item.get("camera") or "").strip()[:2000],
            "transition": transition,
            "retry_prompt": str(item.get("retry_prompt") or "").strip()[:6000],
            "notes": str(item.get("notes") or "").strip()[:4000],
        })
    return shots[:240]


def normalize_video_template(item):
    item = migrate_video_template_format(item)
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
    run_mode = str(settings.get("run_mode") or item.get("run_mode") or "auto").strip().lower()
    if run_mode not in {"auto", "manual"}:
        run_mode = "auto"
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
        "format_version": VIDEO_TEMPLATE_FORMAT_VERSION,
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
            "run_mode": run_mode,
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
    item = migrate_template_block_format(item)
    now = datetime.now(timezone.utc).isoformat()
    source_shot_id = str(item.get("source_shot_id") or item.get("shot_id") or "").strip()
    shot_items = normalize_template_shots([{
        "id": source_shot_id,
        "title": item.get("title") or item.get("name"),
        "method": item.get("method"),
        "duration": item.get("duration"),
        "reference_slot": item.get("reference_slot"),
        "reference_slots": item.get("reference_slots"),
        "output_slot": item.get("output_slot"),
        "image_model": item.get("image_model"),
        "image_resolution": item.get("image_resolution"),
        "edit_input_mode": item.get("edit_input_mode"),
        "video_model": item.get("video_model"),
        "request_provider": item.get("request_provider") or item.get("provider_route"),
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
        "format_version": TEMPLATE_BLOCK_FORMAT_VERSION,
        "id": block_id,
        "title": shot.get("title") or "컷 블록",
        "method": shot.get("method") or "i2v",
        "method_label": VIDEO_TEMPLATE_METHODS.get(shot.get("method"), "이미지→영상"),
        "duration": shot.get("duration") or 6,
        "reference_slot": shot.get("reference_slot") or "",
        "reference_slots": shot.get("reference_slots") or [],
        "output_slot": shot.get("output_slot") or "",
        "image_model": shot.get("image_model") or "",
        "image_resolution": shot.get("image_resolution") or "auto",
        "edit_input_mode": shot.get("edit_input_mode") or "multi",
        "video_model": shot.get("video_model") or "",
        "request_provider": shot.get("request_provider") or "",
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


def http_media_url(value):
    if isinstance(value, str) and value.startswith(("http://", "https://")):
        return value
    return None


def metadata_remote_url(item):
    if not isinstance(item, dict):
        return None
    extra = item.get("extra") if isinstance(item.get("extra"), dict) else {}
    for value in (
        extra.get("remote_url"),
        extra.get("source_url"),
        extra.get("official_image_url"),
        extra.get("official_media_url"),
        item.get("remote_url"),
        item.get("source_url"),
    ):
        url = http_media_url(value)
        if url:
            return url
    return None


def remote_url_for_media_path(path):
    try:
        item = find_metadata_by_file_path(Path(path))
    except Exception:
        item = None
    return metadata_remote_url(item)


def remote_media_url_fetchable(url):
    url = http_media_url(url)
    if not url:
        return False
    try:
        response = requests.head(url, allow_redirects=True, timeout=8)
        if 200 <= response.status_code < 400:
            return True
        if response.status_code not in {403, 405}:
            return False
    except requests.RequestException:
        pass
    try:
        response = requests.get(url, headers={"Range": "bytes=0-0"}, stream=True, timeout=10)
        try:
            return 200 <= response.status_code < 400
        finally:
            response.close()
    except requests.RequestException:
        return False


def image_input_url(path, allow_remote=True):
    remote_url = remote_url_for_media_path(path) if allow_remote else None
    if remote_url and remote_media_url_fetchable(remote_url):
        return remote_url, True
    return data_uri(Path(path)), False


def image_input_object(path, include_type=False, allow_remote=True):
    url, used_remote = image_input_url(path, allow_remote=allow_remote)
    payload = {"url": url}
    if include_type:
        payload["type"] = "image_url"
    return payload, used_remote


class MinimalWebSocket:
    def __init__(self, url, headers=None, timeout=30):
        self.url = url
        self.headers = headers or {}
        self.timeout = timeout
        self.sock = None
        self.connected = False

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()

    def connect(self):
        parsed = urlparse(self.url)
        if parsed.scheme not in {"ws", "wss"}:
            raise ValueError(f"Unsupported WebSocket URL: {self.url}")
        host = parsed.hostname
        port = parsed.port or (443 if parsed.scheme == "wss" else 80)
        path = parsed.path or "/"
        if parsed.query:
            path += "?" + parsed.query
        raw = socket.create_connection((host, port), timeout=self.timeout)
        raw.settimeout(self.timeout)
        if parsed.scheme == "wss":
            raw = ssl.create_default_context().wrap_socket(raw, server_hostname=host)
            raw.settimeout(self.timeout)
        key = base64.b64encode(os.urandom(16)).decode("ascii")
        host_header = host if parsed.port in (None, 80, 443) else f"{host}:{port}"
        lines = [
            f"GET {path} HTTP/1.1",
            f"Host: {host_header}",
            "Upgrade: websocket",
            "Connection: Upgrade",
            f"Sec-WebSocket-Key: {key}",
            "Sec-WebSocket-Version: 13",
        ]
        for name, value in self.headers.items():
            if value is not None and value != "":
                lines.append(f"{name}: {value}")
        request_bytes = ("\r\n".join(lines) + "\r\n\r\n").encode("utf-8")
        raw.sendall(request_bytes)
        response = b""
        while b"\r\n\r\n" not in response:
            chunk = raw.recv(4096)
            if not chunk:
                break
            response += chunk
            if len(response) > 65536:
                break
        head = response.split(b"\r\n\r\n", 1)[0].decode("iso-8859-1", errors="replace")
        if " 101 " not in head.split("\r\n", 1)[0]:
            raw.close()
            raise RuntimeError(f"WebSocket handshake failed: {head[:800]}")
        self.sock = raw
        self.connected = True

    def send_text(self, text):
        self._send_frame(0x1, text.encode("utf-8"))

    def send_json(self, payload):
        self.send_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))

    def recv(self):
        while True:
            fin, opcode, payload = self._recv_frame()
            if opcode in {0x1, 0x2}:
                chunks = [payload]
                initial_opcode = opcode
                while not fin:
                    fin, opcode, payload = self._recv_frame()
                    if opcode == 0x0:
                        chunks.append(payload)
                    elif opcode == 0x9:
                        self._send_frame(0xA, payload)
                    elif opcode == 0x8:
                        self.connected = False
                        return "close", payload
                payload = b"".join(chunks)
                opcode = initial_opcode
            if opcode == 0x1:
                return "text", payload.decode("utf-8", errors="replace")
            if opcode == 0x2:
                return "binary", payload
            if opcode == 0x8:
                self.connected = False
                return "close", payload
            if opcode == 0x9:
                self._send_frame(0xA, payload)
            elif opcode == 0xA:
                continue

    def close(self):
        if not self.sock:
            return
        try:
            if self.connected:
                self._send_frame(0x8, b"")
        except Exception:
            pass
        try:
            self.sock.close()
        except Exception:
            pass
        self.connected = False
        self.sock = None

    def _send_frame(self, opcode, payload):
        if not self.sock:
            raise RuntimeError("WebSocket is not connected.")
        payload = payload or b""
        mask = os.urandom(4)
        first = 0x80 | opcode
        length = len(payload)
        if length < 126:
            header = struct.pack("!BB", first, 0x80 | length)
        elif length < (1 << 16):
            header = struct.pack("!BBH", first, 0x80 | 126, length)
        else:
            header = struct.pack("!BBQ", first, 0x80 | 127, length)
        masked = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
        self.sock.sendall(header + mask + masked)

    def _recv_exact(self, count):
        chunks = []
        remaining = count
        while remaining:
            chunk = self.sock.recv(remaining)
            if not chunk:
                raise RuntimeError("WebSocket connection closed.")
            chunks.append(chunk)
            remaining -= len(chunk)
        return b"".join(chunks)

    def _recv_frame(self):
        header = self._recv_exact(2)
        first, second = header
        fin = bool(first & 0x80)
        opcode = first & 0x0F
        length = second & 0x7F
        masked = bool(second & 0x80)
        if length == 126:
            length = struct.unpack("!H", self._recv_exact(2))[0]
        elif length == 127:
            length = struct.unpack("!Q", self._recv_exact(8))[0]
        mask = self._recv_exact(4) if masked else b""
        payload = self._recv_exact(length) if length else b""
        if masked:
            payload = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
        return fin, opcode, payload


def json_safe(value):
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [json_safe(item) for item in value]
    return value


def recursive_find_values(value, predicate, limit=30):
    found = []

    def walk(node):
        if len(found) >= limit:
            return
        if isinstance(node, dict):
            for item in node.values():
                walk(item)
        elif isinstance(node, list):
            for item in node:
                walk(item)
        elif predicate(node):
            found.append(node)

    walk(value)
    return found


def grok_official_port():
    try:
        return int(os.getenv("GROK_OFFICIAL_CHROME_PORT", "9227"))
    except ValueError:
        return 9227


def grok_official_profile_dir():
    return Path(os.getenv("GROK_OFFICIAL_CHROME_PROFILE") or (ROOT / ".chrome-grok-official-profile")).resolve()


def grok_default_chrome_user_data_dir():
    configured = os.getenv("GROK_OFFICIAL_DEFAULT_CHROME_USER_DATA_DIR")
    if configured:
        return Path(configured).expanduser().resolve()
    local_app_data = os.getenv("LOCALAPPDATA")
    if not local_app_data:
        return None
    return (Path(local_app_data) / "Google" / "Chrome" / "User Data").resolve()


def grok_default_chrome_profile_name():
    configured = (os.getenv("GROK_OFFICIAL_DEFAULT_CHROME_PROFILE") or "").strip()
    if configured:
        return configured
    user_data_dir = grok_default_chrome_user_data_dir()
    if user_data_dir:
        try:
            local_state = json.loads((user_data_dir / "Local State").read_text(encoding="utf-8"))
            last_used = (((local_state or {}).get("profile") or {}).get("last_used") or "").strip()
            if last_used:
                return last_used
        except Exception:
            pass
    return "Default"


def chrome_process_count():
    if os.name != "nt":
        return 0
    try:
        output = subprocess.check_output(
            ["tasklist", "/FI", "IMAGENAME eq chrome.exe", "/FO", "CSV", "/NH"],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=3,
        )
    except Exception:
        return 0
    if "INFO:" in output:
        return 0
    return sum(1 for line in output.splitlines() if line.strip().lower().startswith('"chrome.exe"'))


def stop_chrome_processes():
    if os.name != "nt":
        raise RuntimeError("Chrome 자동 종료는 Windows에서만 지원합니다.")
    before = chrome_process_count()
    if not before:
        return {"stopped": 0, "message": "실행 중인 Chrome이 없습니다."}
    proc = subprocess.run(
        ["taskkill", "/IM", "chrome.exe", "/T", "/F"],
        capture_output=True,
        text=True,
        timeout=15,
    )
    time.sleep(1.0)
    after = chrome_process_count()
    if proc.returncode != 0 and after:
        detail = (proc.stderr or proc.stdout or "").strip()
        raise RuntimeError(f"Chrome 종료에 실패했습니다. {detail[:500]}")
    return {
        "stopped": before,
        "remaining": after,
        "message": f"Chrome 프로세스 {before}개를 종료했습니다.",
    }


def chrome_executable_candidates():
    candidates = []
    for env_name in ("GROK_CHROME_PATH", "CHROME_PATH"):
        value = os.getenv(env_name)
        if value:
            candidates.append(Path(value))
    program_files = [os.getenv("ProgramFiles"), os.getenv("ProgramFiles(x86)"), os.getenv("LOCALAPPDATA")]
    for base in [Path(item) for item in program_files if item]:
        candidates.extend([
            base / "Google" / "Chrome" / "Application" / "chrome.exe",
            base / "Microsoft" / "Edge" / "Application" / "msedge.exe",
        ])
    for name in ("chrome.exe", "chrome", "msedge.exe", "msedge"):
        found = shutil.which(name)
        if found:
            candidates.append(Path(found))
    return candidates


def chrome_executable_path():
    for candidate in chrome_executable_candidates():
        if candidate.exists():
            return candidate
    return None


def update_grok_official_progress(**fields):
    with GROK_OFFICIAL_PROGRESS_LOCK:
        GROK_OFFICIAL_PROGRESS.update(fields)
        GROK_OFFICIAL_PROGRESS["updated_at"] = datetime.now(timezone.utc).isoformat()
        return dict(GROK_OFFICIAL_PROGRESS)


def reset_grok_official_progress(**fields):
    with GROK_OFFICIAL_PROGRESS_LOCK:
        GROK_OFFICIAL_PROGRESS.clear()
        GROK_OFFICIAL_PROGRESS.update({
            "status": "idle",
            "stage": "idle",
            "message": "Grok 공식홈 요청 대기 중",
            "updated_at": None,
        })
        GROK_OFFICIAL_PROGRESS.update(fields)
        GROK_OFFICIAL_PROGRESS["updated_at"] = datetime.now(timezone.utc).isoformat()
        return dict(GROK_OFFICIAL_PROGRESS)


def grok_official_progress_payload():
    with GROK_OFFICIAL_PROGRESS_LOCK:
        return dict(GROK_OFFICIAL_PROGRESS)


def ensure_grok_chrome(use_default_profile=False):
    port = grok_official_port()
    if port_open("127.0.0.1", port):
        return {
            "ok": True,
            "port": port,
            "running": True,
            "started": False,
            "url": f"http://127.0.0.1:{port}",
            "profile_mode": "existing_debug_session",
            "message": "Grok 공식홈 Chrome 디버그 세션이 이미 실행 중입니다.",
        }
    exe = chrome_executable_path()
    if not exe:
        raise RuntimeError("Chrome 또는 Edge 실행 파일을 찾지 못했습니다. GROK_CHROME_PATH를 설정해 주세요.")
    profile_mode = "default_chrome_profile" if use_default_profile else "dedicated_profile"
    profile = grok_default_chrome_user_data_dir() if use_default_profile else grok_official_profile_dir()
    if not profile:
        raise RuntimeError("기본 Chrome 프로필 경로를 찾지 못했습니다. GROK_OFFICIAL_DEFAULT_CHROME_USER_DATA_DIR를 설정해 주세요.")
    if use_default_profile and not profile.exists():
        raise RuntimeError(f"기본 Chrome 프로필 폴더를 찾지 못했습니다: {profile}")
    if use_default_profile and chrome_process_count():
        raise RuntimeError(
            "기본 Chrome 프로필이 이미 실행 중인 Chrome에 잠겨 있습니다. 모든 Chrome 창을 닫은 뒤 설정의 '내 Chrome'을 다시 눌러 주세요."
        )
    profile.mkdir(parents=True, exist_ok=True)
    command = [
        str(exe),
        f"--remote-debugging-port={port}",
        f"--user-data-dir={profile}",
        "--no-first-run",
        "--no-default-browser-check",
        "https://grok.com/",
    ]
    if use_default_profile:
        command.insert(-1, f"--profile-directory={grok_default_chrome_profile_name()}")
    subprocess.Popen(command, cwd=str(ROOT), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(20):
        if port_open("127.0.0.1", port):
            return {
                "ok": True,
                "port": port,
                "running": True,
                "started": True,
                "url": f"http://127.0.0.1:{port}",
                "profile_dir": str(profile),
                "profile_mode": profile_mode,
                "message": "Grok 공식홈 Chrome을 열었습니다.",
            }
        time.sleep(0.5)
    message = "Grok 공식홈 Chrome을 시작했지만 디버그 포트가 열리지 않았습니다."
    if use_default_profile:
        message += " 이미 실행 중인 일반 Chrome이 있으면 모든 Chrome 창을 닫은 뒤 다시 눌러 주세요."
    return {
        "ok": True,
        "port": port,
        "running": False,
        "started": True,
        "url": f"http://127.0.0.1:{port}",
        "profile_dir": str(profile),
        "profile_mode": profile_mode,
        "message": message,
    }


def cdp_json(path, port=None, method="GET"):
    port = port or grok_official_port()
    url = f"http://127.0.0.1:{port}{path}"
    response = requests.request(method, url, timeout=10)
    response.raise_for_status()
    return response.json()


def grok_imagine_tab(port=None, post_id=None):
    port = port or grok_official_port()
    tabs = cdp_json("/json/list", port=port)
    if post_id:
        post_token = f"/imagine/post/{post_id}"
        for tab in tabs:
            if (
                isinstance(tab, dict)
                and post_token in (tab.get("url") or "")
                and tab.get("webSocketDebuggerUrl")
            ):
                return tab
        target_url = f"https://grok.com/imagine/post/{post_id}"
        encoded = quote(target_url, safe=":/?=&")
        for method in ("PUT", "GET"):
            try:
                created = cdp_json("/json/new?" + encoded, port=port, method=method)
                if created.get("webSocketDebuggerUrl"):
                    time.sleep(2)
                    return created
            except Exception:
                pass
    for tab in tabs:
        if isinstance(tab, dict) and "grok.com" in (tab.get("url") or "") and tab.get("webSocketDebuggerUrl"):
            return tab
    encoded = "https://grok.com/"
    for method in ("PUT", "GET"):
        try:
            created = cdp_json("/json/new?" + encoded, port=port, method=method)
            if created.get("webSocketDebuggerUrl"):
                time.sleep(2)
                return created
        except Exception:
            pass
    tabs = cdp_json("/json/list", port=port)
    for tab in tabs:
        if isinstance(tab, dict) and tab.get("webSocketDebuggerUrl"):
            return tab
    raise RuntimeError("Chrome CDP 탭을 찾지 못했습니다.")


class CdpWebSocket:
    def __init__(self, ws_url, timeout=20):
        self.ws = MinimalWebSocket(ws_url, timeout=timeout)
        self.next_id = 1

    def __enter__(self):
        self.ws.connect()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.ws.close()

    def call(self, method, params=None, timeout=20):
        msg_id = self.next_id
        self.next_id += 1
        self.ws.send_json({"id": msg_id, "method": method, "params": params or {}})
        deadline = time.time() + timeout
        while time.time() < deadline:
            kind, data = self.ws.recv()
            if kind != "text":
                continue
            payload = json.loads(data)
            if payload.get("id") != msg_id:
                continue
            if payload.get("error"):
                raise RuntimeError(json.dumps(payload["error"], ensure_ascii=False))
            return payload.get("result") or {}
        raise TimeoutError(f"CDP call timed out: {method}")


def grok_official_is_cloudflare_challenge(text):
    lowered = (text or "").lower()
    return (
        "just a moment" in lowered
        or "challenges.cloudflare.com" in lowered
        or "cf-chl" in lowered
        or ("<!doctype html" in lowered and "cloudflare" in lowered)
        or ("<html" in lowered and "cloudflare" in lowered)
    )


def grok_official_cloudflare_upload_message(status, detail=""):
    hint = (
        "Grok 공식홈 업로드가 Cloudflare 검증 페이지로 차단되었습니다. "
        "Grok 공식홈 Chrome에서 grok.com/imagine을 열어 검증/로그인 상태를 확인한 뒤 다시 시도해 주세요. "
        "계속 반복되면 공식홈 업로드 API가 현재 세션에서 차단된 상태이므로 Grok Agent 탭의 참조 asset 명령 경로를 사용해 주세요."
    )
    preview = " ".join((detail or "").split())[:240]
    return f"{hint} HTTP {status}" + (f" / {preview}" if preview else "")


def grok_official_browser_fetch(url, body=None, method="POST", timeout=360, target_post_id=None):
    tab = grok_imagine_tab(post_id=target_post_id)
    body_json = json.dumps(body or {}, ensure_ascii=False, separators=(",", ":"))
    expression = f"""
(async () => {{
  const findStatsigId = () => {{
    const looksLikeStatsigId = (value) => {{
      if (typeof value !== "string") return false;
      const text = value.trim().replace(/^["']|["']$/g, "");
      return text.length >= 32 && text.length <= 300 && /^[A-Za-z0-9+/=_-]+$/.test(text);
    }};
    const clean = (value) => String(value || "").trim().replace(/^["']|["']$/g, "");
    const scanJson = (value, depth = 0) => {{
      if (depth > 4 || value == null) return "";
      if (looksLikeStatsigId(value)) return clean(value);
      if (Array.isArray(value)) {{
        for (const item of value) {{
          const found = scanJson(item, depth + 1);
          if (found) return found;
        }}
      }} else if (typeof value === "object") {{
        for (const [key, item] of Object.entries(value)) {{
          const found = scanJson(item, depth + 1);
          if (found && String(key).toLowerCase().includes("stable")) return found;
        }}
        for (const item of Object.values(value)) {{
          const found = scanJson(item, depth + 1);
          if (found) return found;
        }}
      }}
      return "";
    }};
    const stores = [];
    try {{ stores.push(window.localStorage); }} catch (error) {{}}
    try {{ stores.push(window.sessionStorage); }} catch (error) {{}}
    const directKeys = ["STATSIG_LOCAL_STORAGE_STABLE_ID", "statsig.stable_id", "statsigStableId", "statsigStableID", "x-statsig-id"];
    for (const store of stores) {{
      for (const key of directKeys) {{
        try {{
          const value = store.getItem(key);
          if (looksLikeStatsigId(value)) return clean(value);
        }} catch (error) {{}}
      }}
      try {{
        for (let index = 0; index < store.length; index += 1) {{
          const key = store.key(index) || "";
          if (!key.toLowerCase().includes("statsig")) continue;
          const raw = store.getItem(key);
          if (looksLikeStatsigId(raw)) return clean(raw);
          try {{
            const found = scanJson(JSON.parse(raw));
            if (found) return found;
          }} catch (error) {{}}
        }}
      }} catch (error) {{}}
    }}
    return "";
  }};
  const requestHeaders = {{
    "Accept": "application/json, text/event-stream, */*",
    "Content-Type": "application/json",
    "x-xai-request-id": crypto.randomUUID ? crypto.randomUUID() : String(Date.now())
  }};
  const statsigId = findStatsigId();
  if (statsigId) requestHeaders["x-statsig-id"] = statsigId;
  const response = await fetch({json.dumps(url)}, {{
    method: {json.dumps(method)},
    credentials: "include",
    headers: requestHeaders,
    body: {json.dumps(body_json)}
  }});
  const headers = Object.fromEntries(response.headers.entries());
  let text = "";
  if (response.body && response.body.getReader) {{
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    while (true) {{
      const chunk = await reader.read();
      if (chunk.done) break;
      text += decoder.decode(chunk.value, {{stream: true}});
    }}
    text += decoder.decode();
  }} else {{
    text = await response.text();
  }}
  return {{ok: response.ok, status: response.status, statusText: response.statusText, headers, text, href: location.href, requestHeaders}};
}})()
"""
    with CdpWebSocket(tab["webSocketDebuggerUrl"], timeout=timeout + 30) as cdp:
        result = cdp.call(
            "Runtime.evaluate",
            {
                "expression": expression,
                "awaitPromise": True,
                "returnByValue": True,
            },
            timeout=timeout + 30,
        )
    value = (result.get("result") or {}).get("value") or {}
    if not isinstance(value, dict):
        raise RuntimeError(f"Grok official browser fetch returned an unexpected response: {value}")
    return value


def grok_chrome_cookies(start_chrome=False):
    if start_chrome:
        ensure_grok_chrome()
    elif not port_open("127.0.0.1", grok_official_port()):
        raise RuntimeError("Grok 공식홈 Chrome이 실행 중이 아닙니다.")
    tab = grok_imagine_tab()
    with CdpWebSocket(tab["webSocketDebuggerUrl"]) as cdp:
        result = cdp.call("Network.getAllCookies")
    cookies = result.get("cookies") or []
    return [cookie for cookie in cookies if "grok.com" in (cookie.get("domain") or "")]


def active_grok_account_id():
    settings = read_settings()
    configured = (settings.get("grok_account_id") or os.getenv("GROK_ACCOUNT_ID") or "").strip()
    if configured:
        return configured
    try:
        cookies = grok_chrome_cookies()
    except Exception:
        return ""
    preferred_names = {"x-userid", "x_grok_account_id", "x-grok-account-id", "grok_account_id", "account_id"}
    for cookie in cookies:
        name = (cookie.get("name") or "").lower()
        if name in preferred_names and cookie.get("value"):
            return cookie["value"]
    for cookie in cookies:
        name = (cookie.get("name") or "").lower()
        if "account" in name and cookie.get("value"):
            return cookie["value"]
    return ""


def grok_web_cookie_for(account_id=None, start_chrome=False):
    try:
        cookies = grok_chrome_cookies(start_chrome=start_chrome)
    except Exception as exc:
        raise RuntimeError("Grok 공식홈 세션 쿠키를 읽지 못했습니다. 설정에서 Grok 공식홈 Chrome을 열고 로그인해 주세요.") from exc
    if not cookies:
        raise RuntimeError("Grok 공식홈 세션 쿠키가 없습니다. 설정에서 Grok 공식홈 Chrome을 열고 로그인해 주세요.")
    pairs = []
    for cookie in cookies:
        name = cookie.get("name")
        value = cookie.get("value")
        if name and value is not None:
            pairs.append(f"{name}={value}")
    if not pairs:
        raise RuntimeError("Grok 공식홈 세션 쿠키가 비어 있습니다. Grok 공식홈에 다시 로그인해 주세요.")
    return "; ".join(pairs)


def grok_cookie_value(cookie_header, names):
    lookup = {}
    for part in cookie_header.split(";"):
        if "=" in part:
            name, value = part.split("=", 1)
            lookup[name.strip().lower()] = value.strip()
    for name in names:
        value = lookup.get(name.lower())
        if value:
            return value
    return ""


def grok_chrome_user_agent():
    now = time.time()
    cached = GROK_CHROME_UA_CACHE.get("value")
    if cached and now < float(GROK_CHROME_UA_CACHE.get("expires_at") or 0):
        return cached
    configured = (os.getenv("GROK_OFFICIAL_USER_AGENT") or "").strip()
    if configured:
        return configured
    try:
        tab = grok_imagine_tab()
        with CdpWebSocket(tab["webSocketDebuggerUrl"]) as cdp:
            version = cdp.call("Browser.getVersion")
        value = (version.get("userAgent") or "").strip()
        if value:
            GROK_CHROME_UA_CACHE.update({"value": value, "expires_at": now + 600})
            return value
    except Exception:
        pass
    return "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


def grok_web_headers(account_id=None, accept="application/json", start_chrome=False):
    account_id = account_id or active_grok_account_id()
    cookie = grok_web_cookie_for(account_id, start_chrome=start_chrome)
    headers = {
        "Accept": accept,
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
        "User-Agent": grok_chrome_user_agent(),
        "Origin": "https://grok.com",
        "Referer": "https://grok.com/",
        "Cookie": cookie,
    }
    if account_id:
        headers["x-grok-account-id"] = account_id
    csrf = grok_cookie_value(cookie, ("csrf", "csrf_token", "_csrf", "grok_csrf_token", "x-csrf-token"))
    if csrf:
        headers["x-csrf-token"] = csrf
    return headers


def official_aspect_ratio(aspect_ratio, fallback="2:3"):
    return aspect_ratio if aspect_ratio in {"2:3", "3:2", "1:1", "9:16", "16:9"} else fallback


def official_image_id_from_url(url):
    match = re.search(r"/images/([A-Za-z0-9_-]+)\.(?:jpe?g|png|webp)", url or "")
    return match.group(1) if match else ""


def grok_official_image_url(image_id):
    return f"https://imagine-public.x.ai/imagine-public/images/{image_id}.jpg" if image_id else ""


def official_generated_id_from_url(url):
    match = re.search(r"/generated/([^/?#]+)/", url or "")
    return match.group(1) if match else ""


def grok_official_generated_asset_image_url(post_id, account_id=None, source_url=""):
    if not post_id:
        return ""
    source_url = source_url or ""
    match = re.search(
        r"(https://assets\.grok\.com/users/[^/]+/generated/" + re.escape(post_id) + r")(?:/[^?#]*)?",
        source_url,
    )
    if match:
        return match.group(1) + "/image.jpg"
    account_id = account_id or active_grok_account_id()
    if account_id:
        return f"https://assets.grok.com/users/{account_id}/generated/{post_id}/image.jpg"
    return grok_official_image_url(post_id)


def grok_official_download_candidates(url, kind="image"):
    candidates = []
    raw_url = str(url or "").strip()
    if raw_url and not raw_url.startswith(("http://", "https://")):
        encoded = quote(raw_url, safe="")
        if raw_url.startswith("assets.grok.com/"):
            asset_path = raw_url.split("assets.grok.com/", 1)[1]
        else:
            asset_path = raw_url.lstrip("/")
        if asset_path.startswith("users/"):
            asset_url = f"https://assets.grok.com/{asset_path}"
            candidates.append(asset_url)
            if "?" not in asset_url:
                candidates.append(asset_url + "?cache=1")
        candidates.extend([
            f"https://grok.com/rest/app-chat/download-file?fileUri={encoded}",
            f"https://grok.com/rest/app-chat/file?fileUri={encoded}",
            f"https://grok.com/rest/app-chat/files?fileUri={encoded}",
            f"https://grok.com/rest/media/file?fileUri={encoded}",
            f"https://grok.com/rest/media/download?fileUri={encoded}",
        ])
        return list(dict.fromkeys(candidates))
    if raw_url:
        candidates.append(raw_url)
    if kind == "image":
        image_id = official_image_id_from_url(raw_url)
        if image_id:
            for suffix in (".jpg", ".jpeg", ".png", ".webp"):
                candidate = f"https://imagine-public.x.ai/imagine-public/images/{image_id}{suffix}"
                if candidate not in candidates:
                    candidates.append(candidate)
    return candidates


def save_response_bytes(blob, dest_dir, suffix=".jpg", filename_prefix="grok-official-"):
    dest = dest_dir / f"{filename_prefix}{now_stamp()}-{uuid.uuid4().hex}{suffix}"
    dest.write_bytes(blob)
    return dest


def likely_grok_official_censor_placeholder(path):
    try:
        from PIL import Image, ImageFilter, ImageStat

        with Image.open(path) as source:
            image = source.convert("RGB")
            image.thumbnail((128, 128))
            gray = image.convert("L")
            edges = gray.filter(ImageFilter.FIND_EDGES)
            hist = gray.histogram()
            total = sum(hist) or 1
            entropy = -sum((count / total) * math.log2(count / total) for count in hist if count)
            edge_mean = ImageStat.Stat(edges).mean[0]
            gray_std = ImageStat.Stat(gray).stddev[0]
        # Grok's moderation placeholder is a blurred, multicolor noise field: many
        # small edges but comparatively low luminance entropy after downsampling.
        is_placeholder = edge_mean >= 40 and entropy <= 7.05 and gray_std <= 35
        return {
            "is_placeholder": bool(is_placeholder),
            "edge_mean": round(edge_mean, 3),
            "entropy": round(entropy, 3),
            "gray_std": round(gray_std, 3),
        }
    except Exception as exc:
        return {"is_placeholder": False, "error": str(exc)[:300]}


def raise_if_grok_official_placeholder(path, extra=None):
    extra = extra if isinstance(extra, dict) else {}
    if extra.get("source") != "grok_official_web":
        return None
    check = likely_grok_official_censor_placeholder(path)
    if check.get("is_placeholder"):
        extra["official_skipped_censor_placeholder"] = {
            "path": public_path(path),
            "check": check,
        }
        raise RuntimeError("Grok 공식홈 이미지 생성 결과가 검열 placeholder로 감지되어 라이브러리에 등록하지 않았습니다.")
    return check


def response_suffix_from_bytes(blob, fallback=".jpg"):
    if blob.startswith(b"\xff\xd8"):
        return ".jpg"
    if blob.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if blob.startswith(b"RIFF") and b"WEBP" in blob[:16]:
        return ".webp"
    if blob[:32].lower().find(b"ftyp") >= 0:
        return ".mp4"
    return fallback


def decode_possible_image_blob(value):
    if not isinstance(value, str):
        return None
    text = value.strip()
    if text.startswith("data:image/") and "," in text:
        text = text.split(",", 1)[1]
    if len(text) < 1024:
        return None
    if not text.startswith(("/9j/", "iVBORw0KGgo", "UklGR")):
        return None
    try:
        blob = base64.b64decode(text, validate=False)
    except Exception:
        return None
    return blob if response_suffix_from_bytes(blob, "") else None


def grok_official_extract_image_blobs(payload, limit=8):
    blobs = []

    def walk(node):
        if len(blobs) >= limit:
            return
        if isinstance(node, dict):
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)
        else:
            blob = decode_possible_image_blob(node)
            if blob:
                blobs.append(blob)

    walk(payload)
    return blobs


def grok_official_event_block_reason(event):
    reasons = []

    def walk(node, key_path=""):
        if len(reasons) >= 8:
            return
        if isinstance(node, dict):
            for key, value in node.items():
                lowered_key = str(key).lower()
                next_path = f"{key_path}.{key}" if key_path else str(key)
                if lowered_key in {"moderated", "blocked", "is_blocked", "policy_blocked", "unsafe"} and value is True:
                    reasons.append(f"{next_path}=true")
                if isinstance(value, str) and lowered_key in {"current_status", "status", "error", "message", "reason", "confirmation"}:
                    lowered_value = value.lower()
                    if any(token in lowered_value for token in ("moderation", "blocked", "policy", "unsafe", "not allowed", "violation")):
                        reasons.append(f"{next_path}={value[:160]}")
                walk(value, next_path)
        elif isinstance(node, list):
            for index, value in enumerate(node):
                walk(value, f"{key_path}[{index}]")

    walk(event)
    return "; ".join(reasons[:8])


def grok_official_ws_error_message(event):
    if not isinstance(event, dict) or event.get("type") != "error":
        return ""
    code = str(event.get("err_code") or event.get("code") or "").strip()
    message = str(event.get("err_msg") or event.get("message") or event.get("error") or "").strip()
    request_id = str(event.get("request_id") or event.get("requestId") or "").strip()
    if code == "rate_limit_exceeded":
        return (
            "Grok 공식홈 이미지 quota 제한에 걸렸습니다"
            + (f": {message}" if message else "")
            + ". Quality 모델이면 'Grok 이미지 기본'으로 바꿔 보시고, 기본 모델도 실패하면 quota 회복 후 다시 시도해 주세요."
        )
    detail = " ".join(part for part in (code, message) if part)
    if request_id:
        detail = f"{detail} request_id={request_id}".strip()
    return f"Grok 공식홈 WebSocket 오류: {detail or json.dumps(event, ensure_ascii=False)[:500]}"


def grok_official_image_blocked_message(blocked_reason):
    reason = str(blocked_reason or "moderated=true").strip()
    return (
        "Grok 공식홈에서 요청이 검열/차단되어 이미지를 저장하지 않았습니다. "
        f"{reason}. 프롬프트를 완화하거나 다른 표현으로 다시 시도해 주세요."
    )


def grok_official_ws_closed_message(json_events, blobs, account_id, completed=False, blocked_reason="", image_urls=None):
    image_urls = image_urls or []
    detail = (
        f"events={len(json_events)}, blobs={len(blobs)}, "
        f"completed={bool(completed)}, account_id={bool(account_id)}"
    )
    if blocked_reason and not (blobs or image_urls):
        return f"{grok_official_image_blocked_message(blocked_reason)} ({detail})"
    if completed and not (blobs or image_urls):
        return (
            "Grok 공식홈이 완료 상태를 보냈지만 이미지 blob/URL을 반환하지 않았습니다. "
            f"{detail}"
        )
    return f"Grok 공식홈 WebSocket이 완료 이미지 응답 전에 닫혔습니다. {detail}"


def grok_official_json_error(response):
    try:
        return json.dumps(response.json(), ensure_ascii=False)[:1200]
    except Exception:
        return (response.text or "")[:1200]


def grok_official_pipeline_error(response, kind="media"):
    detail = grok_official_json_error(response)
    lowered = detail.lower()
    is_rate_limited = (
        response.status_code == 429
        or '"code": 8' in detail
        or "too many requests" in lowered
        or "rate limit" in lowered
    )
    if is_rate_limited:
        media_label = {"video": "영상", "image": "이미지"}.get(kind, "미디어")
        retry_after = (response.headers.get("Retry-After") or "").strip()
        retry_hint = f" Retry-After={retry_after}초." if retry_after else ""
        message = (
            f"Grok 공식홈 {media_label} quota/rate limit에 걸렸습니다."
            f"{retry_hint} 잠시 후 다시 시도하거나 요청 경로를 Hermes Proxy로 바꿔 실행해 주세요."
        )
        update_grok_official_progress(
            status="failed",
            stage="rate_limited",
            message=message,
            http_status=response.status_code,
        )
        return f"{message} 원문: {detail}"
    return f"Grok 공식홈 pipeline 요청 실패: {response.status_code} {detail}"


def grok_official_status_payload(check_cookie=False):
    port = grok_official_port()
    running = port_open("127.0.0.1", port)
    payload = {
        "configured": True,
        "chrome_port": port,
        "chrome_running": running,
        "chrome_processes": chrome_process_count(),
        "profile_dir": str(grok_official_profile_dir()),
        "default_profile_dir": str(grok_default_chrome_user_data_dir() or ""),
        "default_profile_name": grok_default_chrome_profile_name(),
        "session_cookie": False,
        "account_id": "",
        "message": "",
        "progress": grok_official_progress_payload(),
    }
    if check_cookie:
        try:
            cookie = grok_web_cookie_for()
            payload["session_cookie"] = bool(cookie)
            payload["account_id"] = active_grok_account_id()
            payload["message"] = "Grok 공식홈 세션 쿠키를 확인했습니다."
        except Exception as exc:
            payload["message"] = str(exc)
            if not running and payload["chrome_processes"]:
                payload["message"] = "일반 Chrome은 실행 중이지만 9227 디버그 연결이 없습니다. 모든 Chrome 창을 닫고 설정에서 '내 Chrome'을 다시 눌러 주세요."
    return payload


def grok_official_download(url, dest_dir, kind="image", return_url=False):
    try:
        headers = grok_web_headers(accept="*/*")
    except Exception:
        headers = {}
    last_response = None
    candidates = grok_official_download_candidates(url, kind=kind)
    if not candidates:
        raise RuntimeError("Grok 공식홈 미디어 다운로드 URL이 없습니다.")
    attempts = 0
    deadline = time.time() + (45 if kind == "image" else 0)
    max_attempts = 8 if kind == "image" else 1
    while True:
        attempts += 1
        for candidate in candidates:
            request_variants = [headers] if headers else []
            request_variants.append({})
            for request_headers in request_variants:
                response = requests.get(candidate, headers=request_headers or None, timeout=240)
                last_response = response
                if response.status_code < 400:
                    mime = response.headers.get("content-type") or mimetypes.guess_type(urlparse(candidate).path)[0] or ""
                    suffix = ".mp4" if kind == "video" else (".png" if "png" in mime else ".webp" if "webp" in mime else ".jpg")
                    if kind == "video" and suffix != ".mp4":
                        suffix = ".mp4"
                    path = save_response_bytes(response.content, dest_dir, suffix=suffix)
                    return (path, candidate) if return_url else path
        if kind != "image" or attempts >= max_attempts or time.time() >= deadline:
            break
        time.sleep(2)
    if last_response is not None:
        tried = ", ".join(candidates)
        detail = grok_official_json_error(last_response)
        raise RuntimeError(f"Grok 공식홈 미디어 다운로드 실패: {last_response.status_code}. attempts={attempts}. tried={tried}. {detail}")
    raise RuntimeError("Grok 공식홈 미디어 다운로드 응답이 없습니다.")


def grok_agent_parse_json_lines(text):
    events = []
    for raw_line in (text or "").splitlines():
        line = raw_line.strip()
        if line.startswith("data:"):
            line = line[5:].strip()
        if not line or line == "[DONE]":
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events


def grok_agent_extract_card_json(value):
    cards = []

    def parse_card(raw):
        if isinstance(raw, dict):
            cards.append(raw)
            return
        if not isinstance(raw, str) or not raw.strip():
            return
        try:
            parsed = json.loads(raw)
        except Exception:
            return
        if isinstance(parsed, dict):
            cards.append(parsed)

    def walk(node):
        if isinstance(node, dict):
            if "jsonData" in node:
                parse_card(node.get("jsonData"))
            for key, item in node.items():
                if key == "cardAttachmentsJson" and isinstance(item, list):
                    for raw in item:
                        parse_card(raw)
                else:
                    walk(item)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(value)
    return cards


def grok_agent_media_candidates_from_event(event):
    candidates = []

    def add(url, kind="", meta=None):
        if not isinstance(url, str) or not url.strip():
            return
        url = url.strip()
        if not kind:
            lowered = url.lower()
            kind = "video" if lowered.endswith((".mp4", ".webm", ".mov")) or "generated_video" in lowered else "image"
        if any(item.get("url") == url for item in candidates):
            return
        candidates.append({"url": url, "kind": kind, "meta": meta or {}})

    for card in grok_agent_extract_card_json(event):
        card_type = str(card.get("type") or card.get("cardType") or "")
        video_chunk = card.get("video_chunk") if isinstance(card.get("video_chunk"), dict) else {}
        image_chunk = card.get("image_chunk") if isinstance(card.get("image_chunk"), dict) else {}
        if video_chunk.get("videoUrl"):
            add(video_chunk.get("videoUrl"), "video", {"card": card})
        if image_chunk.get("imageUrl"):
            add(image_chunk.get("imageUrl"), "image", {"card": card})
        for key in ("url", "mediaUrl", "imageUrl", "videoUrl"):
            if card.get(key):
                kind = "video" if "video" in card_type.lower() or str(card.get("mime_type") or "").startswith("video/") else ""
                add(card.get(key), kind, {"card": card})
    for url in grok_official_extract_urls(event, kind="video"):
        add(url, "video", {"source": "extract_urls"})
    for url in grok_official_extract_urls(event, kind="image"):
        add(url, "image", {"source": "extract_urls"})
    for url in recursive_find_values(
        event,
        lambda item: isinstance(item, str)
        and len(item) < 1500
        and (
            item.startswith(("http://", "https://", "users/", "/"))
            or "imagine-public.x.ai/" in item
            or "assets.grok.com/" in item
        )
        and (
            "/generated/" in item
            or "imagine-public.x.ai/" in item
            or "assets.grok.com/" in item
        )
        and not item.startswith("data:"),
        limit=40,
    ):
        add(url, "", {"source": "recursive"})
    return candidates


def grok_agent_parse_stream(text):
    events = grok_agent_parse_json_lines(text)
    media_candidates = []
    messages = []
    tool_calls = []
    conversation_id = ""
    response_ids = []
    progress = 0
    moderated = []
    for event in events:
        result = event.get("result") if isinstance(event, dict) else None
        if not isinstance(result, dict):
            continue
        conversation = result.get("conversation")
        if isinstance(conversation, dict) and conversation.get("conversationId"):
            conversation_id = conversation.get("conversationId")
        for response_key in ("response", "userResponse", "modelResponse"):
            response_value = result.get(response_key)
            if isinstance(response_value, dict) and response_value.get("responseId") and response_value.get("responseId") not in response_ids:
                response_ids.append(response_value.get("responseId"))
        if result.get("responseId") and result.get("responseId") not in response_ids:
            response_ids.append(result.get("responseId"))
        for card in grok_agent_extract_card_json(event):
            for chunk_name in ("video_chunk", "image_chunk"):
                chunk = card.get(chunk_name) if isinstance(card.get(chunk_name), dict) else {}
                chunk_progress = chunk.get("progress")
                if isinstance(chunk_progress, (int, float)):
                    progress = max(progress, int(chunk_progress))
                if "moderated" in chunk:
                    moderated.append(bool(chunk.get("moderated")))
        for candidate in grok_agent_media_candidates_from_event(event):
            if not any(item["url"] == candidate["url"] for item in media_candidates):
                media_candidates.append(candidate)
        token = result.get("token")
        if isinstance(token, str) and token:
            messages.append(token)
        response_value = result.get("response")
        if isinstance(response_value, dict) and isinstance(response_value.get("token"), str) and response_value.get("token"):
            messages.append(response_value.get("token"))
        model_response = result.get("modelResponse") or (response_value.get("modelResponse") if isinstance(response_value, dict) else None)
        if isinstance(model_response, dict) and model_response.get("message"):
            messages.append(model_response.get("message"))
        for tool in recursive_find_values(
            event,
            lambda item: isinstance(item, str) and item.startswith("{") and ("asset_id" in item or "resolution_name" in item or "prompt" in item),
            limit=20,
        ):
            if tool not in tool_calls:
                tool_calls.append(tool)
    return {
        "events": events,
        "event_count": len(events),
        "media_candidates": media_candidates,
        "messages": messages[-40:],
        "tool_calls": tool_calls[-20:],
        "conversation_id": conversation_id,
        "response_ids": response_ids[-20:],
        "progress": progress,
        "moderated": moderated[-20:],
    }


def grok_agent_request_body(message, parent_response_id=""):
    body = {
        "message": message,
        "disableSearch": False,
        "enableImageGeneration": True,
        "imageAttachments": [],
        "fileAttachments": [],
        "enableImageStreaming": True,
        "enableSideBySide": False,
        "sendFinalMetadata": True,
        "disableTextFollowUps": True,
        "disableMemory": False,
        "skipCancelCurrentInflightRequests": True,
        "modeId": "imagine-agent-mode",
    }
    if parent_response_id:
        body["parentResponseId"] = parent_response_id
    return body


def grok_agent_run(message, conversation_id="", parent_response_id="", timeout=420):
    conversation_id = (conversation_id or "").strip()
    endpoint = (
        f"https://grok.com/rest/app-chat/conversations/{conversation_id}/responses"
        if conversation_id
        else "https://grok.com/rest/app-chat/conversations/new"
    )
    body = grok_agent_request_body(message, parent_response_id=parent_response_id)
    reset_grok_official_progress(
        status="running",
        stage="agent",
        message="Grok Agent request sent",
        prompt_preview=message[:160],
        agent_conversation_id=conversation_id,
    )
    browser_response = grok_official_browser_fetch(endpoint, body=body, timeout=timeout)
    status = int(browser_response.get("status") or 0)
    text = browser_response.get("text") or ""
    if status >= 400:
        raise RuntimeError(f"Grok Agent request failed: {status} {text[:1200]}")
    parsed = grok_agent_parse_stream(text)
    parsed["request_body"] = body
    parsed["request_url"] = endpoint
    parsed["http_status"] = status
    update_grok_official_progress(
        status="done" if parsed.get("media_candidates") else "failed",
        stage="agent",
        message="Grok Agent response parsed",
        event_count=parsed.get("event_count"),
        progress=parsed.get("progress"),
        media_candidate_count=len(parsed.get("media_candidates") or []),
        agent_conversation_id=parsed.get("conversation_id") or conversation_id,
    )
    return parsed


def grok_agent_download_result(parsed):
    errors = []
    candidates = sorted(parsed.get("media_candidates") or [], key=lambda item: 0 if item.get("kind") == "video" else 1)
    for candidate in candidates:
        url = candidate.get("url")
        kind = candidate.get("kind") or "image"
        try:
            path, used_url = grok_official_download(url, media_path("video" if kind == "video" else "image"), kind=kind, return_url=True)
            return path, used_url, kind, candidate
        except Exception as exc:
            errors.append(f"{url}: {str(exc)[:500]}")
    if parsed.get("moderated") and all(parsed.get("moderated")):
        raise RuntimeError("Grok Agent result was moderated and no downloadable media was returned.")
    raise RuntimeError("Grok Agent 응답에서 다운로드 가능한 이미지/영상 URL을 찾지 못했습니다. " + "; ".join(errors[-5:]))


def grok_official_browser_generated_urls():
    tab = grok_imagine_tab()
    expression = r"""
(() => [...document.images]
  .map(img => img.currentSrc || img.src || "")
  .filter(src => src.includes("assets.grok.com") && src.includes("/generated/"))
  .map(src => src.split("?")[0]))
()
"""
    with CdpWebSocket(tab["webSocketDebuggerUrl"]) as cdp:
        result = cdp.call("Runtime.evaluate", {"expression": expression, "returnByValue": True}, timeout=15)
    return set(((result.get("result") or {}).get("value") or []))


def grok_official_browser_image_candidates(exclude_urls=None):
    exclude = set(exclude_urls or [])
    tab = grok_imagine_tab()
    expression = r"""
(() => {
  const seen = new Set();
  return [...document.images]
    .map((img, index) => {
      const src = img.currentSrc || img.src || "";
      const rect = img.getBoundingClientRect();
      const visible = rect.width > 20 && rect.height > 20 && rect.bottom > 0 && rect.right > 0 && rect.top < innerHeight && rect.left < innerWidth;
      const full = /\/image\.(?:jpe?g|png|webp)(?:\?|$)/i.test(src);
      const generated = src.includes("assets.grok.com") && src.includes("/generated/");
      const score = (visible ? 100000000 : 0) + (full ? 10000000 : 0) + Math.round(rect.width * rect.height * 100) + (img.naturalWidth * img.naturalHeight) + index;
      return {
        index,
        src,
        width: img.naturalWidth || 0,
        height: img.naturalHeight || 0,
        rendered_width: Math.round(rect.width),
        rendered_height: Math.round(rect.height),
        visible,
        full,
        generated,
        score,
      };
    })
    .filter(item => item.generated && item.src && item.width >= 256 && item.height >= 256)
    .sort((a, b) => b.score - a.score)
    .filter(item => {
      const key = item.src.split("?")[0];
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    })
    .slice(0, 12);
})()
"""
    with CdpWebSocket(tab["webSocketDebuggerUrl"]) as cdp:
        result = cdp.call("Runtime.evaluate", {"expression": expression, "returnByValue": True}, timeout=15)
    candidates = ((result.get("result") or {}).get("value") or [])
    if exclude:
        candidates = [item for item in candidates if (item.get("src") or "").split("?")[0] not in exclude]
    return candidates


def grok_official_fetch_browser_image(dest_dir, timeout=90, exclude_urls=None):
    deadline = time.time() + timeout
    last_error = ""
    last_candidates = []
    while time.time() < deadline:
        candidates = grok_official_browser_image_candidates(exclude_urls=exclude_urls)
        last_candidates = candidates
        urls = [item.get("src") for item in candidates if item.get("src")]
        if not urls:
            time.sleep(2)
            continue
        update_grok_official_progress(
            stage="browser-download",
            message="Grok 공식홈 탭에서 결과 이미지 저장 중",
            browser_candidate_count=len(urls),
            browser_candidate_url=urls[0],
        )
        tab = grok_imagine_tab()
        expression = f"""
(async () => {{
  const urls = {json.dumps(urls, ensure_ascii=False)};
  const meta = {json.dumps(candidates, ensure_ascii=False)};
  const toBase64 = (buffer) => {{
    const bytes = new Uint8Array(buffer);
    let binary = "";
    const chunk = 0x8000;
    for (let i = 0; i < bytes.length; i += chunk) {{
      binary += String.fromCharCode(...bytes.subarray(i, i + chunk));
    }}
    return btoa(binary);
  }};
  for (let i = 0; i < urls.length; i += 1) {{
    try {{
      const response = await fetch(urls[i], {{ credentials: "include", cache: "reload" }});
      if (!response.ok) {{
        continue;
      }}
      const blob = await response.blob();
      const buffer = await blob.arrayBuffer();
      return {{
        ok: true,
        url: urls[i],
        mime: blob.type || response.headers.get("content-type") || "image/jpeg",
        base64: toBase64(buffer),
        bytes: buffer.byteLength,
        candidate: meta[i] || null,
        page_url: location.href,
      }};
    }} catch (error) {{
      // Try the next rendered result URL.
    }}
  }}
  return {{ ok: false, error: "No rendered Grok image could be fetched in the official tab.", candidates: meta, page_url: location.href }};
}})()
"""
        with CdpWebSocket(tab["webSocketDebuggerUrl"]) as cdp:
            result = cdp.call(
                "Runtime.evaluate",
                {"expression": expression, "awaitPromise": True, "returnByValue": True},
                timeout=60,
            )
        value = (result.get("result") or {}).get("value") or {}
        if value.get("ok") and value.get("base64"):
            blob = base64.b64decode(value["base64"])
            mime = value.get("mime") or "image/jpeg"
            suffix = ".png" if "png" in mime else ".webp" if "webp" in mime else ".jpg"
            path = save_response_bytes(blob, dest_dir, suffix=suffix, filename_prefix="grok-official-browser-")
            return path, {
                "url": value.get("url") or "",
                "mime": mime,
                "bytes": value.get("bytes") or len(blob),
                "candidate": value.get("candidate") or {},
                "page_url": value.get("page_url") or "",
                "candidate_count": len(candidates),
            }
        last_error = value.get("error") or json.dumps(value, ensure_ascii=False)[:500]
        time.sleep(2)
    raise RuntimeError(f"Grok 공식홈 탭에서 렌더된 이미지 저장에 실패했습니다. {last_error} candidates={len(last_candidates)}")


def grok_official_wait_for_imagine_ready(cdp, timeout=20):
    deadline = time.time() + timeout
    expression = r"""
(() => {
  const box = document.querySelector('[contenteditable="true"][role="textbox"], [role="textbox"][contenteditable="true"], textarea');
  const submit = [...document.querySelectorAll('button')].find(button => {
    const text = (button.innerText || button.ariaLabel || button.getAttribute("aria-label") || "").trim();
    return button.type === "submit" || text === "제출" || text.toLowerCase() === "submit";
  });
  return { ready: Boolean(box && submit), url: location.href, title: document.title };
})()
"""
    last = {}
    while time.time() < deadline:
        result = cdp.call("Runtime.evaluate", {"expression": expression, "returnByValue": True}, timeout=5)
        last = (result.get("result") or {}).get("value") or {}
        if last.get("ready"):
            return last
        time.sleep(0.5)
    raise RuntimeError(f"Grok 공식홈 Imagine 입력창을 찾지 못했습니다. {last}")


def grok_official_submit_imagine_ui(prompt, model=None, aspect_ratio="2:3"):
    ensure_grok_chrome()
    tab = grok_imagine_tab()
    with CdpWebSocket(tab["webSocketDebuggerUrl"]) as cdp:
        current = cdp.call("Runtime.evaluate", {"expression": "location.href", "returnByValue": True}, timeout=5)
        current_url = ((current.get("result") or {}).get("value") or "")
        if "/imagine" not in current_url or "/post/" in current_url:
            cdp.call("Page.navigate", {"url": "https://grok.com/imagine"}, timeout=10)
            time.sleep(2)
        grok_official_wait_for_imagine_ready(cdp)
        configure_expr = f"""
(() => {{
  const clickButton = (matcher) => {{
    const buttons = [...document.querySelectorAll("button")];
    const button = buttons.find((item) => matcher((item.innerText || item.ariaLabel || item.getAttribute("aria-label") || "").trim(), item));
    if (button) {{
      button.click();
      return true;
    }}
    return false;
  }};
  const imageClicked = clickButton((text) => text === "이미지" || text.toLowerCase() === "image");
  const qualityWanted = {json.dumps(model in {"grok-imagine-image-quality", "grok-imagine-image-pro", "grok-imagine-image-quality-latest"})};
  const qualityClicked = qualityWanted ? clickButton((text) => text === "품질" || text.toLowerCase() === "quality") : false;
  return {{ imageClicked, qualityClicked, url: location.href }};
}})()
"""
        config_result = cdp.call("Runtime.evaluate", {"expression": configure_expr, "returnByValue": True}, timeout=10)
        focus_expr = r"""
(() => {
  const box = document.querySelector('[contenteditable="true"][role="textbox"], [role="textbox"][contenteditable="true"], textarea');
  if (!box) return { ok: false, error: "textbox not found" };
  box.focus();
  if (box.isContentEditable) {
    document.execCommand("selectAll", false, null);
    document.execCommand("delete", false, null);
    box.textContent = "";
    box.dispatchEvent(new InputEvent("input", { bubbles: true, inputType: "deleteContentBackward" }));
  } else {
    box.value = "";
    box.dispatchEvent(new Event("input", { bubbles: true }));
  }
  return { ok: true };
})()
"""
        focus_result = cdp.call("Runtime.evaluate", {"expression": focus_expr, "returnByValue": True}, timeout=10)
        focused = (focus_result.get("result") or {}).get("value") or {}
        if not focused.get("ok"):
            raise RuntimeError(f"Grok 공식홈 입력창 포커스 실패: {focused}")
        cdp.call("Input.insertText", {"text": prompt}, timeout=10)
        verify_expr = f"""
(() => {{
  const prompt = {json.dumps(prompt, ensure_ascii=False)};
  const box = document.querySelector('[contenteditable="true"][role="textbox"], [role="textbox"][contenteditable="true"], textarea');
  if (!box) return {{ ok: false, error: "textbox missing after input" }};
  const value = box.isContentEditable ? (box.innerText || box.textContent || "") : (box.value || "");
  if (!value.includes(prompt.slice(0, Math.min(prompt.length, 40)))) {{
    if (box.isContentEditable) {{
      box.textContent = prompt;
      box.dispatchEvent(new InputEvent("input", {{ bubbles: true, inputType: "insertText", data: prompt }}));
    }} else {{
      box.value = prompt;
      box.dispatchEvent(new Event("input", {{ bubbles: true }}));
    }}
  }}
  return {{ ok: true, valueLength: (box.isContentEditable ? (box.innerText || box.textContent || "") : (box.value || "")).length }};
}})()
"""
        verify_result = cdp.call("Runtime.evaluate", {"expression": verify_expr, "returnByValue": True}, timeout=10)
        submit_expr = r"""
(() => {
  const buttons = [...document.querySelectorAll("button")];
  const submit = buttons.find((button) => {
    const text = (button.innerText || button.ariaLabel || button.getAttribute("aria-label") || "").trim();
    return button.type === "submit" || text === "제출" || text.toLowerCase() === "submit";
  });
  if (!submit) return { ok: false, error: "submit button not found" };
  if (submit.disabled || submit.getAttribute("aria-disabled") === "true") return { ok: false, error: "submit button disabled" };
  submit.click();
  return { ok: true, url: location.href };
})()
"""
        submit_result = cdp.call("Runtime.evaluate", {"expression": submit_expr, "returnByValue": True}, timeout=10)
    return {
        "config": (config_result.get("result") or {}).get("value") or {},
        "verify": (verify_result.get("result") or {}).get("value") or {},
        "submit": (submit_result.get("result") or {}).get("value") or {},
    }


def grok_official_image_generate_ui(prompt, dest_dir, count=1, account_id=None, aspect_ratio="2:3", resolution="auto", model=None):
    account_id = account_id or active_grok_account_id()
    request_id = uuid.uuid4().hex
    try:
        browser_baseline_urls = grok_official_browser_generated_urls()
    except Exception:
        browser_baseline_urls = set()
    reset_grok_official_progress(
        status="running",
        stage="ui-submit",
        message="Submitting image prompt in Grok official UI",
        request_id=request_id,
        prompt_preview=prompt[:120],
        aspect_ratio=aspect_ratio,
        resolution=resolution,
        model=model or "grok-imagine-image-quality",
        account_id_present=bool(account_id),
        browser_baseline_count=len(browser_baseline_urls),
    )
    submit_meta = grok_official_submit_imagine_ui(prompt, model=model, aspect_ratio=aspect_ratio)
    if not (submit_meta.get("submit") or {}).get("ok"):
        raise RuntimeError(f"Grok 공식홈 UI 제출 실패: {submit_meta}")
    update_grok_official_progress(stage="browser-download", message="Waiting for newly rendered Grok official result")
    path, browser_saved = grok_official_fetch_browser_image(dest_dir, timeout=240, exclude_urls=browser_baseline_urls)
    width, height = image_dimensions(path) or (None, None)
    image_url = browser_saved.get("url") or ""
    image_id = ""
    generated_match = re.search(r"/generated/([^/]+)/", image_url)
    if generated_match:
        image_id = generated_match.group(1)
    update_grok_official_progress(
        status="done",
        stage="done",
        message="Grok official image generation completed",
        output_path=str(path),
        official_image_url=image_url,
        official_image_id=image_id,
        official_width=width,
        official_height=height,
        browser_saved=browser_saved,
    )
    return path, {
        "source": "grok_official_web",
        "official_mode": "quality" if model in {"grok-imagine-image-quality", "grok-imagine-image-pro", "grok-imagine-image-quality-latest"} else "speed",
        "official_transport": "browser_ui",
        "official_request_id": request_id,
        "official_requested_resolution": resolution,
        "resolution": resolution,
        "aspect_ratio": aspect_ratio,
        "official_image_url": image_url,
        "official_image_id": image_id,
        "official_width": width,
        "official_height": height,
        "official_completed": True,
        "official_browser_saved": browser_saved,
        "official_ui_submit": submit_meta,
        "grok_account_id": account_id,
    }


def grok_official_extract_urls(payload, kind="image"):
    def wanted(value):
        if not isinstance(value, str) or not value.startswith("http"):
            return False
        lowered = value.lower()
        if kind == "video":
            return ".mp4" in lowered or ".m3u8" in lowered or "video" in lowered
        return (
            "imagine-public.x.ai" in lowered
            or "assets.grok.com" in lowered
            or lowered.endswith((".jpg", ".jpeg", ".png", ".webp"))
            or "/images/" in lowered
            or "/generated/" in lowered
        )

    urls = []

    def walk(node):
        if len(urls) >= 30:
            return
        if isinstance(node, dict):
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)
        elif isinstance(node, str):
            if wanted(node):
                urls.append(node)
                return
            text = node.strip()
            if text and text[0] in "{[" and len(text) < 120000:
                try:
                    walk(json.loads(text))
                except Exception:
                    pass

    walk(payload)
    deduped = []
    for url in urls:
        if url not in deduped:
            deduped.append(url)
    return deduped


def grok_official_extract_post_id(payload):
    def wanted(value):
        return isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_-]{8,}", value or "")

    def walk(node, key_path=""):
        if isinstance(node, dict):
            for key, value in node.items():
                lowered = str(key).lower()
                if wanted(value) and (lowered in {"postid", "post_id", "post"} or ("post" in lowered and "id" in lowered)):
                    return value
                if lowered in {"post", "media_post", "mediapost"} and isinstance(value, dict) and wanted(value.get("id")):
                    return value.get("id")
                found = walk(value, f"{key_path}.{key}" if key_path else str(key))
                if found:
                    return found
        elif isinstance(node, list):
            for value in node:
                found = walk(value, key_path)
                if found:
                    return found
        elif isinstance(node, str):
            text = node.strip()
            if text and text[0] in "{[" and len(text) < 120000:
                try:
                    return walk(json.loads(text), key_path)
                except Exception:
                    return ""
        return ""

    found = walk(payload)
    if found:
        return found
    if isinstance(payload, dict) and wanted(payload.get("id")):
        return payload.get("id")
    return ""


def grok_official_extract_image_ids(payload):
    ids = []

    def wanted(value):
        return isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_-]{16,}", value or "")

    def walk(node):
        if len(ids) >= 20:
            return
        if isinstance(node, dict):
            for key, value in node.items():
                lowered = str(key).lower()
                if wanted(value) and (lowered in {"image_id", "imageid", "generated_image_id", "generatedimageid"} or ("image" in lowered and "id" in lowered)):
                    ids.append(value)
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)
        elif isinstance(node, str):
            text = node.strip()
            if text and text[0] in "{[" and len(text) < 120000:
                try:
                    walk(json.loads(text))
                except Exception:
                    pass

    walk(payload)
    deduped = []
    for value in ids:
        if value not in deduped:
            deduped.append(value)
    return deduped


def grok_official_preview_value(value, depth=0):
    if depth >= 4:
        return "..."
    if isinstance(value, dict):
        preview = {}
        for index, (key, item) in enumerate(value.items()):
            if index >= 20:
                preview["_truncated"] = f"{len(value) - index} more keys"
                break
            preview[str(key)] = grok_official_preview_value(item, depth + 1)
        return preview
    if isinstance(value, list):
        items = [grok_official_preview_value(item, depth + 1) for item in value[:8]]
        if len(value) > 8:
            items.append(f"... {len(value) - 8} more items")
        return items
    if isinstance(value, str):
        text = value.strip()
        if text and text[0] in "{[" and len(text) < 120000:
            try:
                return grok_official_preview_value(json.loads(text), depth + 1)
            except Exception:
                pass
        if text.startswith("data:image/"):
            return f"{text[:48]}... len={len(text)}"
        if len(text) > 240:
            return text[:240] + f"... len={len(text)}"
        return text
    return value


def grok_official_extract_media_refs(payload, limit=20):
    refs = []
    ref_keys = {
        "key", "uri", "fileuri", "file_uri", "file", "blob", "blobref", "blob_ref",
        "assetid", "asset_id", "mediaid", "media_id", "imageuri", "image_uri",
        "videouri", "video_uri",
    }

    def wanted(value):
        if not isinstance(value, str):
            return False
        text = value.strip()
        if not text or text.startswith(("http://", "https://", "data:")):
            return False
        if len(text) > 500:
            return False
        return (
            text.startswith(("users/", "user/", "uploads/", "files/", "content/", "media/", "blob:"))
            or "/content" in text
            or re.fullmatch(r"[A-Za-z0-9_-]{16,}", text) is not None
        )

    def add(value):
        if wanted(value) and value not in refs and len(refs) < limit:
            refs.append(value.strip())

    def walk(node):
        if len(refs) >= limit:
            return
        if isinstance(node, dict):
            node_type = str(node.get("type") or node.get("kind") or "").lower()
            if node_type in {"blob_ref", "file_ref", "media_ref", "asset_ref", "image_ref", "video_ref"}:
                for key in ("key", "uri", "fileUri", "file_uri", "id", "assetId", "asset_id", "mediaId", "media_id"):
                    add(node.get(key))
            for key, value in node.items():
                lowered = str(key).lower()
                if lowered in ref_keys or (("uri" in lowered or "url" in lowered) and isinstance(value, str)):
                    add(value)
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)
        elif isinstance(node, str):
            text = node.strip()
            if text and text[0] in "{[" and len(text) < 120000:
                try:
                    walk(json.loads(text))
                except Exception:
                    pass

    walk(payload)
    return refs


def grok_official_pipeline_event_summary(event):
    if not isinstance(event, dict):
        text = str(event)
        return text[:500]
    keys = (
        "type", "status", "current_status", "state", "code", "err_code",
        "message", "error", "reason", "postId", "post_id", "id",
        "image_id", "imageId", "job_id",
    )
    summary = {key: event.get(key) for key in keys if key in event}
    nested_keys = [key for key in ("output", "outputs", "result", "results", "media", "post", "data") if key in event]
    if nested_keys:
        summary["nested_keys"] = nested_keys
        for key in nested_keys:
            summary[f"{key}_preview"] = grok_official_preview_value(event.get(key))
    refs = grok_official_extract_media_refs(event, limit=8)
    if refs:
        summary["media_refs"] = refs
    if not summary:
        summary["keys"] = list(event.keys())[:30]
    return json_safe(summary)


def grok_official_pipeline_state(event):
    state = {
        "pipeline_status": "",
        "step_name": "",
        "step_status": "",
        "progress": None,
        "running": False,
        "completed": False,
        "failed": False,
        "blocked_reason": "",
        "message": "",
    }

    result = event.get("result") if isinstance(event, dict) else None
    if isinstance(result, dict):
        state["pipeline_status"] = str(result.get("pipelineStatus") or result.get("status") or "")
        progress = result.get("overallProgressPct")
        if isinstance(progress, (int, float)):
            state["progress"] = progress
        steps = result.get("steps") if isinstance(result.get("steps"), list) else []
        if steps:
            step = steps[-1] if isinstance(steps[-1], dict) else {}
            state["step_name"] = str(step.get("stepName") or "")
            state["step_status"] = str(step.get("status") or "")
            step_progress = step.get("progressPct")
            if isinstance(step_progress, (int, float)):
                state["progress"] = step_progress

    status_text = " ".join(
        str(value or "") for value in (
            state["pipeline_status"],
            state["step_status"],
            event.get("status") if isinstance(event, dict) else "",
            event.get("current_status") if isinstance(event, dict) else "",
            event.get("message") if isinstance(event, dict) else "",
            event.get("error") if isinstance(event, dict) else "",
        )
    ).lower()
    state["running"] = any(token in status_text for token in ("running", "draft_started", "in_progress", "processing"))
    state["completed"] = any(token in status_text for token in ("completed", "complete", "succeeded", "success", "finished", "ready", "posted"))
    state["failed"] = any(token in status_text for token in ("failed", "failure", "error", "rejected", "blocked", "cancelled", "canceled"))
    if state["failed"]:
        state["message"] = str((event.get("message") or event.get("error") or "") if isinstance(event, dict) else "")
    block_reason = grok_official_event_block_reason(event)
    if block_reason:
        state["blocked_reason"] = block_reason
        state["failed"] = True
    return state


def grok_official_pipeline_incomplete_message(kind, events, post_id, last_state):
    progress = last_state.get("progress")
    progress_text = f", progress={progress}" if progress is not None else ""
    status_text = ", ".join(
        part for part in (
            f"pipeline={last_state.get('pipeline_status')}" if last_state.get("pipeline_status") else "",
            f"step={last_state.get('step_name')}" if last_state.get("step_name") else "",
            f"step_status={last_state.get('step_status')}" if last_state.get("step_status") else "",
        ) if part
    )
    if status_text:
        status_text = f", {status_text}"
    return (
        "Grok 공식홈 pipeline 스트림이 완료 이벤트 전에 종료되었습니다. "
        "공식홈 작업이 아직 실행 중이거나 스트리밍 연결이 중간에 닫힌 상태입니다. "
        f"kind={kind}, events={len(events)}, post_id={post_id or '-'}{progress_text}{status_text}"
    )


def grok_official_upload_file(path, account_id=None):
    source = Path(path)
    if not source.exists():
        raise RuntimeError("업로드할 파일을 찾지 못했습니다.")
    mime = mimetypes.guess_type(source.name)[0] or "application/octet-stream"
    body = {
        "fileName": source.name,
        "fileMimeType": mime,
        "fileSource": "IMAGINE_SELF_UPLOAD_FILE_SOURCE",
        "content": base64.b64encode(source.read_bytes()).decode("ascii"),
    }
    headers = {**grok_web_headers(account_id), "Content-Type": "application/json"}
    response = requests.post("https://grok.com/rest/app-chat/upload-file", headers=headers, json=body, timeout=240)
    if response.status_code >= 400:
        detail = grok_official_json_error(response)
        lowered_detail = detail.lower()
        should_try_browser_upload = (
            response.status_code == 403
            and (
                "anti-bot" in lowered_detail
                or grok_official_is_cloudflare_challenge(detail)
            )
        )
        if should_try_browser_upload:
            browser_response = grok_official_browser_fetch(
                "https://grok.com/rest/app-chat/upload-file",
                body=body,
                timeout=240,
            )
            if int(browser_response.get("status") or 0) >= 400:
                browser_text = browser_response.get("text") or ""
                if grok_official_is_cloudflare_challenge(browser_text):
                    raise RuntimeError(grok_official_cloudflare_upload_message(browser_response.get("status"), browser_text))
                raise RuntimeError(f"Grok official browser upload failed: {browser_response.get('status')} {browser_text[:1200]}")
            try:
                payload = json.loads(browser_response.get("text") or "{}") or {}
            except json.JSONDecodeError as exc:
                raise RuntimeError(f"Grok official browser upload returned non-JSON response: {(browser_response.get('text') or '')[:1200]}") from exc
        else:
            if grok_official_is_cloudflare_challenge(detail):
                raise RuntimeError(grok_official_cloudflare_upload_message(response.status_code, detail))
            raise RuntimeError(f"Grok official upload failed: {response.status_code} {detail}")
    else:
        payload = response.json() or {}
    file_uri = payload.get("fileUri") or payload.get("file_uri")
    if not file_uri:
        strings = recursive_find_values(payload, lambda item: isinstance(item, str) and ("/content" in item or item.startswith("users/")), limit=5)
        file_uri = strings[0] if strings else ""
    return {
        "fileMetadataId": payload.get("fileMetadataId") or payload.get("file_metadata_id") or payload.get("id"),
        "fileUri": file_uri,
        "fileMimeType": payload.get("fileMimeType") or mime,
        "fileName": payload.get("fileName") or source.name,
        "raw": payload,
    }


def grok_official_blob_ref_for_image(path, account_id=None):
    source = Path(path)
    remote_url = remote_url_for_media_path(source)
    uploaded = grok_official_upload_file(source, account_id=account_id)
    key = uploaded.get("fileUri")
    if not key:
        raise RuntimeError("Grok 공식홈 업로드 응답에서 fileUri를 찾지 못했습니다.")
    return {
        "type": "blob_ref",
        "key": key,
        "mime_type": uploaded.get("fileMimeType") or (mimetypes.guess_type(source.name)[0] or "image/jpeg"),
    }, {
        "source_url": remote_url,
        "upload": uploaded,
        "official_source_type": "blob_ref",
        "official_source_mode": "self_upload_blob_ref",
        "official_uploaded_file_uri": key,
        "official_uploaded_file_metadata_id": uploaded.get("fileMetadataId"),
    }


def grok_official_pipeline_run(spec, kind="video", account_id=None):
    headers = {
        **grok_web_headers(account_id, accept="text/event-stream, application/json"),
        "Content-Type": "application/json",
    }
    request_body = {"spec_json": json.dumps(spec, ensure_ascii=False, separators=(",", ":"))}
    response = requests.post(
        "https://grok.com/rest/media/pipeline/run",
        headers=headers,
        json=request_body,
        stream=True,
        timeout=360,
    )
    if response.status_code >= 400:
        raise RuntimeError(grok_official_pipeline_error(response, kind=kind))
    events = []
    post_id = ""
    media_urls = []
    media_blobs = []
    media_blob_hashes = set()
    media_refs = []
    image_ids = []
    completed = False
    pipeline_failed = ""
    last_state = {}
    for raw_line in response.iter_lines(decode_unicode=True):
        if not raw_line:
            continue
        line = raw_line.strip()
        if not line or line.startswith(":") or line.startswith("event:"):
            continue
        if line.startswith("data:"):
            line = line[5:].strip()
        if not line or line == "[DONE]":
            break
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        events.append(event)
        post_id = post_id or grok_official_extract_post_id(event)
        last_state = grok_official_pipeline_state(event)
        if last_state.get("progress") is not None or last_state.get("pipeline_status") or last_state.get("step_status"):
            update_grok_official_progress(
                stage="pipeline",
                message="Grok official pipeline running",
                event_count=len(events),
                post_id=post_id,
                pipeline_status=last_state.get("pipeline_status"),
                pipeline_step=last_state.get("step_name"),
                pipeline_step_status=last_state.get("step_status"),
                progress=last_state.get("progress"),
            )
        if last_state.get("failed"):
            pipeline_failed = (
                last_state.get("blocked_reason")
                or last_state.get("message")
                or last_state.get("step_status")
                or last_state.get("pipeline_status")
                or "pipeline failed"
            )
        if last_state.get("completed"):
            completed = True
        media_urls.extend(url for url in grok_official_extract_urls(event, kind=kind) if url not in media_urls)
        result_payload = event.get("result") if isinstance(event, dict) and "result" in event else None
        for media_ref in grok_official_extract_media_refs(result_payload):
            if media_ref not in media_refs:
                media_refs.append(media_ref)
        if kind == "image":
            for blob in grok_official_extract_image_blobs(event, limit=12):
                digest = hashlib.sha1(blob).hexdigest()
                if digest not in media_blob_hashes:
                    media_blob_hashes.add(digest)
                    media_blobs.append(blob)
            for image_id in grok_official_extract_image_ids(event):
                if image_id not in image_ids:
                    image_ids.append(image_id)
        status_values = recursive_find_values(
            event,
            lambda item: isinstance(item, str) and item.lower() in {"completed", "complete", "done", "succeeded", "success", "successful", "finished", "ready"},
            limit=5,
        )
        if status_values:
            completed = True
    detail_payload = None
    if pipeline_failed and not (media_urls or media_blobs):
        update_grok_official_progress(
            status="failed",
            stage="pipeline-failed",
            message="Grok official pipeline failed",
            error=pipeline_failed,
            event_count=len(events),
            post_id=post_id,
            completed=completed,
            pipeline_state=last_state,
        )
        raise RuntimeError(f"Grok 공식홈 pipeline이 실패 상태로 종료되었습니다: {pipeline_failed}")
    if not completed and not (media_urls or media_blobs):
        message = grok_official_pipeline_incomplete_message(kind, events, post_id, last_state)
        update_grok_official_progress(
            status="failed",
            stage="pipeline-incomplete",
            message="Grok official pipeline stream ended before completion",
            error=message,
            event_count=len(events),
            post_id=post_id,
            completed=completed,
            pipeline_state=last_state,
        )
        raise RuntimeError(message)
    if post_id and not media_urls:
        detail_payload = grok_official_post_detail(post_id, account_id=account_id)
        media_urls.extend(grok_official_extract_urls(detail_payload, kind=kind))
        for media_ref in grok_official_extract_media_refs(detail_payload):
            if media_ref not in media_refs:
                media_refs.append(media_ref)
        if kind == "image":
            for blob in grok_official_extract_image_blobs(detail_payload, limit=12):
                digest = hashlib.sha1(blob).hexdigest()
                if digest not in media_blob_hashes:
                    media_blob_hashes.add(digest)
                    media_blobs.append(blob)
            for image_id in grok_official_extract_image_ids(detail_payload):
                if image_id not in image_ids:
                    image_ids.append(image_id)
    if kind == "image" and not media_urls and image_ids:
        media_urls.extend(grok_official_image_url(image_id) for image_id in image_ids if grok_official_image_url(image_id))
    if not media_urls and media_refs:
        media_urls.extend(media_refs)
    if not media_urls and not media_blobs:
        diagnostic = {
            "events": len(events),
            "post_id": post_id,
            "completed": completed,
            "image_ids": image_ids[:8],
            "media_refs": media_refs[:8],
            "detail": detail_payload,
            "last_events": [grok_official_pipeline_event_summary(event) for event in events[-5:]],
        }
        raise RuntimeError("Grok 공식홈 pipeline 응답에서 결과 미디어 URL/blob을 찾지 못했습니다. " + json.dumps(json_safe(diagnostic), ensure_ascii=False)[:1800])
    return {
        "events": events[-20:],
        "post_id": post_id,
        "completed": completed,
        "media_url": media_urls[0] if media_urls else "",
        "media_urls": media_urls,
        "media_blobs": media_blobs,
        "media_refs": media_refs,
        "detail": detail_payload,
        "request_body": request_body,
    }


def grok_official_post_detail(post_id, account_id=None):
    headers = grok_web_headers(account_id)
    candidates = [
        f"https://grok.com/rest/media/post/{post_id}",
        f"https://grok.com/rest/media/posts/{post_id}",
        f"https://grok.com/rest/media/post?id={urlencode({'': post_id})[1:]}",
        f"https://grok.com/rest/media/post?postId={urlencode({'': post_id})[1:]}",
        f"https://grok.com/rest/media/posts?id={urlencode({'': post_id})[1:]}",
        f"https://grok.com/rest/media/posts?postId={urlencode({'': post_id})[1:]}",
        f"https://grok.com/rest/app-chat/post/{post_id}",
        f"https://grok.com/rest/app-chat/posts/{post_id}",
        f"https://grok.com/rest/app-chat/get-post?postId={urlencode({'': post_id})[1:]}",
        f"https://grok.com/rest/app-chat/get-post?id={urlencode({'': post_id})[1:]}",
    ]
    errors = []
    for url in candidates:
        try:
            response = requests.get(url, headers=headers, timeout=60)
            if response.status_code < 400:
                return response.json()
            errors.append(f"{response.status_code} {url}")
        except Exception as exc:
            errors.append(f"{url}: {str(exc)[:120]}")
    return {"postId": post_id, "detail_errors": errors}


def grok_official_pipeline_video(prompt, source_url="", source_path=None, duration=10, resolution="720p", aspect_ratio="2:3", account_id=None):
    aspect_ratio = official_aspect_ratio(aspect_ratio, fallback="2:3")
    resolution = valid_video_resolution(resolution)
    duration = max(2, min(15, int(duration or 6)))
    inputs = {
        "video_prompt": {
            "type": "text",
            "fixed": {"type": "text", "value": prompt},
        },
    }
    node_inputs = {"prompt": "$input.video_prompt"}
    source_extra = {}
    if source_path:
        fixed, source_extra = grok_official_blob_ref_for_image(source_path, account_id=account_id)
        inputs["photo"] = {"type": "image", "label": "First frame", "fixed": fixed}
        node_inputs["image"] = "$input.photo"
    elif source_url:
        inputs["photo"] = {"type": "image", "label": "First frame", "fixed": {"type": "image_url", "url": source_url}}
        node_inputs["image"] = "$input.photo"
        source_extra["source_url"] = source_url
        source_extra["official_source_type"] = "image_url"
        source_extra["official_source_mode"] = "external_image_url"
    spec = {
        "version": 1,
        "inputs": inputs,
        "nodes": {
            "gen_video": {
                "type": "video_gen",
                "inputs": node_inputs,
                "params": {
                    "duration": duration,
                    "resolution_name": resolution,
                    "aspect_ratio": aspect_ratio,
                    "mode": "normal",
                },
            },
        },
        "outputs": {"video": "$gen_video.video"},
    }
    result = grok_official_pipeline_run(spec, kind="video", account_id=account_id)
    path = grok_official_download(result["media_url"], media_path("video"), kind="video")
    return path, {
        "source": "grok_official_web",
        "official_transport": "pipeline",
        "official_pipeline": "video_gen",
        "official_media_url": result["media_url"],
        "official_post_id": result.get("post_id"),
        "official_completed": result.get("completed"),
        "official_events": result.get("events"),
        "official_spec": spec,
        "official_request_body": result.get("request_body"),
        "duration": duration,
        "resolution": resolution,
        "aspect_ratio": aspect_ratio,
        "grok_account_id": account_id or active_grok_account_id(),
        **source_extra,
    }


def grok_official_pipeline_image_edit(prompt, source_paths, dest_dir, aspect_ratio="auto", resolution="auto", account_id=None):
    sources = [Path(path) for path in source_paths if path]
    if not sources:
        raise RuntimeError("편집할 이미지가 없습니다.")
    aspect_ratio = official_aspect_ratio(aspect_ratio, fallback="2:3")
    fixed, source_extra = grok_official_blob_ref_for_image(sources[0], account_id=account_id)
    inputs = {
        "image_prompt": {"type": "text", "fixed": {"type": "text", "value": prompt}},
        "photo": {"type": "image", "label": "Source image", "fixed": fixed},
    }
    spec = {
        "version": 1,
        "inputs": inputs,
        "nodes": {
            "edit_image": {
                "type": "image_edit",
                "inputs": {
                    "prompt": "$input.image_prompt",
                    "image": "$input.photo",
                },
                "params": {
                    "aspect_ratio": aspect_ratio,
                    "mode": "normal",
                },
            },
        },
        "outputs": {"image": "$edit_image.image"},
    }
    if resolution and resolution != "auto":
        spec["nodes"]["edit_image"]["params"]["resolution"] = resolution
        spec["nodes"]["edit_image"]["params"]["imageGenResolution"] = resolution
    result = grok_official_pipeline_run(spec, kind="image", account_id=account_id)
    media_blobs = result.get("media_blobs") or []
    if media_blobs:
        blob = max(media_blobs, key=len)
        path = save_response_bytes(blob, dest_dir, suffix=response_suffix_from_bytes(blob, ".jpg"))
        used_media_url = result.get("media_url") or ""
    else:
        download_errors = []
        path = None
        used_media_url = ""
        for media_url in result.get("media_urls") or [result.get("media_url")]:
            if not media_url:
                continue
            try:
                path, used_media_url = grok_official_download(media_url, dest_dir, kind="image", return_url=True)
                break
            except Exception as exc:
                download_errors.append(f"{media_url}: {str(exc)[:500]}")
        if not path:
            raise RuntimeError("Grok 공식홈 이미지 편집 결과 다운로드에 실패했습니다. " + "; ".join(download_errors))
    image_id = official_image_id_from_url(used_media_url)
    return path, {
        "source": "grok_official_web",
        "official_transport": "pipeline",
        "official_pipeline": "image_edit",
        "official_image_url": used_media_url,
        "official_image_id": image_id,
        "official_post_id": result.get("post_id"),
        "official_requested_resolution": resolution,
        "resolution": resolution,
        "aspect_ratio": aspect_ratio,
        "official_events": result.get("events"),
        "official_spec": spec,
        "official_request_body": result.get("request_body"),
        "official_media_blob_count": len(media_blobs),
        "source_count": len(sources),
        "grok_account_id": account_id or active_grok_account_id(),
        **source_extra,
    }


def grok_official_image_edit_reference_for_path(path, account_id=None):
    source = Path(path)
    item = find_metadata_by_file_path(source)
    extra = item.get("extra") if isinstance(item, dict) and isinstance(item.get("extra"), dict) else {}
    remote_url = remote_url_for_media_path(source)
    generated_id = (
        official_generated_id_from_url(extra.get("official_image_url") or "")
        or official_generated_id_from_url(extra.get("official_media_url") or "")
        or official_generated_id_from_url(extra.get("official_output_path") or "")
        or official_generated_id_from_url(remote_url or "")
    )
    official_id = generated_id or (
        extra.get("official_image_id")
        or official_image_id_from_url(extra.get("official_image_url") or "")
    )
    if official_id:
        reference = grok_official_generated_asset_image_url(
            official_id,
            account_id=account_id,
            source_url=remote_url or extra.get("official_image_url") or extra.get("official_media_url") or "",
        )
        return reference, {
            "source_url": remote_url,
            "official_source_type": "official_post",
            "official_source_mode": "official_post_image_reference",
            "official_parent_post_id": official_id,
            "official_root_post_id": generated_id or official_id,
            "official_is_root_user_uploaded": False,
        }
    if remote_url and "imagine-public.x.ai" in remote_url:
        image_id = official_image_id_from_url(remote_url)
        return remote_url, {
            "source_url": remote_url,
            "official_source_type": "official_public_image_url",
            "official_source_mode": "official_public_image_reference",
            "official_parent_post_id": image_id,
            "official_root_post_id": image_id,
            "official_is_root_user_uploaded": False,
        }
    uploaded = grok_official_upload_file(source, account_id=account_id)
    key = uploaded.get("fileUri")
    if not key:
        raise RuntimeError("Grok official upload response did not include fileUri.")
    return key, {
        "source_url": remote_url,
        "upload": uploaded,
        "official_source_type": "uploaded_file_uri",
        "official_source_mode": "app_chat_image_reference_upload",
        "official_uploaded_file_uri": key,
        "official_uploaded_file_metadata_id": uploaded.get("fileMetadataId"),
        "official_is_root_user_uploaded": True,
    }


def grok_official_path_has_post_reference(path):
    source = Path(path)
    item = find_metadata_by_file_path(source)
    extra = item.get("extra") if isinstance(item, dict) and isinstance(item.get("extra"), dict) else {}
    official_id = (
        extra.get("official_image_id")
        or official_image_id_from_url(extra.get("official_image_url") or "")
        or official_generated_id_from_url(extra.get("official_image_url") or "")
        or official_generated_id_from_url(extra.get("official_output_path") or "")
    )
    if official_id:
        return True
    remote_url = remote_url_for_media_path(source)
    return bool(
        remote_url
        and (
            "imagine-public.x.ai" in remote_url
            or ("assets.grok.com" in remote_url and "/generated/" in remote_url)
        )
    )


def grok_official_app_chat_image_edit(prompt, source_paths, dest_dir, aspect_ratio="auto", resolution="auto", account_id=None):
    sources = [Path(path) for path in source_paths if path]
    if not sources:
        raise RuntimeError("No source image was provided for Grok official image edit.")
    account_id = account_id or active_grok_account_id()
    image_reference, source_extra = grok_official_image_edit_reference_for_path(sources[0], account_id=account_id)
    image_edit_config = {
        "imageReferences": [image_reference],
    }
    if source_extra.get("official_source_type") == "uploaded_file_uri":
        image_edit_config["isRootUserUploaded"] = True
    parent_post_id = source_extra.get("official_parent_post_id")
    if parent_post_id:
        image_edit_config["parentPostId"] = parent_post_id
    request_body = {
        "temporary": True,
        "modelName": "imagine-image-edit",
        "message": prompt,
        "enableImageGeneration": True,
        "returnImageBytes": False,
        "returnRawGrokInXaiRequest": False,
        "enableImageStreaming": True,
        "imageGenerationCount": 2,
        "forceConcise": False,
        "enableSideBySide": True,
        "sendFinalMetadata": True,
        "isReasoning": False,
        "disableTextFollowUps": True,
        "responseMetadata": {
            "modelConfigOverride": {
                "modelMap": {
                    "imageEditModel": "imagine",
                    "imageEditModelConfig": image_edit_config,
                }
            }
        },
        "disableMemory": False,
        "forceSideBySide": False,
    }
    reset_grok_official_progress(
        status="running",
        stage="app-chat-edit",
        message="Grok official image edit request sent",
        prompt_preview=prompt[:120],
        source_mode=source_extra.get("official_source_mode"),
        account_id_present=bool(account_id),
    )
    browser_response = grok_official_browser_fetch(
        "https://grok.com/rest/app-chat/conversations/new",
        body=request_body,
        timeout=360,
        target_post_id=parent_post_id,
    )
    if int(browser_response.get("status") or 0) >= 400:
        raise RuntimeError(f"Grok official browser image edit request failed: {browser_response.get('status')} {(browser_response.get('text') or '')[:1200]}")
    events = []
    all_urls = []
    final_urls = []
    preview_urls = []
    image_ids = []
    asset_ids = []
    moderated = []
    r_rated = []
    messages = []
    stream_errors = []
    for raw_line in (browser_response.get("text") or "").splitlines():
        if not raw_line:
            continue
        line = raw_line.strip()
        if line.startswith("data:"):
            line = line[5:].strip()
        if not line or line == "[DONE]":
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        events.append(event)
        for url in grok_official_extract_urls(event, kind="image"):
            if url not in all_urls:
                all_urls.append(url)
        for ref in grok_official_extract_media_refs(event, limit=20):
            if ref not in all_urls:
                all_urls.append(ref)
        result = event.get("result") if isinstance(event, dict) else None
        response_payload = result.get("response") if isinstance(result, dict) else None
        if not isinstance(response_payload, dict):
            continue
        stream = response_payload.get("streamingImageGenerationResponse")
        if isinstance(stream, dict):
            image_url = stream.get("imageUrl") or stream.get("url")
            if image_url and image_url not in all_urls:
                all_urls.append(image_url)
            if stream.get("imageId") and stream.get("imageId") not in image_ids:
                image_ids.append(stream.get("imageId"))
            if stream.get("assetId") and stream.get("assetId") not in asset_ids:
                asset_ids.append(stream.get("assetId"))
            if "moderated" in stream:
                moderated.append(bool(stream.get("moderated")))
            if "rRated" in stream:
                r_rated.append(bool(stream.get("rRated")))
            progress = stream.get("progress") or 0
            if image_url:
                if progress >= 100 and "-part-" not in image_url:
                    if image_url not in final_urls:
                        final_urls.append(image_url)
                elif image_url not in preview_urls:
                    preview_urls.append(image_url)
            update_grok_official_progress(
                stage="app-chat-edit",
                message="Grok official image edit streaming",
                progress=progress,
                image_url_found=bool(image_url),
                event_count=len(events),
            )
        model_response = response_payload.get("modelResponse")
        if isinstance(model_response, dict):
            for url in model_response.get("generatedImageUrls") or []:
                if url not in final_urls:
                    final_urls.append(url)
                if url not in all_urls:
                    all_urls.append(url)
            if model_response.get("message"):
                messages.append(model_response.get("message"))
        token = response_payload.get("token")
        if isinstance(token, str) and token:
            messages.append(token)
        for error in response_payload.get("streamErrors") or []:
            stream_errors.append(error)
    candidate_urls = []
    for url in final_urls + all_urls + preview_urls:
        if url and url not in candidate_urls:
            candidate_urls.append(url)
    if moderated and all(moderated) and not candidate_urls:
        raise RuntimeError("Grok official image edit result was moderated and no downloadable image was returned.")
    download_errors = []
    path = None
    used_media_url = ""
    for media_url in candidate_urls:
        try:
            path, used_media_url = grok_official_download(media_url, dest_dir, kind="image", return_url=True)
            break
        except Exception as exc:
            download_errors.append(f"{media_url}: {str(exc)[:500]}")
    if not path:
        diagnostic = {
            "events": len(events),
            "final_urls": final_urls[:8],
            "all_urls": all_urls[:8],
            "image_ids": image_ids[:8],
            "asset_ids": asset_ids[:8],
            "moderated": moderated[-8:],
            "stream_errors": stream_errors[-5:],
            "last_events": [grok_official_pipeline_event_summary(event) for event in events[-5:]],
            "download_errors": download_errors[-5:],
        }
        raise RuntimeError("Grok official app-chat image edit response did not include a downloadable result. " + json.dumps(json_safe(diagnostic), ensure_ascii=False)[:1800])
    image_id = official_image_id_from_url(used_media_url) or official_generated_id_from_url(used_media_url)
    update_grok_official_progress(
        status="done",
        stage="done",
        message="Grok official image edit completed",
        output_path=str(path),
        official_image_url=used_media_url,
        official_image_id=image_id,
    )
    return path, {
        "source": "grok_official_web",
        "official_transport": "app_chat_conversations",
        "official_pipeline": "image_edit",
        "official_image_url": used_media_url,
        "official_image_urls": candidate_urls,
        "official_image_id": image_id,
        "official_asset_ids": asset_ids,
        "official_image_ids": image_ids,
        "official_requested_resolution": resolution,
        "resolution": resolution,
        "aspect_ratio": aspect_ratio,
        "official_events": events[-20:],
        "official_request_body": request_body,
        "official_moderated_flags": moderated,
        "official_r_rated_flags": r_rated,
        "official_messages": messages[-5:],
        "official_stream_errors": stream_errors[-5:],
        "source_count": len(sources),
        "grok_account_id": account_id,
        **source_extra,
    }


def grok_official_is_antibot_error(error):
    detail = error_detail_text(error).lower()
    return (
        "anti-bot" in detail
        or "request rejected by anti-bot" in detail
        or ("\"code\":7" in detail and "rejected" in detail)
        or ("\"code\": 7" in detail and "rejected" in detail)
    )


def grok_official_image_edit(prompt, source_paths, dest_dir, aspect_ratio="auto", resolution="auto", account_id=None):
    sources = [Path(path) for path in source_paths if path]
    if sources and grok_official_path_has_post_reference(sources[0]):
        try:
            path, extra = grok_official_app_chat_image_edit(
                prompt,
                sources,
                dest_dir,
                aspect_ratio=aspect_ratio,
                resolution=resolution,
                account_id=account_id,
            )
            extra["official_preferred_transport"] = "app_chat_conversations"
            extra["official_preferred_reason"] = "official_post_reference"
            return path, extra
        except Exception as exc:
            app_chat_error = error_detail_text(exc)
            if not checked(os.getenv("GROK_OFFICIAL_PIPELINE_EDIT_FALLBACK", "")):
                raise
            update_grok_official_progress(
                status="running",
                stage="pipeline-edit-fallback",
                message="Grok official app-chat image edit failed; trying optional pipeline fallback",
                app_chat_error=app_chat_error[:1200],
            )
            path, extra = grok_official_pipeline_image_edit(
                prompt,
                sources,
                dest_dir,
                aspect_ratio=aspect_ratio,
                resolution=resolution,
                account_id=account_id,
            )
            extra["official_fallback_from"] = "app_chat_image_edit"
            extra["official_fallback_reason"] = "app_chat_failed"
            extra["official_app_chat_error"] = app_chat_error[:1200]
            return path, extra
    try:
        return grok_official_pipeline_image_edit(
            prompt,
            sources,
            dest_dir,
            aspect_ratio=aspect_ratio,
            resolution=resolution,
            account_id=account_id,
        )
    except Exception as exc:
        pipeline_error = error_detail_text(exc)
        if not checked(os.getenv("GROK_OFFICIAL_APP_CHAT_EDIT_FALLBACK", "")):
            raise
        update_grok_official_progress(
            status="running",
            stage="app-chat-edit-fallback",
            message="Grok official pipeline image edit failed; trying optional app-chat fallback",
            pipeline_error=pipeline_error[:1200],
        )
        try:
            path, extra = grok_official_app_chat_image_edit(
                prompt,
                source_paths,
                dest_dir,
                aspect_ratio=aspect_ratio,
                resolution=resolution,
                account_id=account_id,
            )
        except Exception as fallback_exc:
            raise RuntimeError(
                "Grok 공식홈 이미지 편집 pipeline 요청이 실패했고, app-chat fallback도 실패했습니다. "
                f"pipeline={pipeline_error[:900]} app_chat={error_detail_text(fallback_exc)[:900]}"
            ) from fallback_exc
        extra["official_fallback_from"] = "pipeline_image_edit"
        extra["official_fallback_reason"] = "pipeline_failed"
        extra["official_pipeline_error"] = pipeline_error[:1200]
        return path, extra


def grok_official_image_generate_ws(prompt, dest_dir, count=1, account_id=None, aspect_ratio="2:3", resolution="auto", model=None):
    account_id = account_id or active_grok_account_id()
    aspect_ratio = official_aspect_ratio(aspect_ratio, fallback="2:3")
    request_id = str(uuid.uuid4())
    timestamp = int(time.time() * 1000)
    payload_timestamp = timestamp + 90
    headers = grok_web_headers(account_id, accept="*/*")
    ws_headers = {
        "Cookie": headers["Cookie"],
        "Origin": "https://grok.com",
        "Referer": "https://grok.com/",
        "User-Agent": headers["User-Agent"],
        "Accept-Language": headers.get("Accept-Language", "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7"),
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Sec-Fetch-Dest": "websocket",
        "Sec-Fetch-Mode": "websocket",
        "Sec-Fetch-Site": "same-origin",
    }
    if account_id:
        ws_headers["x-grok-account-id"] = account_id
    official_model_name = grok_official_image_model_name(model)
    properties = {
        "section_count": 0,
        "is_kids_mode": False,
        "enable_nsfw": True,
        "skip_upsampler": False,
        "enable_side_by_side": True,
        "is_initial": False,
        "aspect_ratio": aspect_ratio,
        "enable_pro": grok_official_image_enable_pro(model),
    }
    if official_model_name:
        properties["image_model_name"] = official_model_name
    official_resolution_name = grok_official_image_resolution_name(resolution)
    if official_resolution_name:
        properties["resolution_name"] = official_resolution_name
    payload = {
        "type": "conversation.item.create",
        "timestamp": payload_timestamp,
        "item": {
            "type": "message",
            "content": [
                {
                    "requestId": request_id,
                    "text": prompt,
                    "type": "input_text",
                    "properties": properties,
                }
            ],
        },
    }
    blobs = []
    json_events = []
    image_url = ""
    image_urls = []
    image_id = ""
    completed = False
    blocked_reason = ""
    ws_error_message = ""
    deadline = time.time() + 240
    reset_grok_official_progress(
        status="running",
        stage="connect",
        message="Grok official image WebSocket connecting",
        request_id=request_id,
        prompt_preview=prompt[:120],
        aspect_ratio=aspect_ratio,
        resolution=resolution,
        model=model or "grok-imagine-image-quality",
        account_id_present=bool(account_id),
        event_count=0,
        blob_count=0,
        image_url_found=False,
        completed=False,
        official_payload_properties=properties,
    )
    with MinimalWebSocket("wss://grok.com/ws/imagine/listen", headers=ws_headers, timeout=30) as ws:
        update_grok_official_progress(stage="send", message="Grok official image request sent")
        ws.send_json({
            "type": "conversation.item.create",
            "timestamp": timestamp,
            "item": {"type": "message", "content": [{"type": "reset"}]},
        })
        ws.send_json(payload)
        update_grok_official_progress(stage="listen", message="Waiting for Grok official image response")
        while time.time() < deadline:
            try:
                kind, data = ws.recv()
            except socket.timeout:
                update_grok_official_progress(
                    stage="listen",
                    message="Waiting for Grok official image response",
                    event_count=len(json_events),
                    blob_count=len(blobs),
                    image_url_found=bool(image_url),
                )
                if blobs:
                    break
                continue
            except RuntimeError as exc:
                closed_error = ws_error_message or grok_official_ws_closed_message(
                    json_events,
                    blobs,
                    account_id,
                    completed=completed,
                    blocked_reason=blocked_reason,
                    image_urls=[*image_urls, image_url] if image_url else image_urls,
                )
                update_grok_official_progress(
                    status="failed" if not (completed and (blobs or image_url or image_urls)) else "running",
                    stage="closed",
                    message="Grok official WebSocket closed",
                    error=closed_error,
                    event_count=len(json_events),
                    blob_count=len(blobs),
                    image_url_found=bool(image_url or image_urls),
                    completed=completed,
                    blocked_reason=blocked_reason,
                    ws_error=ws_error_message,
                )
                if completed and (blobs or image_url or image_urls):
                    break
                if ws_error_message:
                    raise RuntimeError(ws_error_message) from exc
                raise RuntimeError(closed_error) from exc
            if kind == "binary":
                if len(data) > 1024:
                    blobs.append(data)
                    update_grok_official_progress(
                        stage="receive",
                        message="Grok official binary image blob received",
                        event_count=len(json_events),
                        blob_count=len(blobs),
                        image_url_found=bool(image_url),
                    )
                continue
            if kind == "close":
                update_grok_official_progress(
                    stage="closed",
                    message="Grok official WebSocket close frame received",
                    event_count=len(json_events),
                    blob_count=len(blobs),
                    image_url_found=bool(image_url),
                    completed=completed,
                    blocked_reason=blocked_reason,
                )
                break
            if kind != "text":
                continue
            try:
                event = json.loads(data)
            except json.JSONDecodeError:
                continue
            json_events.append(event)
            event_error_message = grok_official_ws_error_message(event)
            if event_error_message and not ws_error_message:
                ws_error_message = event_error_message
            event_block_reason = grok_official_event_block_reason(event)
            if event_block_reason and not blocked_reason:
                blocked_reason = event_block_reason
            event_blobs = [] if event_block_reason else grok_official_extract_image_blobs(event)
            if event_blobs:
                blobs.extend(event_blobs)
                update_grok_official_progress(
                    stage="receive",
                    message="Grok official JSON image blob received",
                    event_count=len(json_events),
                    blob_count=len(blobs),
                    image_url_found=bool(image_url),
                    completed=completed,
                    blocked_reason=blocked_reason,
                )
            urls = grok_official_extract_urls(event, kind="image")
            for url in urls:
                if url not in image_urls:
                    image_urls.append(url)
            if urls and not image_url:
                image_url = urls[0]
                image_id = official_image_id_from_url(image_url)
            id_values = recursive_find_values(
                event,
                lambda item: isinstance(item, str) and re.fullmatch(r"[A-Za-z0-9_-]{16,}", item or ""),
                limit=10,
            )
            if not image_id:
                for value in id_values:
                    if value != request_id:
                        image_id = value
                        break
            done_values = recursive_find_values(
                event,
                lambda item: isinstance(item, str) and item.lower() in {"completed", "complete", "done", "succeeded"},
                limit=5,
            )
            if done_values:
                completed = True
            update_grok_official_progress(
                stage="receive",
                message="Grok official image event received",
                event_count=len(json_events),
                blob_count=len(blobs),
                image_url_found=bool(image_url),
                completed=completed,
                blocked_reason=blocked_reason,
                ws_error=ws_error_message,
                last_event_type=event.get("type") if isinstance(event, dict) else "",
                last_event_status=(event.get("current_status") or event.get("status") or "") if isinstance(event, dict) else "",
                last_error_code=(event.get("err_code") or event.get("code") or "") if isinstance(event, dict) else "",
                last_error_message=(event.get("err_msg") or event.get("message") or event.get("error") or "") if isinstance(event, dict) else "",
            )
            if done_values:
                if blobs:
                    break
    if ws_error_message:
        update_grok_official_progress(
            status="failed",
            stage="error",
            message="Grok official WebSocket returned an error",
            error=ws_error_message,
            event_count=len(json_events),
            blob_count=len(blobs),
            image_url_found=bool(image_url),
            completed=completed,
        )
        raise RuntimeError(ws_error_message)
    if blocked_reason and not (blobs or image_url or image_urls):
        blocked_message = grok_official_image_blocked_message(blocked_reason)
        update_grok_official_progress(
            status="failed",
            stage="blocked",
            message="Grok official request was blocked or moderated",
            error=blocked_message,
            event_count=len(json_events),
            blob_count=len(blobs),
            image_url_found=bool(image_url or image_urls),
            completed=completed,
        )
        raise RuntimeError(blocked_message)
    if not completed:
        update_grok_official_progress(
            status="failed",
            stage="incomplete",
            message="Grok official image response closed before completion",
            error="missing completed event",
            event_count=len(json_events),
            blob_count=len(blobs),
            image_url_found=bool(image_url),
            completed=completed,
        )
        raise RuntimeError(
            grok_official_ws_closed_message(
                json_events,
                blobs,
                account_id,
                completed=completed,
                blocked_reason=blocked_reason,
                image_urls=[*image_urls, image_url] if image_url else image_urls,
            )
        )
    path = None
    output_paths = []
    downloaded_urls = []
    download_errors = []
    if blobs:
        update_grok_official_progress(stage="save", message="Grok 공식홈 WebSocket 이미지 blob 저장 중")
        seen_blob_hashes = set()
        for blob in blobs:
            digest = hashlib.sha1(blob).hexdigest()
            if digest in seen_blob_hashes:
                continue
            seen_blob_hashes.add(digest)
            output_paths.append(save_response_bytes(blob, dest_dir, suffix=response_suffix_from_bytes(blob, ".jpg")))
        path = output_paths[0] if output_paths else None
    elif image_url or image_urls:
        for url in ([*image_urls] if image_urls else [image_url]):
            if not url or url in downloaded_urls:
                continue
            try:
                downloaded_path, used_url = grok_official_download(url, dest_dir, kind="image", return_url=True)
                output_paths.append(downloaded_path)
                downloaded_urls.append(used_url)
            except Exception as exc:
                download_errors.append(f"{url}: {str(exc)[:500]}")
        if output_paths:
            path = output_paths[0]
            image_url = downloaded_urls[0] if downloaded_urls else image_url
        else:
            image_url = image_urls[0] if image_urls else image_url
        candidates = grok_official_download_candidates(image_url, kind="image")
        update_grok_official_progress(
            stage="download",
            message="Grok 공식홈 WebSocket 이미지 URL 다운로드 중",
            download_candidates=candidates,
        )
        if not output_paths and not download_errors:
            path, image_url = grok_official_download(image_url, dest_dir, kind="image", return_url=True)
            output_paths.append(path)
            downloaded_urls.append(image_url)
        if not output_paths and download_errors:
            update_grok_official_progress(
                status="failed",
                stage="failed",
                message="Grok 공식홈 이미지 다운로드 실패",
                error="; ".join(download_errors),
                event_count=len(json_events),
                blob_count=len(blobs),
                image_url_found=bool(image_url),
                download_candidates=candidates,
                completed=completed,
            )
            raise RuntimeError("; ".join(download_errors))
    else:
        error_message = "Grok 공식홈 WebSocket 응답에서 이미지 blob 또는 URL을 받지 못했습니다."
        update_grok_official_progress(
            status="failed",
            stage="failed",
            message="Grok 공식홈 이미지 생성 실패",
            error=error_message,
            event_count=len(json_events),
            blob_count=len(blobs),
            image_url_found=bool(image_url),
            completed=completed,
        )
        raise RuntimeError(error_message)
    if not image_url and image_id:
        image_url = grok_official_image_url(image_id)
    if image_url and image_url not in image_urls:
        image_urls.insert(0, image_url)
    if path and not output_paths:
        output_paths = [path]
    output_public_paths = [public_path(item) for item in output_paths]
    output_dimensions = [image_dimensions(item) or (None, None) for item in output_paths]
    width, height = image_dimensions(path) or (None, None)
    update_grok_official_progress(
        status="done",
        stage="done",
        message="Grok 공식홈 이미지 생성 완료",
        event_count=len(json_events),
        blob_count=len(blobs),
        image_url_found=bool(image_url),
        completed=completed,
        output_path=str(path),
        output_paths=[str(item) for item in output_paths],
        saved_count=len(output_paths),
        official_image_url=image_url,
        official_image_id=image_id,
    )
    return path, {
        "source": "grok_official_web",
        "official_mode": "quality" if properties.get("enable_pro") else "speed",
        "official_transport": "websocket",
        "official_image_model": model,
        "official_image_model_name": official_model_name,
        "official_request_id": request_id,
        "official_requested_resolution": resolution,
        "official_resolution_name": official_resolution_name,
        "official_payload_properties": properties,
        "resolution": resolution,
        "aspect_ratio": aspect_ratio,
        "official_image_url": image_url,
        "official_image_urls": image_urls,
        "official_image_id": image_id,
        "official_width": width,
        "official_height": height,
        "official_output_count": len(output_paths),
        "official_output_paths": output_public_paths,
        "official_output_file_paths": [str(item) for item in output_paths],
        "official_output_dimensions": [{"width": item[0], "height": item[1]} for item in output_dimensions],
        "official_downloaded_urls": downloaded_urls,
        "official_download_errors": download_errors,
        "official_partial_blocked_reason": blocked_reason or "",
        "official_completed": completed,
        "official_events": json_events[-20:],
        "grok_account_id": account_id,
    }


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


def codex_proxy_running(cfg=None, timeout=3):
    cfg = cfg or config()
    base = (cfg.get("codex_proxy_base_url") or "").rstrip("/")
    if not base:
        return False
    try:
        response = requests.get(base + "/api/health", timeout=timeout)
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
        "image_model": cfg.get("codex_image_model"),
        "detail": "",
        "log_path": str(codex_proxy_log_path()),
        "log_tail": "",
    }
    try:
        log_text = codex_proxy_log_path().read_text(encoding="utf-8", errors="replace")
        payload["log_tail"] = log_text[-2000:]
    except OSError:
        pass
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
        if found and codex_proxy_command_usable(found):
            return [found, "serve"]
        for folder in known_dirs:
            candidate = folder / name if folder else None
            if candidate and candidate.exists() and codex_proxy_command_usable(candidate):
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


def codex_proxy_command_usable(command_path):
    path = Path(command_path)
    name = path.name.lower()
    if name not in {"ima2", "ima2.cmd", "ima2-gen", "ima2-gen.cmd"}:
        return True
    package = path.parent / "node_modules" / "ima2-gen" / "bin" / "ima2.js"
    return package.exists()


def codex_proxy_log_path():
    path = PRIVATE_STATE_DIR / "codex-proxy.log"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


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
    if len(video_paths) > 80:
        raise ValueError("한 번에 최대 80개 영상까지 편집할 수 있습니다.")
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
    if cfg["mode"] != "live" and image_provider not in {"hermes_proxy", "grok_official"}:
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


def upscale_frame_to_2k(frame_path, prompt, image_provider=None):
    dimensions = image_dimensions(frame_path)
    cfg = config()
    image_provider = image_provider or cfg["provider"]
    if cfg["mode"] != "live":
        return frame_path, False, dimensions, "mock 모드에서는 업스케일을 건너뜁니다."
    upscale_prompt = frame_upscale_prompt(prompt)
    upscaled, extra = live_image(
        upscale_prompt,
        media_path("image"),
        edit_source=frame_path,
        aspect_ratio="auto",
        resolution="2k",
        image_provider=image_provider,
    )
    if isinstance(extra, dict):
        extra["upscale_prompt"] = upscale_prompt
    return upscaled, True, dimensions, extra


def upscale_i2v_sources_to_2k(sources, video_prompt=None, image_provider=None):
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
            image_provider=image_provider,
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
    if provider == "grok_official":
        if sources:
            return grok_official_image_edit(prompt, sources[:3], dest_dir, aspect_ratio=aspect_ratio, resolution=resolution)
        return grok_official_image_generate_ws(prompt, dest_dir, aspect_ratio=aspect_ratio, resolution=resolution, model=valid_image_model(image_model, cfg))
    endpoint = "/images/edits" if sources else "/images/generations"
    model = valid_image_model(image_model, cfg)
    body = {"model": model, "prompt": prompt}
    if aspect_ratio != "auto":
        body["aspect_ratio"] = aspect_ratio
    if resolution != "auto":
        body["resolution"] = resolution
    input_remote_urls = []
    if sources:
        if len(sources) == 1:
            body["image"], used_remote = image_input_object(sources[0], include_type=True, allow_remote=False)
            if used_remote:
                input_remote_urls.append(body["image"]["url"])
        else:
            images = []
            for source in sources[:3]:
                image, used_remote = image_input_object(source, include_type=True, allow_remote=False)
                images.append(image)
                if used_remote:
                    input_remote_urls.append(image["url"])
            body["images"] = images
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
    return path, {
        "revised_prompt": revised,
        "remote_url": url,
        "image_model": model,
        "input_remote_urls": input_remote_urls,
        "used_remote_image_inputs": bool(input_remote_urls),
    }


def edit_image_with_config(prompt, source_path, dest_dir, cfg, auth_header, aspect_ratio="auto", filename_prefix="", resolution="auto"):
    body = {
        "model": cfg["image_model"],
        "prompt": prompt,
    }
    body["image"], used_remote = image_input_object(source_path, include_type=True, allow_remote=False)
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
    return path, {
        "revised_prompt": revised,
        "remote_url": url,
        "image_resolution": resolution,
        "input_remote_urls": [body["image"]["url"]] if used_remote else [],
        "used_remote_image_inputs": used_remote,
    }


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
    input_remote_urls = []
    if len(sources) == 1:
        body["image"], used_remote = image_input_object(sources[0], include_type=True, allow_remote=False)
        if used_remote:
            input_remote_urls.append(body["image"]["url"])
    else:
        images = []
        for source in sources[:3]:
            image, used_remote = image_input_object(source, include_type=True, allow_remote=False)
            images.append(image)
            if used_remote:
                input_remote_urls.append(image["url"])
        body["images"] = images
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
        "input_remote_urls": input_remote_urls,
        "used_remote_image_inputs": bool(input_remote_urls),
    }


def live_video(prompt, image_path, duration, aspect_ratio="source", resolution="720p", video_model=None, provider=None):
    cfg = config()
    provider = provider or cfg["provider"]
    model = valid_video_model(video_model, cfg)
    if provider == "grok_official":
        path, extra = grok_official_pipeline_video(
            prompt,
            source_path=image_path,
            duration=duration,
            aspect_ratio=aspect_ratio,
            resolution=resolution,
        )
        extra["video_model"] = model
        extra["input_image_mode"] = "grok_official_upload_blob_ref"
        return path, extra
    image_payload, used_remote = image_input_object(image_path)
    payload = {
        "model": model,
        "prompt": prompt,
        "image": image_payload,
        "duration": duration,
        "resolution": resolution,
    }
    if aspect_ratio not in {"auto", "source"}:
        payload["aspect_ratio"] = aspect_ratio
    start, used_model, model_attempts = post_video_with_model_fallback(
        (cfg["hermes_base_url"] if provider == "hermes_proxy" and cfg.get("hermes_base_url") else cfg["api_base"]) + "/videos/generations",
        xai_headers(provider=provider),
        payload,
        model,
        timeout=120,
    )
    if start.status_code >= 400:
        raise RuntimeError(f"영상 생성 요청 실패: {start.status_code} {response_error_detail(start)}")
    request_id = (start.json() or {}).get("request_id")
    if not request_id:
        raise RuntimeError("영상 생성 요청 ID를 받지 못했습니다.")
    path, extra = poll_video_request(request_id, provider=provider)
    extra["video_model"] = used_model
    if used_model != model:
        extra["requested_video_model"] = model
        extra["video_model_fallback_attempts"] = model_attempts
    extra["input_image_remote_url"] = image_payload["url"] if used_remote else None
    extra["input_image_mode"] = "remote_url" if used_remote else "data_uri"
    return path, extra


def live_video_from_reference_images(prompt, reference_paths, duration, aspect_ratio="source", resolution="720p", video_model=None, provider=None):
    cfg = config()
    provider = provider or cfg["provider"]
    model = valid_video_model(video_model, cfg)
    references = []
    input_reference_remote_urls = []
    seen = set()
    for path in reference_paths:
        if not path:
            continue
        resolved = Path(path).resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        reference, used_remote = image_input_object(resolved)
        references.append(reference)
        if used_remote:
            input_reference_remote_urls.append(reference["url"])
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
    start, used_model, model_attempts = post_video_with_model_fallback(
        (cfg["hermes_base_url"] if provider == "hermes_proxy" and cfg.get("hermes_base_url") else cfg["api_base"]) + "/videos/generations",
        xai_headers(provider=provider),
        payload,
        model,
        timeout=120,
    )
    if start.status_code >= 400:
        raise RuntimeError(f"참조 이미지 기반 영상 생성 요청 실패: {start.status_code} {response_error_detail(start)}")
    request_id = (start.json() or {}).get("request_id")
    if not request_id:
        raise RuntimeError("참조 이미지 기반 영상 생성 요청 ID를 받지 못했습니다.")
    path, extra = poll_video_request(request_id, provider=provider)
    extra["video_model"] = used_model
    if used_model != model:
        extra["requested_video_model"] = model
        extra["video_model_fallback_attempts"] = model_attempts
    extra["reference_image_count"] = len(references[:7])
    extra["input_reference_remote_urls"] = input_reference_remote_urls[:7]
    extra["used_remote_reference_images"] = bool(input_reference_remote_urls[:7])
    if duration > 10:
        extra["requested_duration"] = duration
        extra["duration_clamped_to"] = 10
    return path, extra


def live_video_with_reference_context(prompt, image_path, duration, aspect_ratio="source", resolution="720p", reference_context=None, video_model=None, provider=None):
    if not reference_context:
        return live_video(prompt, image_path, duration, aspect_ratio=aspect_ratio, resolution=resolution, video_model=video_model, provider=provider)
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
        provider=provider,
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


def template_request_metadata(source):
    getter = source.get if isinstance(source, dict) else source.get
    template_result = checked(getter("template_result")) or (getter("generation_origin") or "").strip() == "template"
    template_id = (getter("template_id") or "").strip()
    template_title = (getter("template_title") or "").strip()
    if not template_result and not template_id and not template_title:
        return {}
    return {
        "template_result": True,
        "generation_origin": "template",
        "template_id": template_id[:160],
        "template_title": template_title[:240],
        "template_shot_id": (getter("template_shot_id") or "").strip()[:160],
        "template_shot_title": (getter("template_shot_title") or "").strip()[:240],
        "template_shot_method": (getter("template_shot_method") or "").strip()[:80],
        "template_step_index": (getter("template_step_index") or "").strip()[:40],
        "template_total_steps": (getter("template_total_steps") or "").strip()[:40],
    }


def project_request_metadata(source):
    getter = source.get if isinstance(source, dict) else source.get
    project_id = (getter("project_id") or "").strip()
    project_title = (getter("project_title") or "").strip()
    if not project_id and not project_title:
        return {}
    if project_id:
        project = find_project(project_id)
        if project:
            project_title = project_title or project.get("title") or ""
    return {
        "project_result": True,
        "project_id": project_id[:160],
        "project_title": project_title[:240],
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


def xai_responses_base_headers_provider(provider_override=None):
    cfg = config()
    hermes_base = (cfg.get("hermes_base_url") or "").strip().rstrip("/")
    provider = provider_override or ("hermes_proxy" if hermes_base else cfg["provider"])
    if provider == "grok_official":
        raise RuntimeError("프롬프트 추출은 Hermes xAI OAuth 프록시 또는 direct xAI 경로에서만 사용할 수 있습니다.")
    if provider == "hermes_proxy":
        if not hermes_base:
            raise RuntimeError("프롬프트 추출에 사용할 Hermes xAI OAuth 프록시 연결이 필요합니다.")
        if "127.0.0.1:8645" in hermes_base or "localhost:8645" in hermes_base:
            ensure_hermes_proxy_background()
        return hermes_base, xai_headers(provider="hermes_proxy"), "hermes_proxy"
    if provider == "direct":
        return cfg["api_base"].rstrip("/"), xai_headers(provider="direct"), "direct"
    raise RuntimeError("프롬프트 추출은 Hermes xAI OAuth 프록시 또는 direct xAI 경로에서만 사용할 수 있습니다.")


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


def xai_upload_file(path, provider=None):
    cfg = config()
    provider = provider or cfg["provider"]
    if not path.exists():
        raise RuntimeError("업로드할 파일을 찾을 수 없습니다.")
    if path.stat().st_size > 48 * 1024 * 1024:
        raise RuntimeError("xAI Files API 업로드 한도(48MB)를 초과했습니다. 더 짧거나 작은 mp4를 사용해 주세요.")
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    base_url = cfg["hermes_base_url"] if provider == "hermes_proxy" and cfg.get("hermes_base_url") else cfg["api_base"]
    with path.open("rb") as handle:
        response = requests.post(
            base_url + "/files",
            headers=xai_auth_header(provider=provider),
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


def live_video_extension(prompt, video_path, duration, video_url=None, video_model=None, provider=None):
    cfg = config()
    provider = provider or cfg["provider"]
    model = valid_video_model(video_model, cfg)
    base_url = cfg["hermes_base_url"] if provider == "hermes_proxy" and cfg.get("hermes_base_url") else cfg["api_base"]
    file_id, file_payload = xai_upload_file(video_path, provider=provider)
    payload = {
        "model": model,
        "prompt": prompt,
        "video": {"file_id": file_id},
        "duration": min(10, duration),
    }
    start, used_model, model_attempts = post_video_with_model_fallback(
        base_url + "/videos/extensions",
        xai_headers(provider=provider),
        payload,
        model,
        timeout=120,
    )
    if start.status_code >= 400:
        raise RuntimeError(f"영상 연장 요청 실패: {start.status_code} {response_error_detail(start)}")
    request_id = (start.json() or {}).get("request_id")
    if not request_id:
        raise RuntimeError("영상 연장 요청 ID를 받지 못했습니다.")
    path, extra = poll_video_request(request_id, provider=provider)
    extra["video_model"] = used_model
    if used_model != model:
        extra["requested_video_model"] = model
        extra["video_model_fallback_attempts"] = model_attempts
    extra["extension_api"] = True
    extra["extension_provider"] = provider
    extra["input_video_url"] = video_url
    extra["input_mode"] = "file_id"
    extra["input_file_id"] = file_id
    extra["input_file"] = file_payload
    if duration > 10:
        extra["requested_duration"] = duration
        extra["duration_clamped_to"] = 10
    return path, extra


def poll_video_request(request_id, provider=None):
    cfg = config()
    provider = provider or cfg["provider"]
    base_url = cfg["hermes_base_url"] if provider == "hermes_proxy" and cfg.get("hermes_base_url") else cfg["api_base"]
    headers = xai_auth_header(provider=provider)
    for _ in range(90):
        poll = requests.get(base_url + f"/videos/{request_id}", headers=headers, timeout=60)
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
    grok_official = grok_official_status_payload(check_cookie=cfg["provider"] == "grok_official")
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
        "grok_official": grok_official,
        "hermes_logged_in": hermes_logged_in,
        "hermes_proxy_running": hermes_proxy_running,
        "api_key_configured": bool(cfg["api_key"]),
        "oauth_configured": bool(oauth_token and oauth_token.get("access_token")),
        "oauth_expires_at": oauth_token.get("expires_at") if oauth_token else None,
        "authenticated": bool(
            (cfg["provider"] == "hermes_proxy" and hermes_logged_in and hermes_proxy_running)
            or (cfg["provider"] == "grok_official" and grok_official.get("chrome_running") and grok_official.get("session_cookie"))
            or (cfg["provider"] == "openai_api" and cfg["openai_api_key"])
            or (cfg["provider"] == "codex_proxy" and codex_running)
            or session.get("xai_api_key")
        ),
        "management_configured": bool(cfg["management_key"] and cfg["team_id"]),
        "media_root": str(media_root()),
        "usage": usage,
        "models": hermes_model_candidates_payload(cfg),
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
    grok_official = grok_official_status_payload(check_cookie=cfg["provider"] == "grok_official")
    grok_official_ready = bool(
        cfg["provider"] == "grok_official"
        and grok_official.get("chrome_running")
        and grok_official.get("session_cookie")
    )
    payload = {
        "authenticated": bool(
            cfg["provider"] == "hermes_proxy" and cfg["hermes_base_url"]
            or grok_official_ready
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
        "grok_official": grok_official,
        "oauth_configured": bool(read_oauth_token()),
        "management_configured": bool(cfg["management_key"] and cfg["team_id"]),
        "mode": cfg["mode"],
        "media_root": str(media_root()),
        "models": hermes_model_candidates_payload(cfg),
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
    if provider not in {"direct", "hermes_proxy", "grok_official", "openai_api", "codex_proxy"}:
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


@app.post("/api/settings/provider-mode")
def set_provider_mode():
    data = request.get_json(silent=True) or {}
    provider = (data.get("provider") or "").strip().lower()
    if provider not in {"direct", "hermes_proxy", "grok_official", "openai_api", "codex_proxy"}:
        return safe_error("지원하지 않는 provider입니다.")
    settings = read_settings()
    settings["provider"] = provider
    write_settings(settings)
    return jsonify({"ok": True, "provider": provider, "settings": settings})


@app.get("/api/grok-official/status")
def grok_official_status():
    return jsonify({"ok": True, **grok_official_status_payload(check_cookie=True)})


@app.get("/api/grok-official/progress")
def grok_official_progress():
    return jsonify({"ok": True, "progress": grok_official_progress_payload()})


@app.post("/api/grok-official/chrome/start")
def grok_official_chrome_start():
    try:
        result = ensure_grok_chrome()
        return jsonify({"ok": True, **result, "status": grok_official_status_payload(check_cookie=False)})
    except Exception as exc:
        return safe_error("Grok 공식홈 Chrome을 시작하지 못했습니다.", exc, 502)


@app.post("/api/grok-official/chrome/start-default")
def grok_official_chrome_start_default():
    if port_open("127.0.0.1", grok_official_port()):
        return safe_error(
            "Grok 공식홈 Chrome 디버그 포트가 이미 사용 중입니다.",
            detail="전용 Grok Chrome 창을 모두 닫은 뒤 다시 눌러 주세요. 기본 Chrome 프로필은 이미 실행 중인 일반 Chrome에 뒤늦게 붙을 수 없습니다.",
            status=409,
        )
    try:
        result = ensure_grok_chrome(use_default_profile=True)
        return jsonify({"ok": True, **result, "status": grok_official_status_payload(check_cookie=False)})
    except Exception as exc:
        return safe_error("기본 Chrome 프로필로 Grok 공식홈을 시작하지 못했습니다.", exc, 502)


@app.post("/api/grok-official/chrome/restart-default")
def grok_official_chrome_restart_default():
    try:
        stopped = stop_chrome_processes()
        result = ensure_grok_chrome(use_default_profile=True)
        return jsonify({
            "ok": True,
            **result,
            "stopped_chrome": stopped,
            "status": grok_official_status_payload(check_cookie=False),
            "message": "Chrome을 종료하고 기본 프로필로 Grok 공식홈을 열었습니다.",
        })
    except Exception as exc:
        return safe_error("Chrome 종료 후 기본 프로필 실행에 실패했습니다.", exc, 502)


@app.post("/api/codex-proxy/start")
def codex_proxy_start():
    result = start_codex_proxy_background()
    if not result.get("ok"):
        return safe_error(result.get("error") or "Codex OAuth 프록시를 시작하지 못했습니다.", result.get("detail"), result.get("status", 500))
    return jsonify(result)


def start_codex_proxy_background():
    global CODEX_PROXY_PROCESS
    cfg = config()
    if codex_proxy_running(cfg, timeout=1):
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
        log_path = codex_proxy_log_path()
        log_file = open(log_path, "a", encoding="utf-8", buffering=1)
        print(f"\n[{datetime.now(timezone.utc).isoformat()}] starting codex proxy: {json.dumps(command, ensure_ascii=False)}", file=log_file, flush=True)
        CODEX_PROXY_PROCESS = subprocess.Popen(
            command,
            cwd=str(ROOT),
            env=env,
            stdout=log_file,
            stderr=log_file,
            stdin=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
    except Exception as exc:
        return {"ok": False, "error": "Codex OAuth 프록시를 시작하지 못했습니다.", "detail": error_detail_text(exc), "status": 500}
    for _ in range(12):
        time.sleep(0.5)
        if CODEX_PROXY_PROCESS.poll() is not None:
            detail = ""
            try:
                detail = codex_proxy_log_path().read_text(encoding="utf-8", errors="replace")[-2000:]
            except OSError:
                pass
            return {
                "ok": False,
                "error": "Codex OAuth 프록시 프로세스가 바로 종료되었습니다.",
                "detail": detail or f"exit_code={CODEX_PROXY_PROCESS.returncode}",
                "status": 502,
                "log_path": str(codex_proxy_log_path()),
            }
        refreshed = {**cfg, "codex_proxy_base_url": discover_codex_proxy_url() or cfg["codex_proxy_base_url"]}
        if codex_proxy_running(refreshed, timeout=1):
            settings = read_settings()
            if refreshed["codex_proxy_base_url"]:
                settings["codex_proxy_base_url"] = refreshed["codex_proxy_base_url"]
                write_settings(settings)
            return {"ok": True, "message": "Codex OAuth 프록시가 실행되었습니다.", "proxy_running": True, "url": refreshed["codex_proxy_base_url"]}
    return {
        "ok": True,
        "message": "Codex OAuth 프록시를 백그라운드에서 시작했습니다. 설치/로그인이 진행 중이면 잠시 뒤 다시 확인해 주세요.",
        "proxy_running": False,
        "url": cfg["codex_proxy_base_url"],
        "log_path": str(codex_proxy_log_path()),
    }


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


def hermes_listed_models(cfg, headers):
    models = []
    errors = []
    for path in ("/v1/models", "/models"):
        try:
            response = requests.get(cfg["hermes_base_url"].rstrip("/") + path, headers=headers, timeout=20)
            if response.status_code >= 400:
                errors.append(f"{path}: {response.status_code}")
                continue
            payload = response.json()
            rows = payload.get("data") if isinstance(payload, dict) else payload
            if isinstance(rows, list):
                for row in rows:
                    if isinstance(row, dict):
                        models.append(row.get("id") or row.get("name") or row.get("model"))
                    else:
                        models.append(row)
        except Exception as exc:
            errors.append(f"{path}: {str(exc)[:120]}")
    return unique_model_ids(models), errors


def hermes_model_kind_hint(model, kind):
    value = str(model or "").strip().lower()
    if not value:
        return False
    if kind in {"image", "edit"}:
        return (
            "video" not in value
            and ("image" in value or "imagine" in value)
            or value in {item.lower() for item in HERMES_IMAGE_MODEL_CANDIDATES}
        )
    if kind == "video":
        return (
            "video" in value
            or "i2v" in value
            or value in {item.lower() for item in HERMES_VIDEO_MODEL_CANDIDATES}
        )
    return False


def hermes_probe_candidates(user_candidates, listed, cfg, kind, limit):
    user_models = unique_model_ids(user_candidates)
    listed_models = [model for model in listed if hermes_model_kind_hint(model, kind)]
    if kind == "video":
        defaults = HERMES_VIDEO_MODEL_CANDIDATES + cfg.get("hermes_discovered_video_models", [])
    else:
        defaults = HERMES_IMAGE_MODEL_CANDIDATES + cfg.get("hermes_discovered_image_models", [])
    return unique_model_ids(user_models + defaults + listed_models)[:limit]


def hermes_probe_image_model(cfg, headers, model):
    payload = {
        "model": model,
        "prompt": "model capability probe: a plain gray square on white background",
        "aspect_ratio": "1:1",
    }
    response = requests.post(
        cfg["hermes_base_url"].rstrip("/") + "/images/generations",
        headers=headers,
        json=payload,
        timeout=180,
    )
    detail = response_error_detail(response) if response.status_code >= 400 else response.text[:500]
    missing = response.status_code in {400, 404} and any(token in detail.lower() for token in ("does not exist", "does not have access", "model_not_found", "not found"))
    return {
        "model": model,
        "ok": response.status_code < 400,
        "accepted": response.status_code < 400 or not missing,
        "status_code": response.status_code,
        "detail": detail[:900],
    }


def hermes_probe_edit_model(cfg, headers, model):
    payload = {
        "model": model,
        "prompt": "model capability probe: make the square blue",
        "image": {"type": "image_url", "url": HERMES_PROBE_IMAGE_DATA_URI},
    }
    response = requests.post(
        cfg["hermes_base_url"].rstrip("/") + "/images/edits",
        headers=headers,
        json=payload,
        timeout=180,
    )
    detail = response_error_detail(response) if response.status_code >= 400 else response.text[:500]
    missing = response.status_code in {400, 404} and any(token in detail.lower() for token in ("does not exist", "does not have access", "model_not_found", "not found"))
    return {
        "model": model,
        "ok": response.status_code < 400,
        "accepted": response.status_code < 400 or not missing,
        "status_code": response.status_code,
        "detail": detail[:900],
    }


def hermes_probe_video_model(cfg, headers, model):
    payload = {
        "model": model,
        "prompt": "model capability probe: slow camera drift over a plain gray square",
        "reference_images": [{"url": HERMES_PROBE_IMAGE_DATA_URI}],
        "duration": 2,
        "resolution": "480p",
    }
    response = requests.post(
        cfg["hermes_base_url"].rstrip("/") + "/videos/generations",
        headers=headers,
        json=payload,
        timeout=180,
    )
    detail = response_error_detail(response) if response.status_code >= 400 else response.text[:500]
    missing = response.status_code in {400, 404} and any(token in detail.lower() for token in ("does not exist", "does not have access", "model_not_found", "not found"))
    return {
        "model": model,
        "ok": response.status_code < 400,
        "accepted": response.status_code < 400 or not missing,
        "status_code": response.status_code,
        "detail": detail[:900],
    }


@app.post("/api/hermes/model-probe")
def hermes_model_probe():
    cfg = config()
    if not cfg["hermes_base_url"]:
        return safe_error("Hermes Proxy Base URL을 먼저 설정해 주세요.")
    data = request.get_json(silent=True) or {}
    kind = (data.get("kind") or "image").strip().lower()
    if kind not in {"image", "edit", "video", "both", "all"}:
        return safe_error("kind는 image, edit, video, both, all 중 하나여야 합니다.")
    try:
        limit = max(1, min(80, int(data.get("limit") or 30)))
    except (TypeError, ValueError):
        limit = 30
    headers = xai_headers(provider="hermes_proxy")
    listed, listed_errors = hermes_listed_models(cfg, headers)
    user_candidates = data.get("candidates") or []
    if isinstance(user_candidates, str):
        user_candidates = re.split(r"[\s,]+", user_candidates)
    save_results = str(data.get("save") or "").strip().lower() in {"1", "true", "yes", "on"}
    image_candidates = hermes_probe_candidates(user_candidates, listed, cfg, "image", limit)
    edit_candidates = hermes_probe_candidates(user_candidates, listed, cfg, "edit", limit)
    video_candidates = hermes_probe_candidates(user_candidates, listed, cfg, "video", limit)
    image_results = []
    edit_results = []
    video_results = []
    if kind in {"image", "both", "all"}:
        for model in image_candidates:
            image_results.append(hermes_probe_image_model(cfg, headers, model))
    if kind in {"edit", "all"}:
        for model in edit_candidates:
            edit_results.append(hermes_probe_edit_model(cfg, headers, model))
    if kind in {"video", "both", "all"}:
        for model in video_candidates:
            video_results.append(hermes_probe_video_model(cfg, headers, model))
    found_images = [item["model"] for item in image_results if item.get("ok")]
    found_edits = [item["model"] for item in edit_results if item.get("ok")]
    found_videos = [item["model"] for item in video_results if item.get("ok")]
    settings = read_settings()
    if save_results and (found_images or found_edits):
        settings["hermes_discovered_image_models"] = unique_model_ids(
            settings.get("hermes_discovered_image_models", []) + found_images + found_edits
        )
    if save_results and found_videos:
        settings["hermes_discovered_video_models"] = unique_model_ids(
            settings.get("hermes_discovered_video_models", []) + found_videos
        )
    if save_results and (found_images or found_edits or found_videos):
        write_settings(settings)
    saved_models = hermes_model_candidates_payload(config()) if save_results else None
    return jsonify({
        "ok": True,
        "kind": kind,
        "saved": save_results,
        "listed_models": listed,
        "listed_errors": listed_errors,
        "image_candidates": image_candidates,
        "edit_candidates": edit_candidates,
        "video_candidates": video_candidates if kind in {"video", "both", "all"} else [],
        "image_results": image_results,
        "edit_results": edit_results,
        "video_results": video_results,
        "found_image_models": found_images,
        "found_edit_models": found_edits,
        "found_video_models": found_videos,
        "models": saved_models,
    })


@app.post("/api/hermes/models/add")
def hermes_models_add():
    data = request.get_json(silent=True) or {}
    image_models = unique_model_ids(
        request_model_id_list(data.get("image_models")) + request_model_id_list(data.get("edit_models"))
    )
    video_models = unique_model_ids(request_model_id_list(data.get("video_models")))
    if not image_models and not video_models:
        return safe_error("추가할 모델을 선택해 주세요.", status=400)
    settings = read_settings()
    if image_models:
        settings["hermes_discovered_image_models"] = unique_model_ids(
            settings.get("hermes_discovered_image_models", []) + image_models
        )
    if video_models:
        settings["hermes_discovered_video_models"] = unique_model_ids(
            settings.get("hermes_discovered_video_models", []) + video_models
        )
    write_settings(settings)
    cfg = config()
    return jsonify({
        "ok": True,
        "added_image_models": image_models,
        "added_video_models": video_models,
        "models": hermes_model_candidates_payload(cfg),
    })


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


@app.get("/api/projects")
def project_library():
    items = read_projects()
    items.sort(key=lambda item: (bool(item.get("favorite")), item.get("updated_at") or ""), reverse=True)
    return jsonify({"ok": True, "items": items})


@app.post("/api/projects")
def save_project_item():
    payload = request.get_json(silent=True) or {}
    project_id = str(payload.get("id") or "").strip()
    now = datetime.now(timezone.utc).isoformat()
    incoming = normalize_project({
        "id": project_id or uuid.uuid4().hex,
        "title": payload.get("title"),
        "description": payload.get("description"),
        "tags": payload.get("tags"),
        "favorite": parse_request_bool(payload.get("favorite")),
        "created_at": now,
        "updated_at": now,
    })
    items = read_projects()
    for index, item in enumerate(items):
        if item.get("id") != project_id:
            continue
        previous = normalize_project(item)
        incoming["created_at"] = previous.get("created_at") or now
        incoming["updated_at"] = now
        items[index] = incoming
        write_projects(items)
        return jsonify({"ok": True, "item": incoming, "created": False})
    items.insert(0, incoming)
    write_projects(items)
    return jsonify({"ok": True, "item": incoming, "created": True})


@app.post("/api/projects/favorite")
def favorite_project_item():
    payload = request.get_json(silent=True) or {}
    project_id = str(payload.get("id") or "").strip()
    favorite = parse_request_bool(payload.get("favorite"))
    items = read_projects()
    for item in items:
        if item.get("id") == project_id:
            item["favorite"] = favorite
            item["updated_at"] = datetime.now(timezone.utc).isoformat()
            write_projects(items)
            return jsonify({"ok": True, "id": project_id, "favorite": favorite})
    return safe_error("프로젝트를 찾을 수 없습니다.", status=404)


@app.post("/api/projects/delete")
def delete_project_items():
    payload = request.get_json(silent=True) or {}
    ids = set(str(item) for item in (payload.get("ids") or []) if item)
    if not ids:
        return safe_error("삭제할 프로젝트를 선택해 주세요.")
    items = read_projects()
    keep = [item for item in items if item.get("id") not in ids]
    write_projects(keep)
    return jsonify({"ok": True, "deleted": len(items) - len(keep)})


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


@app.post("/api/template-slot-upload")
def template_slot_upload():
    uploaded = request.files.get("file")
    if not uploaded or not uploaded.filename:
        return safe_error("슬롯에 넣을 파일을 선택해 주세요.")
    slot_key = (request.form.get("slot_key") or "").strip()
    kind = (request.form.get("kind") or "image").strip().lower()
    filename = secure_filename(uploaded.filename) or "upload"
    suffix = Path(filename).suffix.lower()
    try:
        if kind == "video":
            if suffix not in {".mp4", ".webm", ".mov"}:
                return safe_error("영상 슬롯에는 mp4, webm, mov 파일만 넣을 수 있습니다.", status=400)
            ensure_media_dirs()
            dest = media_path("uploads", f"{now_stamp()}-{uuid.uuid4().hex}-template-slot{suffix}")
            uploaded.save(dest)
            item = add_metadata(
                "video",
                f"Template slot video: {uploaded.filename}",
                "upload",
                dest,
                extra={
                    "origin": "upload",
                    "used_for": "template-slot",
                    "slot_key": slot_key,
                    "original_name": uploaded.filename,
                },
            )
        else:
            if suffix not in {".jpg", ".jpeg", ".png", ".webp"}:
                return safe_error("이미지 슬롯에는 jpg, png, webp 파일만 넣을 수 있습니다.", status=400)
            ensure_media_dirs()
            blob = read_uploaded_bytes(uploaded)
            existing, existing_item = find_existing_image_by_bytes(blob)
            if existing:
                item = existing_item or register_uploaded_image_source(existing, "template-slot", original_name=uploaded.filename)
            else:
                dest = media_path("image", f"{now_stamp()}-{uuid.uuid4().hex}-template-slot{suffix}")
                dest.write_bytes(blob)
                item = add_metadata(
                    "image",
                    f"Template slot image: {uploaded.filename}",
                    "upload",
                    dest,
                    extra={
                        "origin": "upload",
                        "used_for": "template-slot",
                        "slot_key": slot_key,
                        "original_name": uploaded.filename,
                    },
                )
        return jsonify({"ok": True, "item": item})
    except Exception as exc:
        return safe_error("템플릿 슬롯 파일 업로드에 실패했습니다.", exc, 502)


@app.post("/api/grok-official-t2i")
def grok_official_t2i():
    payload = request.get_json(silent=True) or {}
    prompt = (payload.get("prompt") or request.form.get("prompt") or "").strip()
    aspect_ratio = valid_aspect_ratio(payload.get("aspect_ratio") or request.form.get("aspect_ratio"))
    image_resolution = valid_image_resolution(payload.get("image_resolution") or request.form.get("image_resolution"))
    image_model = valid_image_model(payload.get("image_model") or request.form.get("image_model"))
    if not prompt:
        return safe_error("프롬프트를 입력해 주세요.")
    try:
        path, extra = grok_official_image_generate_ws(
            prompt,
            media_path("image"),
            aspect_ratio=aspect_ratio,
            resolution=image_resolution,
            model=image_model,
        )
        extra.update(prompt_planner_request_metadata(payload, prompt))
        extra.update(template_request_metadata(payload))
        extra.update(project_request_metadata(payload))
        output_file_paths = [Path(item) for item in (extra.get("official_output_file_paths") or []) if item]
        output_file_paths = [item for item in output_file_paths if item.exists()]
        if not output_file_paths:
            output_file_paths = [Path(path)]
        original_output_total = len(output_file_paths)
        common_extra = dict(extra)
        common_extra.pop("official_output_file_paths", None)
        skipped_placeholders = []
        filtered_output_paths = []
        for output_path in output_file_paths:
            placeholder_check = likely_grok_official_censor_placeholder(output_path)
            if placeholder_check.get("is_placeholder"):
                skipped_placeholders.append({
                    "path": public_path(output_path),
                    "check": placeholder_check,
                })
                continue
            filtered_output_paths.append(output_path)
        output_file_paths = filtered_output_paths
        if skipped_placeholders:
            common_extra["official_skipped_censor_placeholders"] = skipped_placeholders
            common_extra["official_skipped_censor_placeholder_count"] = len(skipped_placeholders)
            common_extra["official_original_output_total"] = original_output_total
        if not output_file_paths:
            raise RuntimeError("Grok 공식홈 이미지 생성 결과가 검열 placeholder로 감지되어 라이브러리에 등록하지 않았습니다.")
        output_total = len(output_file_paths)
        created = []
        for index, output_path in reversed(list(enumerate(output_file_paths, start=1))):
            item_extra = dict(common_extra)
            width, height = image_dimensions(output_path) or (None, None)
            item_extra.update({
                "official_output_index": index,
                "official_output_total": output_total,
                "official_output_path": public_path(output_path),
                "official_width": width,
                "official_height": height,
            })
            created.append((index, add_metadata("image", prompt, image_model, output_path, extra=item_extra)))
        items = [item for _, item in sorted(created, key=lambda pair: pair[0])]
        item = items[0]
        return jsonify({"ok": True, "item": item, "items": items, "official": json_safe(extra)})
    except Exception as exc:
        return safe_error("Grok 공식홈 이미지 생성에 실패했습니다.", exc, 502)


@app.post("/api/grok-official-i2i")
def grok_official_i2i():
    prompt = (request.form.get("prompt") or "").strip()
    aspect_ratio = valid_aspect_ratio(request.form.get("aspect_ratio"))
    image_resolution = valid_image_resolution(request.form.get("image_resolution"))
    image_model = valid_image_model(request.form.get("image_model"))
    if not prompt:
        return safe_error("편집 프롬프트를 입력해 주세요.")
    try:
        sources, source_items = save_reference_images_or_library("image", "grok-official-i2i", limit=3)
        path, extra = grok_official_image_edit(
            prompt,
            sources,
            media_path("image"),
            aspect_ratio=aspect_ratio,
            resolution=image_resolution,
        )
        extra.update({
            "source_image_path": public_path(sources[0]),
            "source_image_paths": [public_path(source) for source in sources],
            "source_image_ids": [item.get("id") if item else None for item in source_items],
            "image_model": image_model,
        })
        extra.update(prompt_planner_request_metadata(request.form, prompt))
        extra.update(template_request_metadata(request.form))
        extra.update(project_request_metadata(request.form))
        item = add_metadata("edit", prompt, image_model, path, source_path=sources[0], extra=extra)
        return jsonify({"ok": True, "item": item, "official": json_safe(extra)})
    except ValueError as exc:
        return safe_error(str(exc))
    except Exception as exc:
        return safe_error("Grok 공식홈 이미지 편집에 실패했습니다.", exc, 502)


@app.post("/api/grok-official-t2v")
def grok_official_t2v():
    payload = request.get_json(silent=True) or {}
    prompt = (payload.get("prompt") or request.form.get("prompt") or "").strip()
    duration = valid_duration(payload.get("duration") or request.form.get("duration"))
    aspect_ratio = valid_aspect_ratio(payload.get("aspect_ratio") or request.form.get("aspect_ratio"))
    resolution = valid_video_resolution(payload.get("resolution") or request.form.get("resolution"))
    video_model = valid_video_model(payload.get("video_model") or request.form.get("video_model"))
    if not prompt:
        return safe_error("영상 프롬프트를 입력해 주세요.")
    try:
        path, extra = grok_official_pipeline_video(prompt, duration=duration, aspect_ratio=aspect_ratio, resolution=resolution)
        extra.update({
            "generation_type": "t2v",
            "video_model": video_model,
            "requested_resolution": resolution,
        })
        extra.update(prompt_planner_request_metadata(payload, prompt))
        extra.update(template_request_metadata(payload))
        extra.update(project_request_metadata(payload))
        item = add_metadata("video", prompt, video_model, path, extra=extra)
        return jsonify({"ok": True, "item": item, "official": json_safe(extra)})
    except Exception as exc:
        return safe_error("Grok 공식홈 텍스트→영상 생성에 실패했습니다.", exc, 502)


@app.post("/api/grok-official-i2v")
def grok_official_i2v():
    prompt = (request.form.get("prompt") or "").strip()
    duration = valid_duration(request.form.get("duration"))
    aspect_ratio = valid_aspect_ratio(request.form.get("aspect_ratio"), allow_source=True)
    resolution = valid_video_resolution(request.form.get("resolution"))
    video_model = valid_video_model(request.form.get("video_model"))
    if not prompt:
        return safe_error("영상 프롬프트를 입력해 주세요.")
    try:
        sources, source_items = save_reference_images_or_library("image", "grok-official-i2v", limit=1)
        source = sources[0]
        source_item = source_items[0] if source_items else None
        path, extra = grok_official_pipeline_video(prompt, source_path=source, duration=duration, aspect_ratio=aspect_ratio, resolution=resolution)
        extra.update({
            "generation_type": "i2v",
            "i2v_prompt": prompt,
            "video_model": video_model,
            "requested_resolution": resolution,
            "start_image_path": public_path(source),
            "start_image_id": source_item.get("id") if source_item else None,
        })
        extra.update(prompt_planner_request_metadata(request.form, prompt))
        extra.update(template_request_metadata(request.form))
        extra.update(project_request_metadata(request.form))
        item = add_metadata("video", prompt, video_model, path, source_path=source, extra=extra)
        return jsonify({"ok": True, "item": item, "official": json_safe(extra)})
    except ValueError as exc:
        return safe_error(str(exc))
    except Exception as exc:
        return safe_error("Grok 공식홈 이미지→영상 생성에 실패했습니다.", exc, 502)


@app.post("/api/grok-agent")
def grok_agent():
    prompt = (request.form.get("prompt") or "").strip()
    agent_task = (request.form.get("agent_task") or "auto").strip().lower()
    conversation_id = (request.form.get("conversation_id") or "").strip()
    parent_response_id = (request.form.get("parent_response_id") or "").strip()
    if not prompt:
        return safe_error("Grok Agent 명령을 입력해 주세요.")
    task_prefix = {
        "auto": "",
        "image": "이미지를 생성해줘. ",
        "image_edit": "이미지를 편집해줘. ",
        "i2v": "이미지 또는 참조 asset을 영상으로 만들어줘. ",
        "video": "영상을 생성해줘. ",
    }.get(agent_task, "")
    message = (task_prefix + prompt).strip()
    try:
        parsed = grok_agent_run(
            message,
            conversation_id=conversation_id,
            parent_response_id=parent_response_id,
        )
        path, used_url, result_kind, candidate = grok_agent_download_result(parsed)
        model = "grok-agent-imagine"
        extra = {
            "source": "grok_official_web",
            "request_provider": "grok_agent",
            "official_transport": "app_chat_agent",
            "agent_task": agent_task,
            "agent_message": message,
            "agent_conversation_id": parsed.get("conversation_id") or conversation_id,
            "agent_response_ids": parsed.get("response_ids"),
            "agent_progress": parsed.get("progress"),
            "agent_media_url": used_url,
            "agent_media_candidate": candidate,
            "agent_media_candidates": parsed.get("media_candidates"),
            "agent_tool_calls": parsed.get("tool_calls"),
            "agent_messages": parsed.get("messages"),
            "agent_event_count": parsed.get("event_count"),
            "agent_request_url": parsed.get("request_url"),
            "agent_request_body": parsed.get("request_body"),
            "agent_moderated_flags": parsed.get("moderated"),
            "grok_account_id": active_grok_account_id(),
        }
        extra.update(prompt_planner_request_metadata(request.form, prompt))
        extra.update(template_request_metadata(request.form))
        extra.update(project_request_metadata(request.form))
        item_kind = "video" if result_kind == "video" else ("edit" if agent_task == "image_edit" else "image")
        item = add_metadata(item_kind, prompt, model, path, extra=extra)
        return jsonify({"ok": True, "item": item, "agent": json_safe(extra)})
    except Exception as exc:
        return safe_error("Grok Agent 요청에 실패했습니다.", exc, 502)


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
        provider_override = request_provider_override(payload) or request_provider_override(request.form)
        image_provider, image_model = selected_image_backend(payload.get("image_model") or request.form.get("image_model"), cfg, provider_override=provider_override)
        if cfg["mode"] == "live" or image_provider in {"hermes_proxy", "grok_official"}:
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
        extra["request_provider"] = image_provider
        extra.update(prompt_planner_request_metadata(payload, prompt))
        extra.update(template_request_metadata(payload))
        extra.update(project_request_metadata(payload))
        raise_if_grok_official_placeholder(path, extra)
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
        provider_override = request_provider_override(request.form)
        image_provider, image_model = selected_image_backend(request.form.get("image_model"), cfg, provider_override=provider_override)
        sources, source_items = save_reference_images_or_library("image", "i2i", limit=3)
        edit_source = stitched_reference_image(sources) if edit_input_mode == "stitch" else sources[0]
        edit_sources = sources if edit_input_mode == "multi" and len(sources) > 1 else None
        output_dir = media_path("manga_trans") if manga_edit else media_path("image")
        source_name = Path(sources[0]).name
        if source_items and source_items[0]:
            source_name = (source_items[0].get("extra") or {}).get("original_name") or source_items[0].get("file_path") or source_name
        source_name = re.split(r"[\\/]", str(source_name))[-1]
        manga_prefix = f"grok_trans_{safe_output_stem(source_name, 1)}_" if manga_edit else ""
        if cfg["mode"] == "live" or image_provider in {"hermes_proxy", "grok_official"}:
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
            "request_provider": image_provider,
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
        extra.update(template_request_metadata(request.form))
        extra.update(project_request_metadata(request.form))
        raise_if_grok_official_placeholder(path, extra)
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
        project_metadata = dict(job.get("project_metadata") or {})
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
                        extra.update(project_metadata)
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
                        extra.update(project_metadata)
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
                extra.update(project_metadata)
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
                "project_metadata": project_request_metadata(request.form),
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
    provider_override = request_provider_override(request.form)
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
        live_requested = cfg["mode"] == "live" or provider_override in {"hermes_proxy", "grok_official"}
        effective_video_provider = provider_override or cfg["provider"]
        if live_requested and upscale_source:
            video_sources, upscale_details = upscale_i2v_sources_to_2k(sources, prompt, image_provider=effective_video_provider)
        source = video_sources[0]
        if live_requested:
            if effective_video_provider == "grok_official":
                path, extra = grok_official_pipeline_video(prompt, source_path=source, duration=duration, aspect_ratio=aspect_ratio, resolution=resolution)
            elif len(video_sources) > 1:
                reference_prompt = (
                    f"{prompt}\n\n"
                    f"Use IMAGE_1 as the primary starting image. "
                    f"Use the additional reference images to preserve identity, outfit, environment, palette, style, and target visual details."
                ).strip()
                path, extra = live_video_from_reference_images(reference_prompt, video_sources, duration, aspect_ratio=aspect_ratio, resolution=resolution, video_model=video_model, provider=effective_video_provider)
            else:
                path, extra = live_video(prompt, source, duration, aspect_ratio=aspect_ratio, resolution=resolution, video_model=video_model, provider=effective_video_provider)
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
            "request_provider": effective_video_provider,
        })
        extra.update(prompt_planner_request_metadata(request.form, prompt))
        extra.update(template_request_metadata(request.form))
        extra.update(project_request_metadata(request.form))
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
        sources, source_items = save_video_uploads_or_library_paths("videos", limit=80)
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
        extra.update(template_request_metadata(request.form))
        extra.update(project_request_metadata(request.form))
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
    provider_override = request_provider_override(request.form)
    effective_video_provider = provider_override or cfg["provider"]
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
            official_path, extra = live_video_extension(
                extension_prompt,
                extension_source,
                duration,
                video_url=remote_url if not trim_extra.get("trimmed_for_connect_time") else None,
                video_model=video_model,
                provider=effective_video_provider,
            )
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
        elif cfg["mode"] == "live" or effective_video_provider in {"hermes_proxy", "grok_official"}:
            frame = extract_last_frame(source_video)
            if upscale_frame:
                prepared_frame, upscaled, frame_dimensions, upscale_extra = upscale_frame_to_2k(
                    frame,
                    extension_prompt,
                    image_provider=effective_video_provider,
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
                provider=effective_video_provider,
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
            "request_provider": effective_video_provider,
        })
        extra.update(prompt_planner_request_metadata(request.form, prompt))
        extra.update(template_request_metadata(request.form))
        extra.update(project_request_metadata(request.form))
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
        request_provider = None
        if cfg["mode"] == "live":
            provider_override = request_provider_override(request.form)
            base_url, headers, request_provider = xai_responses_base_headers_provider(provider_override)
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
            response = requests.post(base_url.rstrip("/") + "/responses", headers=headers, json=body, timeout=240)
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
            "request_provider": request_provider,
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
