import os
import json
import mimetypes
import secrets
import shutil
import time
import urllib.parse
import logging
import threading
import hmac
import hashlib
import errno
from pathlib import Path

from flask import Flask, Response, make_response, request, g


ROOT_DIR = Path(__file__).resolve().parent
DATA_DIR = ROOT_DIR / "data"
GALLERY_DIR = ROOT_DIR / "assets" / "gallery"
COUPON_DIR = ROOT_DIR / "assets" / "coupon"
CALENDAR_DIR = ROOT_DIR / "assets" / "calendar"

OFFERINGS_PATH = DATA_DIR / "nerchas.json"
PURCHASES_PATH = DATA_DIR / "purchases.json"
GALLERY_META_PATH = DATA_DIR / "gallery.json"
LIVE_LINK_PATH = DATA_DIR / "live_link.json"
CALENDAR_FS_LOCK_PATH = DATA_DIR / "_calendar_fs_lock"
COUPON_FS_LOCK_PATH = DATA_DIR / "_coupon_fs_lock"

SESSION_COOKIE = "admin_session"
SESSION_TTL_SECONDS = 60 * 60 * 6  # 6 hours


# Defaults tuned for large media uploads (override via env on hosting).
_DEFAULT_MAX_UPLOAD = 500 * 1024 * 1024
_DEFAULT_MAX_FILE = 450 * 1024 * 1024

# Site images that belong in the public gallery (moved from assets/ root into assets/gallery/).
_GALLERY_RELOCATE_FROM_ASSETS_ROOT = [
    "church_exterior.jpg.jpg",
    "church_night.jpg.jpg",
    "649334100_1337804095050528_5143294464664934259_n.jpg",
    "priest_sermon.jpg.jpg",
    "palm_sunday.jpg.jpg",
    "virgin_mary_icon.jpg.jpg",
]


DEFAULT_OFFERINGS = [
    {"english": "anitha", "malayalam": "അനിത", "price": 10, "image": ""},
    {"english": "v. kurbana", "malayalam": "വി. കുർബാന", "price": 10, "image": ""},
    {"english": "prarthana", "malayalam": "പ്രാർത്ഥന", "price": 10, "image": ""},
    {"english": "panthrandu paithangulude nercha", "malayalam": "പന്ത്രണ്ടു പൈതങ്ങളുടെ നേർച്ച", "price": 500, "image": ""},
]


SESSIONS = {}  # token -> {created_at: float}


def ensure_data_files():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    GALLERY_DIR.mkdir(parents=True, exist_ok=True)
    COUPON_DIR.mkdir(parents=True, exist_ok=True)
    CALENDAR_DIR.mkdir(parents=True, exist_ok=True)

    if not OFFERINGS_PATH.exists():
        OFFERINGS_PATH.write_text(json.dumps({"offerings": DEFAULT_OFFERINGS}, ensure_ascii=False, indent=2), encoding="utf-8")

    if not PURCHASES_PATH.exists():
        PURCHASES_PATH.write_text(json.dumps({"purchases": []}, ensure_ascii=False, indent=2), encoding="utf-8")

    if not GALLERY_META_PATH.exists():
        default_gallery = {
            "items": [
                {"filename": "church_exterior.jpg.jpg", "type": "image", "date": "March 19, 2026"},
                {"filename": "649334100_1337804095050528_5143294464664934259_n.jpg", "type": "image", "date": "March 19, 2026"},
                {"filename": "church_night.jpg.jpg", "type": "image", "date": "March 19, 2026"},
                {"filename": "priest_sermon.jpg.jpg", "type": "image", "date": "March 19, 2026"},
                {"filename": "palm_sunday.jpg.jpg", "type": "image", "date": "March 19, 2026"},
                {"filename": "virgin_mary_icon.jpg.jpg", "type": "image", "date": "March 19, 2026"}
            ]
        }
        GALLERY_META_PATH.write_text(json.dumps(default_gallery, ensure_ascii=False, indent=2), encoding="utf-8")

    if not LIVE_LINK_PATH.exists():
        LIVE_LINK_PATH.write_text(json.dumps({"url": "", "kind": ""}, ensure_ascii=False, indent=2), encoding="utf-8")

    migrate_live_link_schema()

    migrate_loose_gallery_images_from_assets_root()
    migrate_nercha_images_from_coupon_to_gallery()
    sync_gallery_metadata_with_disk()


def read_json_file(path: Path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        # Avoid crashes if a partial write ever happened.
        return {}


def write_json_file(path: Path, payload):
    directory = path.parent
    directory.mkdir(parents=True, exist_ok=True)
    # Unique temp file avoids cross-process clobbering.
    tmp_path = directory / (path.name + f".tmp_{os.getpid()}_{threading.get_ident()}_{secrets.token_hex(6)}")
    data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    with open(tmp_path, "wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.replace(str(tmp_path), str(path))
    # Best-effort directory fsync to reduce the chance of rename without persistence.
    try:
        with open(directory, "rb") as d:
            os.fsync(d.fileno())
    except Exception:
        pass


def sanitize_filename(name: str) -> str:
    name = os.path.basename(name)
    name = name.replace("\\", "_").replace("/", "_")
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-")
    cleaned = "".join(ch for ch in name if ch in allowed)
    return cleaned or f"upload_{secrets.token_hex(8)}"


def parse_multipart_files(content_type: str, body: bytes, field_name: str):
    files = []
    if "boundary=" not in content_type:
        return files

    boundary = content_type.split("boundary=", 1)[1].strip().strip('"')
    boundary_bytes = ("--" + boundary).encode("utf-8")
    parts = body.split(boundary_bytes)

    for part in parts:
        part = part.strip()
        if not part or part == b"--":
            continue

        if b"\r\n\r\n" not in part:
            continue

        headers_blob, payload = part.split(b"\r\n\r\n", 1)
        payload = payload.rstrip(b"\r\n")
        headers_text = headers_blob.decode("utf-8", errors="ignore")

        if "Content-Disposition" not in headers_text:
            continue

        name_token = f'name="{field_name}"'
        if name_token not in headers_text:
            continue

        filename = None
        part_content_type = None
        for line in headers_text.split("\r\n"):
            if "Content-Disposition" in line and 'filename="' in line:
                filename = line.split('filename="', 1)[1].split('"', 1)[0]
                break

            if line.lower().startswith("content-type:"):
                part_content_type = line.split(":", 1)[1].strip()

        if not filename:
            continue

        files.append((filename, payload, part_content_type))

    return files


def format_date_label(ts=None):
    if ts is None:
        ts = time.time()
    return time.strftime("%B %d, %Y", time.localtime(ts))


def format_time_label(ts=None):
    if ts is None:
        ts = time.time()
    return time.strftime("%I:%M %p", time.localtime(ts))


def _parse_date_label_to_ts(label) -> float:
    if not label or not isinstance(label, str):
        return 0.0
    try:
        return time.mktime(time.strptime(label.strip(), "%B %d, %Y"))
    except Exception:
        return 0.0


def _gallery_image_video_suffixes():
    image_suffixes = [".jpg", ".jpeg", ".png", ".gif", ".webp"]
    video_suffixes = [".mp4", ".mov", ".mkv", ".webm"]
    return image_suffixes, video_suffixes


def migrate_loose_gallery_images_from_assets_root():
    """Move gallery-oriented images from /assets/ into /assets/gallery/."""
    assets = ROOT_DIR / "assets"
    if not assets.is_dir():
        return
    GALLERY_DIR.mkdir(parents=True, exist_ok=True)
    for name in _GALLERY_RELOCATE_FROM_ASSETS_ROOT:
        src = assets / name
        if not src.is_file():
            continue
        dest = GALLERY_DIR / name
        if dest.exists():
            continue
        try:
            shutil.move(str(src), str(dest))
        except Exception:
            pass


def migrate_nercha_images_from_coupon_to_gallery():
    """Move offering images stored under assets/coupon into assets/gallery/ and fix JSON paths."""
    data = read_json_file(OFFERINGS_PATH)
    offerings = data.get("offerings", [])
    if not isinstance(offerings, list):
        return
    changed = False
    new_list = []
    GALLERY_DIR.mkdir(parents=True, exist_ok=True)
    for item in offerings:
        if not isinstance(item, dict):
            continue
        row = dict(item)
        img = (row.get("image") or "").strip()
        if img:
            safe = sanitize_filename(img)
            cpath = COUPON_DIR / safe
            gpath = GALLERY_DIR / safe
            if cpath.is_file():
                final_name = safe
                target = gpath
                if target.exists():
                    stem = Path(safe).stem
                    suf = Path(safe).suffix.lower() or ".jpg"
                    final_name = f"{stem}_{secrets.token_hex(4)}{suf}"
                    target = GALLERY_DIR / final_name
                try:
                    shutil.move(str(cpath), str(target))
                    row["image"] = final_name
                    changed = True
                except Exception:
                    pass
        new_list.append(row)
    if changed:
        with _lock_for_path(OFFERINGS_PATH):
            write_json_file(OFFERINGS_PATH, {"offerings": new_list})


def infer_live_kind_from_url(url: str) -> str:
    u = (url or "").strip().lower()
    if not u:
        return ""
    if "youtu.be" in u or "youtube.com" in u:
        return "youtube"
    if "facebook.com" in u or "fb.com" in u or "fb.watch" in u:
        return "facebook"
    return "facebook"


def migrate_live_link_schema():
    if not LIVE_LINK_PATH.exists():
        return
    data = read_json_file(LIVE_LINK_PATH)
    if not isinstance(data, dict):
        data = {}
    if "kind" in data and isinstance(data.get("kind"), str):
        return
    url = (data.get("url") or "").strip()
    kind = infer_live_kind_from_url(url) if url else ""
    with _lock_for_path(LIVE_LINK_PATH):
        write_json_file(LIVE_LINK_PATH, {"url": url, "kind": kind})


def sync_gallery_metadata_with_disk():
    """Ensure every file in assets/gallery/ appears in data/gallery.json (persistent, deployment-safe)."""
    image_suffixes, video_suffixes = _gallery_image_video_suffixes()
    allowed = set(image_suffixes + video_suffixes)
    GALLERY_DIR.mkdir(parents=True, exist_ok=True)

    with _lock_for_path(GALLERY_META_PATH):
        data = read_json_file(GALLERY_META_PATH)
        items = data.get("items", [])
        if not isinstance(items, list):
            items = []
        by_name = {}
        for item in items:
            if isinstance(item, dict) and item.get("filename"):
                by_name[item["filename"]] = dict(item)

        changed = False
        for f in GALLERY_DIR.iterdir():
            if not f.is_file():
                continue
            suf = f.suffix.lower()
            if suf not in allowed:
                continue
            name = f.name
            if name in by_name:
                continue
            st = f.stat()
            media_type = "video" if suf in video_suffixes else "image"
            by_name[name] = {
                "filename": name,
                "type": media_type,
                "date": format_date_label(st.st_mtime),
                "uploaded_at": st.st_mtime,
            }
            changed = True

        if not changed:
            return

        merged = list(by_name.values())

        def sort_key(it):
            ts = it.get("uploaded_at")
            if ts is None:
                ts = _parse_date_label_to_ts(it.get("date"))
            try:
                ts = float(ts)
            except (TypeError, ValueError):
                ts = 0.0
            return (ts, it.get("filename") or "")

        merged.sort(key=sort_key, reverse=True)
        write_json_file(GALLERY_META_PATH, {"items": merged})


def sort_gallery_items_for_api(items):
    if not isinstance(items, list):
        return []

    def sort_key(it):
        if not isinstance(it, dict):
            return (0.0, "")
        ts = it.get("uploaded_at")
        if ts is None:
            ts = _parse_date_label_to_ts(it.get("date"))
        try:
            ts = float(ts)
        except (TypeError, ValueError):
            ts = 0.0
        return (ts, it.get("filename") or "")

    return sorted(items, key=sort_key, reverse=True)


app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = int(os.environ.get("MAX_UPLOAD_BYTES", str(_DEFAULT_MAX_UPLOAD)))

_logger = logging.getLogger("piravomvalliyapalli")
if not _logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    _logger.addHandler(_handler)
_logger.setLevel(logging.INFO)

_LOCK_TIMEOUT_SECONDS = float(os.environ.get("LOCK_TIMEOUT_SECONDS", "10"))
_LOCK_POLL_SECONDS = float(os.environ.get("LOCK_POLL_SECONDS", "0.1"))


class _InterProcessFileLock:
    """
    Cross-process (and cross-thread) lock using a lock file.
    Used to protect JSON read-modify-write and to prevent corruption/races.
    """

    _local = threading.local()

    def __init__(self, target: Path):
        self.target = target
        self.lock_path = Path(str(target) + ".lock")
        self.fp = None
        self._key = str(self.lock_path)

    def __enter__(self):
        counts = getattr(self._local, "counts", None)
        if counts is None:
            counts = {}
            self._local.counts = counts

        current = counts.get(self._key, 0)
        if current > 0:
            counts[self._key] = current + 1
            return self

        # Ensure lock file exists.
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        self.fp = open(self.lock_path, "a+b")

        deadline = time.monotonic() + _LOCK_TIMEOUT_SECONDS
        acquired = False

        if os.name == "nt":
            import msvcrt

            while time.monotonic() < deadline:
                try:
                    # Lock first byte as a sentinel.
                    msvcrt.locking(self.fp.fileno(), msvcrt.LK_NBLCK, 1)
                    acquired = True
                    break
                except OSError as e:
                    if e.errno in (errno.EACCES, errno.EAGAIN):
                        time.sleep(_LOCK_POLL_SECONDS)
                        continue
                    raise
        else:
            import fcntl

            while time.monotonic() < deadline:
                try:
                    fcntl.flock(self.fp.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    acquired = True
                    break
                except OSError as e:
                    if e.errno in (errno.EACCES, errno.EAGAIN):
                        time.sleep(_LOCK_POLL_SECONDS)
                        continue
                    raise

        if not acquired:
            try:
                self.fp.close()
            except Exception:
                pass
            self.fp = None
            raise TimeoutError(f"Could not acquire lock for {self.lock_path}")

        counts[self._key] = 1
        return self

    def __exit__(self, exc_type, exc, tb):
        counts = getattr(self._local, "counts", None) or {}
        current = counts.get(self._key, 0)
        if current <= 1:
            try:
                if self.fp:
                    if os.name == "nt":
                        import msvcrt

                        msvcrt.locking(self.fp.fileno(), msvcrt.LK_UNLCK, 1)
                    else:
                        import fcntl

                        fcntl.flock(self.fp.fileno(), fcntl.LOCK_UN)
            finally:
                try:
                    if self.fp:
                        self.fp.close()
                except Exception:
                    pass
                self.fp = None
                counts.pop(self._key, None)
        else:
            counts[self._key] = current - 1
        self._local.counts = counts


def _lock_for_path(path: Path):
    return _InterProcessFileLock(path)


def json_response(status: int, payload: dict):
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    resp = make_response(data, status)
    resp.headers["Content-Type"] = "application/json; charset=utf-8"
    resp.headers["Content-Length"] = str(len(data))
    return resp


def not_found():
    return Response(b"Not Found", status=404, content_type="text/plain; charset=utf-8")


def serve_static(url_path: str):
    # Map "pretty paths" to existing files
    if url_path == "/":
        file_path = ROOT_DIR / "index.html"
    elif url_path == "/admin":
        file_path = ROOT_DIR / "admin.html"
    elif url_path == "/nerchas":
        file_path = ROOT_DIR / "nerchas.html"
    elif url_path == "/history":
        file_path = ROOT_DIR / "history.html"
    else:
        safe_rel = url_path.lstrip("/")
        safe_path = (ROOT_DIR / safe_rel).resolve()
        if ROOT_DIR not in safe_path.parents and safe_path != ROOT_DIR / "index.html":
            return not_found()
        file_path = safe_path

    if not file_path.exists() or not file_path.is_file():
        return not_found()

    mime_type, _ = mimetypes.guess_type(str(file_path))
    mime_type = mime_type or "application/octet-stream"
    data = file_path.read_bytes()
    resp = Response(data, status=200, mimetype=mime_type)
    resp.headers["Content-Length"] = str(len(data))
    return resp


_SESSION_HMAC_SECRET = os.environ.get("SESSION_HMAC_SECRET")
if not _SESSION_HMAC_SECRET:
    # Deterministic secret across gunicorn workers (same ROOT_DIR path).
    _SESSION_HMAC_SECRET = hashlib.sha256(str(ROOT_DIR).encode("utf-8")).hexdigest()
_SESSION_HMAC_SECRET_BYTES = _SESSION_HMAC_SECRET.encode("utf-8")


def _sign_session(nonce: str, ts_int: int) -> str:
    msg = f"{nonce}|{ts_int}".encode("utf-8")
    return hmac.new(_SESSION_HMAC_SECRET_BYTES, msg, hashlib.sha256).hexdigest()


def _make_session_cookie_value(ts_int=None) -> str:
    if ts_int is None:
        ts_int = int(time.time())
    nonce = secrets.token_urlsafe(16)
    sig = _sign_session(nonce, int(ts_int))
    return f"{nonce}.{int(ts_int)}.{sig}"


def is_logged_in() -> bool:
    value = request.cookies.get(SESSION_COOKIE)
    if not value:
        return False
    parts = value.split(".")
    if len(parts) != 3:
        return False
    nonce, ts_s, sig = parts
    try:
        ts_int = int(ts_s)
    except Exception:
        return False
    expected = _sign_session(nonce, ts_int)
    if not hmac.compare_digest(expected, sig):
        return False
    if time.time() - ts_int > SESSION_TTL_SECONDS:
        return False
    return True


_RATE_GUARD = threading.Lock()
_RATE_STATE = {}  # key -> list[timestamps]


def _client_ip() -> str:
    xf = request.headers.get("X-Forwarded-For", "").strip()
    if xf:
        return xf.split(",")[0].strip()
    return request.remote_addr or "unknown"


def _rate_limit(key: str, limit: int, window_seconds: int) -> bool:
    now = time.time()
    cutoff = now - window_seconds
    with _RATE_GUARD:
        arr = _RATE_STATE.get(key, [])
        arr = [t for t in arr if t >= cutoff]
        if len(arr) >= limit:
            _RATE_STATE[key] = arr
            return False
        arr.append(now)
        _RATE_STATE[key] = arr
        return True


@app.before_request
def _before_request():
    if request.path.startswith("/api/") and request.method in ["POST", "PUT"]:
        # Basic in-memory rate limiting (per worker).
        ip = _client_ip()
        if request.path == "/api/login":
            allowed = _rate_limit(f"rl:{ip}:{request.path}", 8, 600)
        elif request.path == "/api/purchase":
            allowed = _rate_limit(f"rl:{ip}:{request.path}", 30, 600)
        elif request.path in ["/api/gallery/upload", "/api/calendar/upload", "/api/nercha-image/upload"]:
            allowed = _rate_limit(f"rl:{ip}:{request.path}", 10, 600)
        else:
            allowed = _rate_limit(f"rl:{ip}:{request.path}", 120, 600)
        if not allowed:
            _logger.warning("Rate limited %s %s from %s", request.method, request.path, ip)
            return json_response(429, {"error": "unauthorized"})


@app.before_request
def _request_logging_start():
    if request.path.startswith("/api/"):
        g.req_id = secrets.token_hex(8)
        g.req_start = time.perf_counter()


@app.after_request
def _request_logging_end(resp):
    if request.path.startswith("/api/"):
        start = getattr(g, "req_start", None)
        dur_ms = None
        if start is not None:
            dur_ms = int((time.perf_counter() - start) * 1000)
        ip = _client_ip()
        _logger.info(
            "api_request req_id=%s ip=%s method=%s path=%s status=%s duration_ms=%s",
            getattr(g, "req_id", "-"),
            ip,
            request.method,
            request.path,
            getattr(resp, "status_code", "-"),
            dur_ms if dur_ms is not None else "-"
        )
    return resp


@app.errorhandler(413)
def _handle_413(_e):
    if request.path.startswith("/api/"):
        return json_response(413, {"error": "upload_too_large"})
    return not_found()


@app.errorhandler(Exception)
def _handle_exception(_e):
    if request.path.startswith("/api/"):
        _logger.exception("Unhandled error on API route %s", request.path)
        return json_response(500, {"error": "server_error"})
    _logger.exception("Unhandled error")
    return not_found()


ensure_data_files()


@app.route("/", methods=["GET"])
def route_root():
    return serve_static("/")


@app.route("/admin", methods=["GET"])
def route_admin():
    return serve_static("/admin")


@app.route("/nerchas", methods=["GET"])
def route_nerchas():
    return serve_static("/nerchas")


@app.route("/history", methods=["GET"])
def route_history():
    return serve_static("/history")


@app.route("/<path:url_path>", methods=["GET"])
def route_catch_all(url_path: str):
    # Let any /api routes be handled by explicit Flask routes.
    return serve_static("/" + url_path)


@app.route("/api/nerchas", methods=["GET"])
def api_get_nerchas():
    data = read_json_file(OFFERINGS_PATH)
    offerings = []
    for item in data.get("offerings", []):
        if not isinstance(item, dict):
            continue
        row = dict(item)
        row.setdefault("image", "")
        offerings.append(row)
    _logger.info("api_get_nerchas")
    return json_response(200, {"offerings": offerings})


@app.route("/api/nerchas", methods=["PUT"])
def api_put_nerchas():
    if not is_logged_in():
        return json_response(401, {"error": "unauthorized"})
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        body = {}
    offerings = body.get("offerings", [])
    cleaned = []
    if isinstance(offerings, list):
        for item in offerings:
            if not isinstance(item, dict):
                continue
            english = (item.get("english") or "").strip()
            malayalam = (item.get("malayalam") or "").strip()
            try:
                price = int(item.get("price"))
            except Exception:
                price = 0
            image = (item.get("image") or "").strip()
            if image:
                image = sanitize_filename(image)
            cleaned.append({"english": english, "malayalam": malayalam, "price": price, "image": image})
    with _lock_for_path(OFFERINGS_PATH):
        write_json_file(OFFERINGS_PATH, {"offerings": cleaned})
    _logger.info("admin updated nerchas")
    return json_response(200, {"ok": True})


@app.route("/api/purchases", methods=["GET"])
def api_get_purchases():
    if not is_logged_in():
        return json_response(401, {"error": "unauthorized"})
    data = read_json_file(PURCHASES_PATH)
    return json_response(200, {"purchases": data.get("purchases", [])})


@app.route("/api/gallery", methods=["GET"])
def api_get_gallery():
    sync_gallery_metadata_with_disk()
    data = read_json_file(GALLERY_META_PATH)
    items = data.get("items", [])
    if not isinstance(items, list):
        items = []
    return json_response(200, {"items": sort_gallery_items_for_api(items)})


@app.route("/api/gallery/upload", methods=["POST"])
def api_upload_gallery():
    if not is_logged_in():
        return json_response(401, {"error": "unauthorized"})

    ctype = request.content_type or ""
    if "multipart/form-data" not in ctype:
        return json_response(400, {"error": "expected multipart/form-data"})

    body = request.get_data(cache=False)
    media_files = parse_multipart_files(ctype, body, "media")
    if not media_files:
        return json_response(400, {"error": "no files uploaded"})

    uploaded = []
    now_ts = time.time()
    label = format_date_label(now_ts)
    image_suffixes, video_suffixes = _gallery_image_video_suffixes()
    prepared = []
    max_file_bytes = int(os.environ.get("MAX_FILE_BYTES", str(_DEFAULT_MAX_FILE)))
    for raw_filename, file_bytes, part_ct in media_files:
        if len(file_bytes) > max_file_bytes:
            return json_response(400, {"error": "file_too_large"})
        filename = sanitize_filename(raw_filename)
        suffix = Path(filename).suffix.lower()
        if suffix not in image_suffixes and suffix not in video_suffixes:
            return json_response(400, {"error": "unsupported media type"})
        if part_ct:
            lowered = part_ct.lower().split(";")[0].strip()
            if suffix in video_suffixes:
                if not (lowered.startswith("video/") or lowered == "application/octet-stream"):
                    return json_response(400, {"error": "unsupported media type"})
            else:
                if not (lowered.startswith("image/") or lowered == "application/octet-stream"):
                    return json_response(400, {"error": "unsupported media type"})
        prepared.append((filename, suffix, file_bytes))

    with _lock_for_path(GALLERY_META_PATH):
        gallery_data = read_json_file(GALLERY_META_PATH)
        gallery_items = gallery_data.get("items", [])
        if not isinstance(gallery_items, list):
            gallery_items = []
        for filename, suffix, file_bytes in prepared:
            out_path = GALLERY_DIR / filename
            if out_path.exists():
                out_path = GALLERY_DIR / f"{Path(filename).stem}_{secrets.token_hex(4)}{suffix}"

            out_path.write_bytes(file_bytes)
            uploaded.append(out_path.name)
            media_type = "video" if suffix in video_suffixes else "image"
            gallery_items.append(
                {
                    "filename": out_path.name,
                    "type": media_type,
                    "date": label,
                    "uploaded_at": now_ts,
                }
            )

        gallery_items = sort_gallery_items_for_api(gallery_items)
        write_json_file(GALLERY_META_PATH, {"items": gallery_items})

    _logger.info("admin gallery upload: %d file(s)", len(uploaded))
    return json_response(200, {"ok": True, "message": f"Uploaded {len(uploaded)} file(s).", "files": uploaded})


@app.route("/api/gallery/delete", methods=["POST"])
def api_delete_gallery():
    if not is_logged_in():
        return json_response(401, {"error": "unauthorized"})

    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        body = {}
    filename = sanitize_filename(body.get("filename", ""))
    if not filename:
        return json_response(400, {"error": "filename required"})

    with _lock_for_path(GALLERY_META_PATH):
        gallery_data = read_json_file(GALLERY_META_PATH)
        items = gallery_data.get("items", [])
        items = [item for item in items if item.get("filename") != filename]
        write_json_file(GALLERY_META_PATH, {"items": items})

    target = GALLERY_DIR / filename
    if target.exists() and target.is_file():
        target.unlink()

    _logger.info("admin gallery delete: %s", filename)
    return json_response(200, {"ok": True})


@app.route("/api/nercha-image/upload", methods=["POST"])
def api_upload_nercha_image():
    if not is_logged_in():
        return json_response(401, {"error": "unauthorized"})

    ctype = request.content_type or ""
    if "multipart/form-data" not in ctype:
        return json_response(400, {"error": "expected multipart/form-data"})

    body = request.get_data(cache=False)
    media_files = parse_multipart_files(ctype, body, "nercha_image")
    if not media_files:
        return json_response(400, {"error": "no file uploaded"})

    raw_filename, file_bytes, part_ct = media_files[0]
    max_file_bytes = int(os.environ.get("MAX_FILE_BYTES", str(_DEFAULT_MAX_FILE)))
    if len(file_bytes) > max_file_bytes:
        return json_response(400, {"error": "file_too_large"})
    filename = sanitize_filename(raw_filename)
    suffix = Path(filename).suffix.lower()
    if suffix not in [".jpg", ".jpeg", ".png", ".gif", ".webp"]:
        return json_response(400, {"error": "unsupported image type"})
    if part_ct:
        lowered = part_ct.lower().split(";")[0].strip()
        if not (lowered.startswith("image/") or lowered == "application/octet-stream"):
            return json_response(400, {"error": "unsupported image type"})
    GALLERY_DIR.mkdir(parents=True, exist_ok=True)
    with _lock_for_path(GALLERY_META_PATH):
        out_path = GALLERY_DIR / filename
        if out_path.exists():
            out_path = GALLERY_DIR / f"{Path(filename).stem}_{secrets.token_hex(4)}{suffix}"

        out_path.write_bytes(file_bytes)
        now_ts = time.time()
        label = format_date_label(now_ts)
        gallery_data = read_json_file(GALLERY_META_PATH)
        gallery_items = gallery_data.get("items", [])
        if not isinstance(gallery_items, list):
            gallery_items = []
        gallery_items.append(
            {
                "filename": out_path.name,
                "type": "image",
                "date": label,
                "uploaded_at": now_ts,
            }
        )
        gallery_items = sort_gallery_items_for_api(gallery_items)
        write_json_file(GALLERY_META_PATH, {"items": gallery_items})
        _logger.info("admin nercha image upload (gallery): %s", out_path.name)
        return json_response(200, {"ok": True, "filename": out_path.name})


@app.route("/api/calendar", methods=["GET"])
def api_get_calendar():
    images = []
    if CALENDAR_DIR.exists():
        for f in sorted(CALENDAR_DIR.iterdir()):
            if f.is_file() and f.suffix.lower() in [".jpg", ".jpeg", ".png", ".gif", ".webp"]:
                images.append(f.name)
    return json_response(200, {"images": images})


@app.route("/api/calendar/upload", methods=["POST"])
def api_upload_calendar():
    if not is_logged_in():
        return json_response(401, {"error": "unauthorized"})

    ctype = request.content_type or ""
    if "multipart/form-data" not in ctype:
        return json_response(400, {"error": "expected multipart/form-data"})

    body = request.get_data(cache=False)
    media_files = parse_multipart_files(ctype, body, "calendar")
    if not media_files:
        return json_response(400, {"error": "no files uploaded"})

    uploaded = []
    max_file_bytes = int(os.environ.get("MAX_FILE_BYTES", str(_DEFAULT_MAX_FILE)))
    with _lock_for_path(CALENDAR_FS_LOCK_PATH):
        for raw_filename, file_bytes, part_ct in media_files:
            if len(file_bytes) > max_file_bytes:
                return json_response(400, {"error": "file_too_large"})
            filename = sanitize_filename(raw_filename)
            suffix = Path(filename).suffix.lower()
            if suffix not in [".jpg", ".jpeg", ".png", ".gif", ".webp"]:
                continue
            if part_ct:
                lowered = part_ct.lower().split(";")[0].strip()
                if not (lowered.startswith("image/") or lowered == "application/octet-stream"):
                    continue
            out_path = CALENDAR_DIR / filename
            if out_path.exists():
                out_path = CALENDAR_DIR / f"{Path(filename).stem}_{secrets.token_hex(4)}{suffix}"
            out_path.write_bytes(file_bytes)
            uploaded.append(out_path.name)

    _logger.info("admin calendar upload: %d file(s)", len(uploaded))
    return json_response(200, {"ok": True, "message": f"Uploaded {len(uploaded)} file(s).", "images": uploaded})


@app.route("/api/calendar/delete", methods=["POST"])
def api_delete_calendar():
    if not is_logged_in():
        return json_response(401, {"error": "unauthorized"})

    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        body = {}
    filename = sanitize_filename(body.get("filename", ""))
    if not filename:
        return json_response(400, {"error": "filename required"})
    with _lock_for_path(CALENDAR_FS_LOCK_PATH):
        target = CALENDAR_DIR / filename
        if target.exists() and target.is_file():
            target.unlink()

    _logger.info("admin calendar delete: %s", filename)
    return json_response(200, {"ok": True})


_PAYMENT_HMAC_SECRET = (
    os.environ.get("PAYMENT_HMAC_SECRET")
    or os.environ.get("PAYMENT_WEBHOOK_SECRET")
    or ""
).strip()


def _verify_payment_signature(provider: str, transaction_id: str, signature: str) -> (bool, str):
    """
    Verify payment signature using HMAC-SHA256 over provider+transaction_id.
    This does not require any payment gateway SDK; it is purely server-side verification.
    """
    if not _PAYMENT_HMAC_SECRET:
        return False, "missing_payment_secret"
    provider = (provider or "").strip().lower() or "generic"
    msg = f"{provider}|{transaction_id}".encode("utf-8")
    expected = hmac.new(_PAYMENT_HMAC_SECRET.encode("utf-8"), msg, hashlib.sha256).hexdigest()
    if hmac.compare_digest(expected, signature):
        return True, "verified"
    return False, "signature_mismatch"


@app.route("/api/purchase", methods=["POST"])
def api_purchase():
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        body = {}

    # Payment safety fields (only used when provided by the client).
    transaction_id = str(body.get("transaction_id") or body.get("transactionId") or body.get("payment_id") or "").strip()
    signature = str(body.get("signature") or body.get("signature_value") or body.get("signatureId") or "").strip()
    provider = str(body.get("provider") or body.get("gateway") or "").strip()

    purchases = []
    with _lock_for_path(PURCHASES_PATH):
        purchases = read_json_file(PURCHASES_PATH).get("purchases", [])

        # Prevent duplicate transactions if an ID is provided.
        if transaction_id:
            for p in purchases:
                if str(p.get("transaction_id", "")).strip() == transaction_id:
                    _logger.warning("purchase duplicate transaction_id blocked: %s", transaction_id)
                    return json_response(200, {"ok": True})

        ts = time.time()

        payment_status = "pending"
        payment_error = ""
        if transaction_id and signature:
            ok, reason = _verify_payment_signature(provider, transaction_id, signature)
            payment_status = "success" if ok else "failed"
            payment_error = "" if ok else reason

        record = {
            "name": str(body.get("name") or "").strip(),
            "address": str(body.get("address") or "").strip(),
            "phone": str(body.get("phone") or "").strip(),
            "malayalam": str(body.get("malayalam") or "").strip(),
            "english": str(body.get("english") or "").strip(),
            "price": int(body.get("price") or 0),
            "date": format_date_label(ts),
            "time": format_time_label(ts),
            "timestamp": int(ts),
            "payment_status": payment_status
        }

        if transaction_id:
            record["transaction_id"] = transaction_id
            if provider:
                record["provider"] = provider
        if payment_error:
            record["payment_error"] = payment_error

        purchases.append(record)
        write_json_file(PURCHASES_PATH, {"purchases": purchases})

    _logger.info(
        "purchase recorded: status=%s tx=%s",
        payment_status,
        transaction_id if transaction_id else "-"
    )
    return json_response(200, {"ok": True})


@app.route("/api/live-link", methods=["GET"])
def api_live_link_get():
    data = read_json_file(LIVE_LINK_PATH)
    if not isinstance(data, dict):
        data = {}
    url = (data.get("url") or "").strip()
    kind = (data.get("kind") or "").strip().lower()
    if kind not in ("facebook", "youtube", ""):
        kind = ""
    if url and not kind:
        kind = infer_live_kind_from_url(url)
    return json_response(200, {"url": url, "kind": kind})


@app.route("/api/live-link", methods=["PUT"])
def api_live_link_put():
    if not is_logged_in():
        return json_response(401, {"error": "unauthorized"})
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        body = {}
    url = (body.get("url") or "").strip()
    kind = (body.get("kind") or "").strip().lower()
    if url:
        if kind not in ("facebook", "youtube"):
            return json_response(400, {"error": "invalid_kind"})
    else:
        kind = ""
    with _lock_for_path(LIVE_LINK_PATH):
        write_json_file(LIVE_LINK_PATH, {"url": url, "kind": kind})
    _logger.info("admin live url updated kind=%s", kind or "-")
    return json_response(200, {"ok": True})


@app.route("/api/login", methods=["POST"])
def api_login():
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        body = {}
    username = (body.get("username") or "").strip()
    password = (body.get("password") or "").strip()

    if username == "media" and password == "valiyapalli216":
        token_value = _make_session_cookie_value()
        resp = json_response(200, {"ok": True})
        resp.set_cookie(
            SESSION_COOKIE,
            token_value,
            httponly=True,
            path="/",
            max_age=SESSION_TTL_SECONDS,
            samesite="Lax",
        )
        _logger.info("admin login ok")
        return resp

    _logger.warning("admin login failed")
    return json_response(401, {"error": "invalid_credentials"})


@app.route("/api/logout", methods=["POST"])
def api_logout():
    resp = json_response(200, {"ok": True})
    resp.set_cookie(
        SESSION_COOKIE,
        "",
        httponly=True,
        path="/",
        max_age=0,
        samesite="Lax",
    )
    _logger.info("admin logout")
    return resp


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5500"))
    print(f"Serving on http://localhost:{port}")
    # Threaded mode for local runs; production should use gunicorn.
    app.run(host="0.0.0.0", port=port, threaded=True)

