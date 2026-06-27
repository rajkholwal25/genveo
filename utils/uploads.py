"""Save and remove profile gallery photos.

Photos are uploaded to the Supabase Storage bucket ``profile`` and the public
URL is stored on the ProfilePhoto row. If Storage is unreachable/unconfigured
we fall back to saving under ``static/uploads`` so the app still works offline.
"""
import mimetypes
import os
import secrets
import urllib.request

from werkzeug.utils import secure_filename

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif"}
ICON_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif", "svg"}
MAX_PHOTOS = 6
BUCKET = "profile"
ICON_BUCKET = "icons"


def _allowed(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def _prepare_image(data: bytes, max_dim: int):
    """Downscale + recompress so uploads stay small and within bucket limits.

    Returns (data, content_type, ext). Falls back to the original bytes if
    Pillow is unavailable or the image can't be processed.
    """
    try:
        import io

        from PIL import Image, ImageOps

        im = Image.open(io.BytesIO(data))
        im = ImageOps.exif_transpose(im)  # respect phone orientation
        im.thumbnail((max_dim, max_dim))

        out = io.BytesIO()
        if im.mode in ("RGBA", "LA", "P"):
            im = im.convert("RGBA")
            im.save(out, "PNG", optimize=True)
            return out.getvalue(), "image/png", "png"
        im = im.convert("RGB")
        im.save(out, "JPEG", quality=85, optimize=True)
        return out.getvalue(), "image/jpeg", "jpg"
    except Exception as exc:  # noqa: BLE001 — keep original on any failure
        print(f"[image] processing skipped: {str(exc)[:120]}")
        return None


def _upload_dir() -> str:
    from flask import current_app

    path = current_app.config["UPLOAD_FOLDER"]
    os.makedirs(path, exist_ok=True)
    return path


def _storage_cfg():
    url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    key = os.environ.get("SUPABASE_SECRET_KEY") or os.environ.get("SUPABASE_KEY", "")
    return url, key


def _public_url(url: str, object_path: str, bucket: str = BUCKET) -> str:
    return f"{url}/storage/v1/object/public/{bucket}/{object_path}"


def _storage_upload(data: bytes, object_path: str, content_type: str, bucket: str = BUCKET):
    """Upload bytes to a Supabase Storage bucket; return public URL or None."""
    url, key = _storage_cfg()
    if not url or not key:
        return None

    endpoint = f"{url}/storage/v1/object/{bucket}/{object_path}"
    req = urllib.request.Request(endpoint, data=data, method="POST")
    req.add_header("Authorization", f"Bearer {key}")
    req.add_header("apikey", key)
    req.add_header("Content-Type", content_type)
    req.add_header("x-upsert", "true")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            if resp.status in (200, 201):
                return _public_url(url, object_path, bucket)
            print(f"[storage] upload HTTP {resp.status}")
    except Exception as exc:  # noqa: BLE001 — log and fall back to local
        print(f"[storage] upload failed: {str(exc)[:160]}")
    return None


def _storage_delete(stored_url: str) -> None:
    url, key = _storage_cfg()
    marker = "/object/public/"
    if not url or not key or marker not in stored_url:
        return
    # stored_url = {url}/storage/v1/object/public/{bucket}/{object_path}
    tail = stored_url.split(marker, 1)[1]
    bucket, _, object_path = tail.partition("/")
    endpoint = f"{url}/storage/v1/object/{bucket}/{object_path}"
    req = urllib.request.Request(endpoint, method="DELETE")
    req.add_header("Authorization", f"Bearer {key}")
    req.add_header("apikey", key)
    try:
        urllib.request.urlopen(req, timeout=20)
    except Exception as exc:  # noqa: BLE001
        print(f"[storage] delete failed: {str(exc)[:160]}")


def upload_icon(file):
    """Upload a category icon image to the icons bucket. Returns public URL or None."""
    if not file or not file.filename:
        return None
    if "." not in file.filename or file.filename.rsplit(".", 1)[1].lower() not in ICON_EXTENSIONS:
        return None
    ext = file.filename.rsplit(".", 1)[1].lower()
    data = file.read()
    if not data:
        return None
    ctype = file.mimetype or mimetypes.guess_type(file.filename)[0] or "image/png"
    object_path = f"{secrets.token_hex(8)}.{ext}"
    return _storage_upload(data, object_path, ctype, bucket=ICON_BUCKET)


def delete_icon(stored_url: str) -> None:
    if stored_url and stored_url.startswith("http"):
        _storage_delete(stored_url)


def save_photos(files, owner_type: str, owner_id: int) -> int:
    """Save uploaded files as ProfilePhoto rows. Returns the number saved.

    Respects MAX_PHOTOS across the owner's existing gallery.
    """
    from extensions import db
    from models import ProfilePhoto

    existing = ProfilePhoto.query.filter_by(owner_type=owner_type, owner_id=owner_id).count()
    slots = MAX_PHOTOS - existing
    saved = 0

    for file in files:
        if slots <= 0:
            break
        if not file or not file.filename or not _allowed(file.filename):
            continue

        ext = file.filename.rsplit(".", 1)[1].lower()
        data = file.read()
        if not data:
            continue
        content_type = file.mimetype or mimetypes.guess_type(file.filename)[0] or "image/jpeg"
        prepared = _prepare_image(data, 1280)
        if prepared:
            data, content_type, ext = prepared
        object_path = f"{owner_type}/{owner_id}/{secrets.token_hex(8)}.{ext}"

        stored = _storage_upload(data, object_path, content_type)
        if not stored:
            # offline fallback: write to static/uploads
            local = secure_filename(f"{owner_type}_{owner_id}_{secrets.token_hex(8)}.{ext}")
            with open(os.path.join(_upload_dir(), local), "wb") as fh:
                fh.write(data)
            stored = local

        db.session.add(
            ProfilePhoto(owner_type=owner_type, owner_id=owner_id, filename=stored)
        )
        saved += 1
        slots -= 1

    if saved:
        db.session.commit()
    return saved


def save_avatar(file, owner_type: str, owner_id: int, old_url: str | None = None):
    """Upload a single profile picture; return its src (URL or static path) or None.

    Deletes the previous avatar when a new one is saved.
    """
    if not file or not file.filename or not _allowed(file.filename):
        return None
    ext = file.filename.rsplit(".", 1)[1].lower()
    data = file.read()
    if not data:
        return None
    ctype = file.mimetype or mimetypes.guess_type(file.filename)[0] or "image/jpeg"
    prepared = _prepare_image(data, 600)
    if prepared:
        data, ctype, ext = prepared
    object_path = f"avatars/{owner_type}_{owner_id}_{secrets.token_hex(6)}.{ext}"

    stored = _storage_upload(data, object_path, ctype, bucket=BUCKET)
    if not stored:
        from flask import url_for

        local = secure_filename(f"avatar_{owner_type}_{owner_id}_{secrets.token_hex(6)}.{ext}")
        with open(os.path.join(_upload_dir(), local), "wb") as fh:
            fh.write(data)
        stored = url_for("static", filename=f"uploads/{local}")

    if stored and old_url and old_url.startswith("http"):
        _storage_delete(old_url)
    return stored


def delete_photo(photo_id: int, owner_type: str, owner_id: int) -> bool:
    """Delete one photo the caller owns. Returns True if removed."""
    from extensions import db
    from models import ProfilePhoto

    photo = ProfilePhoto.query.filter_by(
        id=photo_id, owner_type=owner_type, owner_id=owner_id
    ).first()
    if not photo:
        return False

    if photo.filename.startswith("http"):
        _storage_delete(photo.filename)
    else:
        try:
            os.remove(os.path.join(_upload_dir(), photo.filename))
        except OSError:
            pass

    db.session.delete(photo)
    db.session.commit()
    return True
