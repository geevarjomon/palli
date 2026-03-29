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
ASSET_FS_LOCK_PATH = DATA_DIR / "_asset_fs_lock"
HOMEPAGE_CONTENT_PATH = DATA_DIR / "homepage.json"
ABOUT_CONTENT_PATH = DATA_DIR / "about.json"
HISTORY_CONTENT_PATH = DATA_DIR / "history_content.json"
EVENTS_CONTENT_PATH = DATA_DIR / "events.json"
PRIESTS_CONTENT_PATH = DATA_DIR / "priests.json"
HKMEDIA_CONTENT_PATH = DATA_DIR / "hkmedia_content.json"
LIVE_SCHEDULE_PATH = DATA_DIR / "live_schedule.json"

SESSION_COOKIE = "admin_session"
SESSION_TTL_SECONDS = 60 * 60 * 6  # 6 hours

# SHA-256 credential hashes for built-in admin accounts.
# Use ADMIN_CREDENTIAL_HASHES_JSON to override/extend in production:
# {"username":"sha256hex", ...}
_ADMIN_CREDENTIAL_HASHES = {
    "media": "3af0dcb115a95e7e40417ddc5c0a2c2217ffeca1e9331a2ab34ecd0aa043b5c0",
    "jobin": "9e85129d32f8e71aae86894e91c7b3d3c014fc4c39ef05dd7c89b32b4f6c891d",
}
_ADMIN_ROLES = {
    "jobin": "super_admin",
    "media": "limited_admin",
}


def _load_admin_credential_hashes():
    raw = os.environ.get("ADMIN_CREDENTIAL_HASHES_JSON", "").strip()
    if not raw:
        return dict(_ADMIN_CREDENTIAL_HASHES)
    try:
        parsed = json.loads(raw)
    except Exception:
        return dict(_ADMIN_CREDENTIAL_HASHES)
    if not isinstance(parsed, dict):
        return dict(_ADMIN_CREDENTIAL_HASHES)

    merged = dict(_ADMIN_CREDENTIAL_HASHES)
    for k, v in parsed.items():
        if not isinstance(k, str) or not isinstance(v, str):
            continue
        u = k.strip()
        h = v.strip().lower()
        if not u or len(h) != 64:
            continue
        merged[u] = h
    return merged


def _hash_password_sha256(password: str) -> str:
    return hashlib.sha256((password or "").encode("utf-8")).hexdigest()


def _is_valid_admin_login(username: str, password: str) -> bool:
    user = (username or "").strip()
    if not user:
        return False
    hashes = _load_admin_credential_hashes()
    expected_hash = hashes.get(user)
    if not expected_hash:
        return False
    incoming_hash = _hash_password_sha256((password or "").strip())
    return hmac.compare_digest(expected_hash, incoming_hash)


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

DEFAULT_HOMEPAGE_CONTENT = {
    "hero_desktop_image": "church_exterior.jpg.jpg",
    "hero_mobile_image": "mobile_version.jpeg",
}

DEFAULT_ABOUT_CONTENT = {
    "image": "about.jpg.jpeg",
    "title": "About Piravom Valiyapalli",
    "paragraphs": [
        "Piravom Valiyapalli – St. Mary's Orthodox Syrian Cathedral stands as a testament to centuries of unwavering faith and rich Christian heritage in Kerala. Founded around the 6th century, this historic pilgrimage center is one of the most prominent Syrian Christian churches in the region.",
        "Perched majestically on a hill near the Muvattupuzha River, approximately 35 kilometers from Kochi, the cathedral serves as a spiritual beacon for thousands of devotees. As a vital part of the Malankara Orthodox Syrian Church, it continues to preserve ancient traditions while embracing the spiritual needs of contemporary believers.",
        "The church's significance extends beyond its architectural beauty; it represents the enduring legacy of Syrian Christianity in India and serves as a bridge between ancient apostolic traditions and modern spiritual practice.",
    ],
}

DEFAULT_HISTORY_CONTENT = {
    "history_title": "HISTORY",
    "history_text": "PIRAVOM VALIYA PALLY which is one of the most ancient and prominent church in Kerala stands on a lovely hilltop on the eastern bank of the Muvattupuzha river at Piravom, 35 Kms east of Kochi. Adorned with all the majestic beauty of nature, this Church is believed to be as old as the Christianity. Its lamp, the light of hope, is kept burning perpetually throughout day and night, a peculiar feature! Though the Church is named after St. Mary, it is popularly known as the 'Church of the Kings' (“Rajakkalude Pally”). People from various parts of the country irrespective of caste, creed and religion reach this pilgrim centre for consolation and comfort with offerings to their ‘Kings’ who never refuse the prayers and tears of the devotees. This pilgrim centre stands as a fort of refuge, showering blessings, ecstasy, complacence and solace to millions of people far and near. The church has been invariably known as Piravom Valiyapally, Morth Mariyam Pally, Rajakkalude Pally, St.Mary’s Jacobite Syrian Chathedral etc.. As legends say, it is the first Christian church in the world, and it is the only church in the name of the Holy Kings (MAGI) which stands on the solid rock of Christian faith. It is one among the rare churches in Malankara where there has been daily Holy Mass from very olden times. There is the \"Vishudha Moonninmel Qurbono\" (The Holy Mass offered jointly by three priests) almost daily and there are two Holy Masses one after the other on Sundays. Pilgrims from far and near come to pray for consolation and comfort. Many parishioners come daily in the afternoon to pray and they light candles in the church and at the tombs of their forefathers in the graveyard, which is another significance of this church among the Churches in Malankara. This church remains loyal to the Patriarch of Antioch, seated on the Holy Apostolic throne of St. Peter.",
    "old_history_title": "Old History",
    "old_history_text": "About 2000 years ago, \"…after the birth of Jesus Christ in Bethlehem of Judaea, in the days of king Herod the \"Wisemen\" from the east (The Magi) reached Bethlehem through Jerusalem. The \"star\" they saw in the east was moving to direct them till they reached the birthplace of Infant Jesus… They saw the young child on the lap of mother Mary, knelt down and worshipped him. They opened their treasures and presented gifts to him: Gold, Frankincense, and Myrrh (St. Mathew 2:1-11) And they returned with exceeding joy and satisfaction to their home land in the east. The Wisemen (Holy kings) were scholars, rulers and devotees. The legends name them as Melchior, Gaspar and Balthazar. Old Melchior, middle aged Gaspar and young Belthazar visited Infant Jesus. When they reached back their homeland, they built an edifice in the Indian style and here they began to worship the Holy infant. As such Piravom Valiyapally is the first church in the world, where worshipping Jesus Christ started. During the 5th Century, this building may have been rebuilt as a Christian church as we now see. Evidences are many which goes to prove this traditional faith. The commercial connection of Kerala with the western countries and the astrological competence of Kerala are only some. The westerners were visiting Kerala for the business of spices. The major part of the gift presented by the Holy Kings was spices. The Holy Book says that the wise men came from the East. Aryabhata, Vararuchi and Sankaranarayana are examples for the fact that Kerala has been famous for astronomy since olden times. Widely famous astrological centre, the ‘Pazhoor Padippura’ very near to this church is also an evidence to reach to this conclusion. \"The place-name Piravom itself is related to 'piravi' (Birth)\". Many people are of such opinions. It is seen in the History of St.Thomas (Page. 15; Suriyani Sabha, Kaniyanparambil Kurian Corepiscopa) that the ‘Megusans’ (MAGI), who made offerings to Infant Jesus had been sanctified as Christians in India by St.Thomas, when he was in missionary works in Kerala. It is believed that, in the beginning, this church building was in the architectural style of Hindu Temples. But later during the flourishing of the Persian culture, the church building was renovated adopting the Persian architecture. The picture of fish, an ancient Christian emblem has a venerable place in the church. The Church was built as a strong fort; having been built in the periods of \"Padayottam\" (civil wars and banditry) its walls are more than four feet in thickness.",
    "images": [
        "gallery/church_exterior.jpg.jpg",
        "gallery/church_night.jpg.jpg",
        "about.jpg.jpeg",
        "gallery/649334100_1337804095050528_5143294464664934259_n.jpg",
    ],
}

DEFAULT_EVENTS_CONTENT = {
    "events": [
        {"date": "January 1 – 6", "event": "Danaha Perunal", "description": "Join us for this sacred celebration at Piravom Valiyapalli.", "image": "danaha.jpeg"},
        {"date": "March 15 – 19", "event": "Convention", "description": "Join us for this sacred celebration at Piravom Valiyapalli.", "image": "convention.jpeg"},
        {"date": "March 25", "event": "Vachanipp Perunall", "description": "Join us for this sacred celebration at Piravom Valiyapalli.", "image": "vachanipp.jpeg"},
        {"date": "March 29", "event": "Oshana", "description": "Join us for this sacred celebration at Piravom Valiyapalli.", "image": "oshana.jpeg"},
        {"date": "April 2", "event": "Pesaha Vyazham", "description": "Join us for this sacred celebration at Piravom Valiyapalli.", "image": "pesaha.jpg"},
        {"date": "April 3", "event": "Good Friday", "description": "Join us for this sacred celebration at Piravom Valiyapalli.", "image": "friday.jpeg"},
        {"date": "April 4", "event": "Holy Saturday", "description": "Join us for this sacred celebration at Piravom Valiyapalli.", "image": "saturday.jpg"},
        {"date": "April 5", "event": "Easter", "description": "Join us for this sacred celebration at Piravom Valiyapalli.", "image": "easter.jpg"},
        {"date": "April 5", "event": "Paithel Nercha", "description": "Join us for this sacred celebration at Piravom Valiyapalli.", "image": "nercha.jpeg"},
        {"date": "April 19", "event": "Paithel Vechoot Nercha", "description": "Join us for this sacred celebration at Piravom Valiyapalli.", "image": "paithel.jpeg"},
        {"date": "May 6 – 7", "event": "Vishudha Geevarghese Sahadayude Perunal", "description": "Join us for this sacred celebration at Piravom Valiyapalli.", "image": "geevarghese.jpeg"},
        {"date": "June 29", "event": "Sleeha Perunal", "description": "Join us for this sacred celebration at Piravom Valiyapalli.", "image": "sleeha.jpeg"},
        {"date": "August 14 – 15", "event": "Vishudha Maadhavinte Vaagippu Perunal", "description": "Join us for this sacred celebration at Piravom Valiyapalli.", "image": "maadhavu.jpeg"},
        {"date": "October 7 – 8", "event": "Kallitta Perunal", "description": "Join us for this sacred celebration at Piravom Valiyapalli.", "image": "kallitta.jpeg"},
        {"date": "December 25", "event": "Christmas", "description": "Join us for this sacred celebration at Piravom Valiyapalli.", "image": "christmas.jpeg"},
    ]
}

DEFAULT_PRIESTS_CONTENT = {
    "priests": [
        {"name": "Fr. Benoy John", "phone": "+91 94953 14833", "image": "benoy.jpeg", "is_vicar": False},
        {"name": "Fr. Elias Cherukattu", "phone": "+91 9447820111", "image": "elias.jpeg", "is_vicar": True},
        {"name": "Fr. Babu Abraham", "phone": "+91 96455 94306", "image": "babu.jpeg", "is_vicar": False},
    ]
}

DEFAULT_HKMEDIA_CONTENT = {
    "logo": "hkmedia.jpeg",
    "description": "HK Media is the dedicated media and communications team of Piravom Valiyapalli, committed to delivering high-quality digital coverage for all church events and activities. As the official media wing of Holy Kings Media, the team specializes in live streaming, event documentation, photography, videography, and content production, ensuring that every significant moment is captured and shared with clarity and professionalism. With a strong focus on technical excellence and visual storytelling, HK Media plays a vital role in connecting the church community both locally and globally, maintaining a consistent and engaging digital presence across platforms.",
    "contacts": ["9446965149", "99955 59133", "8714746599"],
}

DEFAULT_LIVE_SCHEDULE = {
    "items": [
        {"time": "6:30 AM", "title": "Morning Qurbana", "notes": ""},
        {"time": "6:00 PM", "title": "Evening Prayer", "notes": ""},
        {"time": "8:00 AM", "title": "Sunday Special Qurbana", "notes": "Sunday"},
    ]
}


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
    if not HOMEPAGE_CONTENT_PATH.exists():
        HOMEPAGE_CONTENT_PATH.write_text(json.dumps(DEFAULT_HOMEPAGE_CONTENT, ensure_ascii=False, indent=2), encoding="utf-8")
    if not ABOUT_CONTENT_PATH.exists():
        ABOUT_CONTENT_PATH.write_text(json.dumps(DEFAULT_ABOUT_CONTENT, ensure_ascii=False, indent=2), encoding="utf-8")
    if not HISTORY_CONTENT_PATH.exists():
        HISTORY_CONTENT_PATH.write_text(json.dumps(DEFAULT_HISTORY_CONTENT, ensure_ascii=False, indent=2), encoding="utf-8")
    if not EVENTS_CONTENT_PATH.exists():
        EVENTS_CONTENT_PATH.write_text(json.dumps(DEFAULT_EVENTS_CONTENT, ensure_ascii=False, indent=2), encoding="utf-8")
    if not PRIESTS_CONTENT_PATH.exists():
        PRIESTS_CONTENT_PATH.write_text(json.dumps(DEFAULT_PRIESTS_CONTENT, ensure_ascii=False, indent=2), encoding="utf-8")
    if not HKMEDIA_CONTENT_PATH.exists():
        HKMEDIA_CONTENT_PATH.write_text(json.dumps(DEFAULT_HKMEDIA_CONTENT, ensure_ascii=False, indent=2), encoding="utf-8")
    if not LIVE_SCHEDULE_PATH.exists():
        LIVE_SCHEDULE_PATH.write_text(json.dumps(DEFAULT_LIVE_SCHEDULE, ensure_ascii=False, indent=2), encoding="utf-8")

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


def _sign_session(*parts) -> str:
    msg = "|".join(str(p) for p in parts).encode("utf-8")
    return hmac.new(_SESSION_HMAC_SECRET_BYTES, msg, hashlib.sha256).hexdigest()


def _role_for_username(username: str) -> str:
    return _ADMIN_ROLES.get((username or "").strip(), "limited_admin")


def _make_session_cookie_value(username="", role="", ts_int=None) -> str:
    if ts_int is None:
        ts_int = int(time.time())
    nonce = secrets.token_urlsafe(16)
    if username and role:
        u_enc = urllib.parse.quote((username or "").strip(), safe="")
        r_enc = urllib.parse.quote((role or "").strip(), safe="")
        sig = _sign_session(nonce, int(ts_int), u_enc, r_enc)
        return f"{nonce}.{int(ts_int)}.{u_enc}.{r_enc}.{sig}"
    sig = _sign_session(nonce, int(ts_int))
    return f"{nonce}.{int(ts_int)}.{sig}"


def get_session_user():
    value = request.cookies.get(SESSION_COOKIE)
    if not value:
        return None
    parts = value.split(".")
    if len(parts) not in (3, 5):
        return None
    nonce = parts[0]
    ts_s = parts[1]
    try:
        ts_int = int(ts_s)
    except Exception:
        return None
    if time.time() - ts_int > SESSION_TTL_SECONDS:
        return None

    # Backward-compat for older cookies without role claims.
    if len(parts) == 3:
        sig = parts[2]
        expected = _sign_session(nonce, ts_int)
        if not hmac.compare_digest(expected, sig):
            return None
        return {"username": "legacy", "role": "super_admin", "ts": ts_int}

    u_enc = parts[2]
    r_enc = parts[3]
    sig = parts[4]
    expected = _sign_session(nonce, ts_int, u_enc, r_enc)
    if not hmac.compare_digest(expected, sig):
        return None
    username = urllib.parse.unquote(u_enc).strip()
    role = urllib.parse.unquote(r_enc).strip()
    if role not in ("super_admin", "limited_admin"):
        return None
    return {"username": username, "role": role, "ts": ts_int}


def is_logged_in() -> bool:
    return bool(get_session_user())


def require_roles(*allowed_roles):
    if not is_logged_in():
        return False, json_response(401, {"error": "unauthorized"})
    if not allowed_roles:
        return True, None
    session_user = get_session_user() or {}
    role = (session_user.get("role") or "").strip()
    if role not in allowed_roles:
        return False, json_response(403, {"error": "forbidden"})
    return True, None


def require_jobin_super_admin():
    ok, resp = require_roles("super_admin")
    if not ok:
        return False, resp
    session_user = get_session_user() or {}
    if (session_user.get("username") or "").strip() != "jobin":
        return False, json_response(403, {"error": "forbidden"})
    return True, None


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
    ok, resp = require_roles("super_admin")
    if not ok:
        return resp
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
    ok, resp = require_roles("super_admin")
    if not ok:
        return resp
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
    ok, resp = require_roles("super_admin", "limited_admin")
    if not ok:
        return resp

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
    ok, resp = require_roles("super_admin", "limited_admin")
    if not ok:
        return resp

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
    ok, resp = require_roles("super_admin")
    if not ok:
        return resp

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
    ok, resp = require_roles("super_admin")
    if not ok:
        return resp

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
    ok, resp = require_roles("super_admin")
    if not ok:
        return resp

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


def _clean_text(val, max_len=20000):
    s = str(val or "").strip()
    if len(s) > max_len:
        s = s[:max_len]
    return s


def _clean_image_ref(val):
    s = _clean_text(val, 255)
    if not s:
        return ""
    if "/" in s:
        parts = [sanitize_filename(p) for p in s.split("/") if p]
        if not parts:
            return ""
        return "/".join(parts)
    return sanitize_filename(s)


def _normalize_asset_ref(ref):
    """
    Normalize to a safe path relative to /assets (no leading assets/).
    Example inputs:
      "assets/gallery/a.jpg" -> "gallery/a.jpg"
      "gallery/a.jpg" -> "gallery/a.jpg"
      "a.jpg" -> "a.jpg"
    """
    raw = _clean_text(ref, 512).replace("\\", "/").strip("/")
    if raw.lower().startswith("assets/"):
        raw = raw[7:]
    if not raw:
        return ""
    parts = [sanitize_filename(p) for p in raw.split("/") if p]
    if not parts:
        return ""
    return "/".join(parts)


def _asset_ref_to_path(ref):
    safe_ref = _normalize_asset_ref(ref)
    if not safe_ref:
        return "", None
    assets_root = (ROOT_DIR / "assets").resolve()
    target = (assets_root / safe_ref).resolve()
    if assets_root not in target.parents and target != assets_root:
        return "", None
    return safe_ref, target


def _read_json_with_default(path: Path, default_payload):
    data = read_json_file(path)
    if not isinstance(data, dict):
        return dict(default_payload)
    merged = dict(default_payload)
    merged.update(data)
    return merged


@app.route("/api/homepage-content", methods=["GET"])
def api_get_homepage_content():
    data = _read_json_with_default(HOMEPAGE_CONTENT_PATH, DEFAULT_HOMEPAGE_CONTENT)
    return json_response(200, data)


@app.route("/api/homepage-content", methods=["PUT"])
def api_put_homepage_content():
    ok, resp = require_roles("super_admin")
    if not ok:
        return resp
    body = request.get_json(silent=True) or {}
    payload = {
        "hero_desktop_image": _clean_image_ref(body.get("hero_desktop_image")),
        "hero_mobile_image": _clean_image_ref(body.get("hero_mobile_image")),
    }
    with _lock_for_path(HOMEPAGE_CONTENT_PATH):
        write_json_file(HOMEPAGE_CONTENT_PATH, payload)
    return json_response(200, {"ok": True})


@app.route("/api/about-content", methods=["GET"])
def api_get_about_content():
    data = _read_json_with_default(ABOUT_CONTENT_PATH, DEFAULT_ABOUT_CONTENT)
    return json_response(200, data)


@app.route("/api/about-content", methods=["PUT"])
def api_put_about_content():
    ok, resp = require_roles("super_admin")
    if not ok:
        return resp
    body = request.get_json(silent=True) or {}
    paragraphs = body.get("paragraphs", [])
    clean_paragraphs = []
    if isinstance(paragraphs, list):
        for p in paragraphs:
            t = _clean_text(p, 5000)
            if t:
                clean_paragraphs.append(t)
    payload = {
        "image": _clean_image_ref(body.get("image")),
        "title": _clean_text(body.get("title"), 200),
        "paragraphs": clean_paragraphs,
    }
    with _lock_for_path(ABOUT_CONTENT_PATH):
        write_json_file(ABOUT_CONTENT_PATH, payload)
    return json_response(200, {"ok": True})


@app.route("/api/history-content", methods=["GET"])
def api_get_history_content():
    data = _read_json_with_default(HISTORY_CONTENT_PATH, DEFAULT_HISTORY_CONTENT)
    return json_response(200, data)


@app.route("/api/history-content", methods=["PUT"])
def api_put_history_content():
    ok, resp = require_roles("super_admin")
    if not ok:
        return resp
    body = request.get_json(silent=True) or {}
    images = body.get("images", [])
    clean_images = []
    if isinstance(images, list):
        for img in images:
            ref = _clean_image_ref(img)
            if ref:
                clean_images.append(ref)
    payload = {
        "history_title": _clean_text(body.get("history_title"), 120),
        "history_text": _clean_text(body.get("history_text"), 30000),
        "old_history_title": _clean_text(body.get("old_history_title"), 120),
        "old_history_text": _clean_text(body.get("old_history_text"), 30000),
        "images": clean_images[:12],
    }
    with _lock_for_path(HISTORY_CONTENT_PATH):
        write_json_file(HISTORY_CONTENT_PATH, payload)
    return json_response(200, {"ok": True})


@app.route("/api/events", methods=["GET"])
def api_get_events():
    data = _read_json_with_default(EVENTS_CONTENT_PATH, DEFAULT_EVENTS_CONTENT)
    events = data.get("events", [])
    if not isinstance(events, list):
        events = []
    return json_response(200, {"events": events})


@app.route("/api/events", methods=["PUT"])
def api_put_events():
    ok, resp = require_roles("super_admin")
    if not ok:
        return resp
    body = request.get_json(silent=True) or {}
    rows = body.get("events", [])
    clean_rows = []
    if isinstance(rows, list):
        for row in rows:
            if not isinstance(row, dict):
                continue
            clean_rows.append(
                {
                    "date": _clean_text(row.get("date"), 80),
                    "event": _clean_text(row.get("event"), 200),
                    "description": _clean_text(row.get("description"), 1000),
                    "image": _clean_image_ref(row.get("image")),
                }
            )
    with _lock_for_path(EVENTS_CONTENT_PATH):
        write_json_file(EVENTS_CONTENT_PATH, {"events": clean_rows})
    return json_response(200, {"ok": True})


@app.route("/api/priests", methods=["GET"])
def api_get_priests():
    data = _read_json_with_default(PRIESTS_CONTENT_PATH, DEFAULT_PRIESTS_CONTENT)
    priests = data.get("priests", [])
    if not isinstance(priests, list):
        priests = []
    return json_response(200, {"priests": priests})


@app.route("/api/priests", methods=["PUT"])
def api_put_priests():
    ok, resp = require_roles("super_admin")
    if not ok:
        return resp
    body = request.get_json(silent=True) or {}
    rows = body.get("priests", [])
    clean_rows = []
    vicar_seen = False
    if isinstance(rows, list):
        for row in rows:
            if not isinstance(row, dict):
                continue
            is_vicar = bool(row.get("is_vicar"))
            if is_vicar:
                if vicar_seen:
                    is_vicar = False
                else:
                    vicar_seen = True
            clean_rows.append(
                {
                    "name": _clean_text(row.get("name"), 200),
                    "phone": _clean_text(row.get("phone"), 80),
                    "image": _clean_image_ref(row.get("image")),
                    "is_vicar": is_vicar,
                }
            )
    if clean_rows and not any(bool(p.get("is_vicar")) for p in clean_rows):
        clean_rows[0]["is_vicar"] = True
    with _lock_for_path(PRIESTS_CONTENT_PATH):
        write_json_file(PRIESTS_CONTENT_PATH, {"priests": clean_rows})
    return json_response(200, {"ok": True})


@app.route("/api/hkmedia-content", methods=["GET"])
def api_get_hkmedia_content():
    data = _read_json_with_default(HKMEDIA_CONTENT_PATH, DEFAULT_HKMEDIA_CONTENT)
    return json_response(200, data)


@app.route("/api/hkmedia-content", methods=["PUT"])
def api_put_hkmedia_content():
    ok, resp = require_roles("super_admin")
    if not ok:
        return resp
    body = request.get_json(silent=True) or {}
    contacts = body.get("contacts", [])
    clean_contacts = []
    if isinstance(contacts, list):
        for c in contacts:
            t = _clean_text(c, 80)
            if t:
                clean_contacts.append(t)
    payload = {
        "logo": _clean_image_ref(body.get("logo")),
        "description": _clean_text(body.get("description"), 12000),
        "contacts": clean_contacts[:10],
    }
    with _lock_for_path(HKMEDIA_CONTENT_PATH):
        write_json_file(HKMEDIA_CONTENT_PATH, payload)
    return json_response(200, {"ok": True})


@app.route("/api/live-schedule", methods=["GET"])
def api_get_live_schedule():
    data = _read_json_with_default(LIVE_SCHEDULE_PATH, DEFAULT_LIVE_SCHEDULE)
    items = data.get("items", [])
    if not isinstance(items, list):
        items = []
    return json_response(200, {"items": items})


@app.route("/api/live-schedule", methods=["PUT"])
def api_put_live_schedule():
    ok, resp = require_roles("super_admin", "limited_admin")
    if not ok:
        return resp
    body = request.get_json(silent=True) or {}
    rows = body.get("items", [])
    clean_rows = []
    if isinstance(rows, list):
        for row in rows:
            if not isinstance(row, dict):
                continue
            clean_rows.append(
                {
                    "time": _clean_text(row.get("time"), 80),
                    "title": _clean_text(row.get("title"), 200),
                    "notes": _clean_text(row.get("notes"), 400),
                }
            )
    with _lock_for_path(LIVE_SCHEDULE_PATH):
        write_json_file(LIVE_SCHEDULE_PATH, {"items": clean_rows})
    return json_response(200, {"ok": True})


@app.route("/api/super-admin/replace-image", methods=["POST"])
def api_super_admin_replace_image():
    ok, resp = require_jobin_super_admin()
    if not ok:
        return resp

    if "image" not in request.files:
        return json_response(400, {"error": "no_file"})

    f = request.files.get("image")
    if not f:
        return json_response(400, {"error": "no_file"})

    file_bytes = f.read() or b""
    max_file_bytes = int(os.environ.get("MAX_FILE_BYTES", str(_DEFAULT_MAX_FILE)))
    if len(file_bytes) > max_file_bytes:
        return json_response(400, {"error": "file_too_large"})

    original_name = sanitize_filename(f.filename or "")
    suffix = Path(original_name).suffix.lower()
    if suffix not in [".jpg", ".jpeg", ".png", ".gif", ".webp"]:
        return json_response(400, {"error": "unsupported_image_type"})

    replace_ref = request.form.get("replace_ref", "")
    replace_ref = _normalize_asset_ref(replace_ref)
    target_dir = _clean_text(request.form.get("target_dir", ""), 120).replace("\\", "/").strip("/")
    target_dir = _normalize_asset_ref(target_dir)

    if replace_ref:
        final_ref = replace_ref
    else:
        if target_dir:
            final_ref = f"{target_dir}/{original_name}"
        else:
            final_ref = original_name

    safe_ref, out_path = _asset_ref_to_path(final_ref)
    if not safe_ref or out_path is None:
        return json_response(400, {"error": "invalid_target"})

    with _lock_for_path(ASSET_FS_LOCK_PATH):
        out_path.parent.mkdir(parents=True, exist_ok=True)
        # Replace existing file in-place. This keeps references stable
        # and avoids creating duplicate orphan files for jobin workflows.
        out_path.write_bytes(file_bytes)

    return json_response(200, {"ok": True, "ref": safe_ref})


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
    ok, resp = require_roles("super_admin", "limited_admin")
    if not ok:
        return resp
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

    if _is_valid_admin_login(username, password):
        role = _role_for_username(username)
        token_value = _make_session_cookie_value(username=username, role=role)
        resp = json_response(200, {"ok": True, "username": username, "role": role})
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


@app.route("/api/me", methods=["GET"])
def api_me():
    session_user = get_session_user()
    if not session_user:
        return json_response(401, {"error": "unauthorized"})
    return json_response(
        200,
        {
            "ok": True,
            "username": session_user.get("username", ""),
            "role": session_user.get("role", ""),
        },
    )


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

