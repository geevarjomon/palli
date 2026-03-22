import os
import json
import mimetypes
import secrets
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent
DATA_DIR = ROOT_DIR / "data"
GALLERY_DIR = ROOT_DIR / "assets" / "gallery"
COUPON_DIR = ROOT_DIR / "assets" / "coupon"
CALENDAR_DIR = ROOT_DIR / "assets" / "calendar"

OFFERINGS_PATH = DATA_DIR / "nerchas.json"
PURCHASES_PATH = DATA_DIR / "purchases.json"
GALLERY_META_PATH = DATA_DIR / "gallery.json"
LIVE_LINK_PATH = DATA_DIR / "live_link.json"

SESSION_COOKIE = "admin_session"
SESSION_TTL_SECONDS = 60 * 60 * 6  # 6 hours


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
        LIVE_LINK_PATH.write_text(json.dumps({"url": ""}, ensure_ascii=False, indent=2), encoding="utf-8")


def read_json_file(path: Path):
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_json_file(path: Path, payload):
    tmp_path = path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(path)


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
        for line in headers_text.split("\r\n"):
            if "Content-Disposition" in line and 'filename="' in line:
                filename = line.split('filename="', 1)[1].split('"', 1)[0]
                break

        if not filename:
            continue

        files.append((filename, payload))

    return files


def format_date_label(ts=None):
    if ts is None:
        ts = time.time()
    return time.strftime("%B %d, %Y", time.localtime(ts))


def format_time_label(ts=None):
    if ts is None:
        ts = time.time()
    return time.strftime("%I:%M %p", time.localtime(ts))


def get_cookie(handler: BaseHTTPRequestHandler, name: str):
    cookie_header = handler.headers.get("Cookie")
    if not cookie_header:
        return None
    parts = cookie_header.split(";")
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if part.startswith(name + "="):
            return part.split("=", 1)[1]
    return None


def is_logged_in(handler: BaseHTTPRequestHandler):
    token = get_cookie(handler, SESSION_COOKIE)
    if not token:
        return False
    sess = SESSIONS.get(token)
    if not sess:
        return False
    if time.time() - sess["created_at"] > SESSION_TTL_SECONDS:
        SESSIONS.pop(token, None)
        return False
    return True


def json_response(handler: BaseHTTPRequestHandler, status: int, payload):
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


def not_found(handler: BaseHTTPRequestHandler):
    handler.send_response(404)
    handler.end_headers()
    handler.wfile.write(b"Not Found")


def serve_static(handler: BaseHTTPRequestHandler, url_path: str):
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
        # strip leading slash and prevent path traversal
        safe_rel = url_path.lstrip("/")
        safe_path = (ROOT_DIR / safe_rel).resolve()
        if ROOT_DIR not in safe_path.parents and safe_path != ROOT_DIR / "index.html":
            return not_found(handler)
        file_path = safe_path

    if not file_path.exists() or not file_path.is_file():
        return not_found(handler)

    mime_type, _ = mimetypes.guess_type(str(file_path))
    mime_type = mime_type or "application/octet-stream"

    data = file_path.read_bytes()
    handler.send_response(200)
    handler.send_header("Content-Type", mime_type)
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


class Handler(BaseHTTPRequestHandler):
    server_version = "PiravomLocalServer/1.0"

    def _read_body(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return b""
        return self.rfile.read(length)

    def _parse_json_body(self):
        raw = self._read_body()
        if not raw:
            return {}
        return json.loads(raw.decode("utf-8"))

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/api/nerchas":
            data = read_json_file(OFFERINGS_PATH)
            offerings = []
            for item in data.get("offerings", []):
                if not isinstance(item, dict):
                    continue
                row = dict(item)
                row.setdefault("image", "")
                offerings.append(row)
            return json_response(self, 200, {"offerings": offerings})

        if path == "/api/purchases":
            if not is_logged_in(self):
                return json_response(self, 401, {"error": "unauthorized"})
            data = read_json_file(PURCHASES_PATH)
            return json_response(self, 200, {"purchases": data.get("purchases", [])})

        if path == "/api/gallery":
            data = read_json_file(GALLERY_META_PATH)
            return json_response(self, 200, {"items": data.get("items", [])})

        if path == "/api/live-link":
            data = read_json_file(LIVE_LINK_PATH)
            return json_response(self, 200, {"url": data.get("url", "")})

        if path == "/api/calendar":
            images = []
            if CALENDAR_DIR.exists():
                for f in sorted(CALENDAR_DIR.iterdir()):
                    if f.is_file() and f.suffix.lower() in [".jpg", ".jpeg", ".png", ".gif", ".webp"]:
                        images.append(f.name)
            return json_response(self, 200, {"images": images})

        # fallback static
        return serve_static(self, path)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/api/login":
            body = self._parse_json_body()
            username = (body.get("username") or "").strip()
            password = (body.get("password") or "").strip()

            if username == "media" and password == "valiyapalli216":
                token = secrets.token_hex(24)
                SESSIONS[token] = {"created_at": time.time()}
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Set-Cookie", f"{SESSION_COOKIE}={token}; HttpOnly; Path=/")
                payload = json.dumps({"ok": True}).encode("utf-8")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
                return

            return json_response(self, 401, {"error": "invalid_credentials"})

        if path == "/api/logout":
            token = get_cookie(self, SESSION_COOKIE)
            if token and token in SESSIONS:
                SESSIONS.pop(token, None)
            # expire cookie
            self.send_response(200)
            self.send_header("Set-Cookie", f"{SESSION_COOKIE}=; HttpOnly; Path=/; Max-Age=0")
            self.send_header("Content-Type", "application/json; charset=utf-8")
            payload = json.dumps({"ok": True}).encode("utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return

        if path == "/api/nercha-image/upload":
            if not is_logged_in(self):
                return json_response(self, 401, {"error": "unauthorized"})

            ctype = self.headers.get("Content-Type", "")
            if "multipart/form-data" not in ctype:
                return json_response(self, 400, {"error": "expected multipart/form-data"})

            body = self._read_body()
            media_files = parse_multipart_files(ctype, body, "nercha_image")
            if not media_files:
                return json_response(self, 400, {"error": "no file uploaded"})

            raw_filename, file_bytes = media_files[0]
            filename = sanitize_filename(raw_filename)
            suffix = Path(filename).suffix.lower()
            if suffix not in [".jpg", ".jpeg", ".png", ".gif", ".webp"]:
                return json_response(self, 400, {"error": "unsupported image type"})

            out_path = COUPON_DIR / filename
            if out_path.exists():
                out_path = COUPON_DIR / f"{Path(filename).stem}_{secrets.token_hex(4)}{suffix}"

            out_path.write_bytes(file_bytes)
            return json_response(self, 200, {"ok": True, "filename": out_path.name})

        if path == "/api/calendar/upload":
            if not is_logged_in(self):
                return json_response(self, 401, {"error": "unauthorized"})

            ctype = self.headers.get("Content-Type", "")
            if "multipart/form-data" not in ctype:
                return json_response(self, 400, {"error": "expected multipart/form-data"})

            body = self._read_body()
            media_files = parse_multipart_files(ctype, body, "calendar")
            if not media_files:
                return json_response(self, 400, {"error": "no files uploaded"})

            uploaded = []
            for raw_filename, file_bytes in media_files:
                filename = sanitize_filename(raw_filename)
                suffix = Path(filename).suffix.lower()
                if suffix not in [".jpg", ".jpeg", ".png", ".gif", ".webp"]:
                    continue
                out_path = CALENDAR_DIR / filename
                if out_path.exists():
                    out_path = CALENDAR_DIR / f"{Path(filename).stem}_{secrets.token_hex(4)}{suffix}"
                out_path.write_bytes(file_bytes)
                uploaded.append(out_path.name)

            return json_response(self, 200, {"ok": True, "message": f"Uploaded {len(uploaded)} file(s).", "images": uploaded})

        if path == "/api/calendar/delete":
            if not is_logged_in(self):
                return json_response(self, 401, {"error": "unauthorized"})

            body = self._parse_json_body()
            filename = sanitize_filename(body.get("filename", ""))
            if not filename:
                return json_response(self, 400, {"error": "filename required"})

            target = CALENDAR_DIR / filename
            if target.exists() and target.is_file():
                target.unlink()

            return json_response(self, 200, {"ok": True})

        if path == "/api/gallery/upload":
            if not is_logged_in(self):
                return json_response(self, 401, {"error": "unauthorized"})

            ctype = self.headers.get("Content-Type", "")
            if "multipart/form-data" not in ctype:
                return json_response(self, 400, {"error": "expected multipart/form-data"})

            body = self._read_body()
            media_files = parse_multipart_files(ctype, body, "media")
            if not media_files:
                return json_response(self, 400, {"error": "no files uploaded"})

            uploaded = []
            gallery_data = read_json_file(GALLERY_META_PATH)
            gallery_items = gallery_data.get("items", [])
            label = format_date_label()
            for raw_filename, file_bytes in media_files:
                filename = sanitize_filename(raw_filename)
                suffix = Path(filename).suffix.lower()
                out_path = GALLERY_DIR / filename
                # avoid overwrite: add suffix if exists
                if out_path.exists():
                    out_path = GALLERY_DIR / f"{Path(filename).stem}_{secrets.token_hex(4)}{suffix}"

                out_path.write_bytes(file_bytes)
                uploaded.append(out_path.name)
                media_type = "video" if suffix in [".mp4", ".mov", ".mkv", ".webm"] else "image"
                gallery_items.append({"filename": out_path.name, "type": media_type, "date": label})

            write_json_file(GALLERY_META_PATH, {"items": gallery_items})

            return json_response(self, 200, {"ok": True, "message": f"Uploaded {len(uploaded)} file(s).", "files": uploaded})

        if path == "/api/purchase":
            body = self._parse_json_body()
            purchases = read_json_file(PURCHASES_PATH).get("purchases", [])
            ts = time.time()
            purchases.append({
                "name": (body.get("name") or "").strip(),
                "address": (body.get("address") or "").strip(),
                "phone": (body.get("phone") or "").strip(),
                "malayalam": (body.get("malayalam") or "").strip(),
                "english": (body.get("english") or "").strip(),
                "price": int(body.get("price") or 0),
                "date": format_date_label(ts),
                "time": format_time_label(ts),
                "timestamp": int(ts)
            })
            write_json_file(PURCHASES_PATH, {"purchases": purchases})
            return json_response(self, 200, {"ok": True})

        if path == "/api/gallery/delete":
            if not is_logged_in(self):
                return json_response(self, 401, {"error": "unauthorized"})

            body = self._parse_json_body()
            filename = sanitize_filename(body.get("filename", ""))
            if not filename:
                return json_response(self, 400, {"error": "filename required"})

            gallery_data = read_json_file(GALLERY_META_PATH)
            items = gallery_data.get("items", [])
            items = [item for item in items if item.get("filename") != filename]
            write_json_file(GALLERY_META_PATH, {"items": items})

            target = GALLERY_DIR / filename
            if target.exists() and target.is_file():
                target.unlink()

            return json_response(self, 200, {"ok": True})

        return not_found(self)

    def do_PUT(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/api/nerchas":
            if not is_logged_in(self):
                return json_response(self, 401, {"error": "unauthorized"})

            body = self._parse_json_body()
            offerings = body.get("offerings", [])
            # Validate minimal structure
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

            write_json_file(OFFERINGS_PATH, {"offerings": cleaned})
            return json_response(self, 200, {"ok": True})

        if path == "/api/live-link":
            if not is_logged_in(self):
                return json_response(self, 401, {"error": "unauthorized"})
            body = self._parse_json_body()
            url = (body.get("url") or "").strip()
            write_json_file(LIVE_LINK_PATH, {"url": url})
            return json_response(self, 200, {"ok": True})

        return not_found(self)

    def log_message(self, format, *args):
        # Silence default request logging for cleaner local runs.
        return


class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


def run(port: int = 5500):
    ensure_data_files()
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"Serving on http://localhost:{port}")
    server.serve_forever()


if __name__ == "__main__":
    run()

