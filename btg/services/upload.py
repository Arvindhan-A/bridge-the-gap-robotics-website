import os
import uuid
from PIL import Image
from io import BytesIO

from btg.config import Config

MAGIC_BYTES = {
    b'\xff\xd8\xff': 'jpg',
    b'\x89PNG\r\n\x1a\n': 'png',
    b'GIF87a': 'gif',
    b'GIF89a': 'gif',
    b'RIFF': 'webp',
}

MAX_FILE_SIZE = 4 * 1024 * 1024
ALLOWED_EXTS = {'jpg', 'jpeg', 'png', 'gif', 'webp'}


def _detect_ext(data):
    for sig, ext in MAGIC_BYTES.items():
        if data[:len(sig)] == sig:
            return ext
    return None


def validate_upload(file):
    if not file or not file.filename:
        return None, 'No file provided.'

    if file.content_length and file.content_length > MAX_FILE_SIZE:
        return None, 'File exceeds 4 MB limit.'

    raw = file.read(MAX_FILE_SIZE + 1)
    file.seek(0)

    if len(raw) < 16:
        return None, 'File too small or empty.'

    if len(raw) > MAX_FILE_SIZE:
        return None, 'File exceeds 4 MB limit.'

    ext = _detect_ext(raw[:16])
    if not ext:
        return None, 'Invalid file type. Only JPEG, PNG, GIF, WebP allowed.'

    _, user_ext = os.path.splitext(file.filename)
    user_ext = user_ext.lower().lstrip('.')
    if user_ext not in ALLOWED_EXTS:
        return None, f'Extension .{user_ext} not allowed.'

    return ext, raw


def strip_exif(raw, ext):
    try:
        img = Image.open(BytesIO(raw))
        if img.mode in ('RGBA', 'LA', 'P'):
            img = img.convert('RGB')
        out = BytesIO()
        save_fmt = 'JPEG' if ext == 'jpg' else ext.upper()
        img.save(out, format=save_fmt)
        out.seek(0)
        return out.read()
    except Exception:
        return raw


def save_upload(file, subfolder=''):
    ext, raw_or_err = validate_upload(file)
    if isinstance(raw_or_err, str):
        return ''

    safe = strip_exif(raw_or_err, ext)

    filename = f'{uuid.uuid4().hex}.{ext}'
    sub_path = os.path.join(Config.UPLOAD_FOLDER, subfolder)
    os.makedirs(sub_path, exist_ok=True)
    dest = os.path.join(sub_path, filename)

    with open(dest, 'wb') as f:
        f.write(safe)

    return f'uploads/{subfolder}/{filename}'


def delete_upload(path):
    if not path:
        return
    static_dir = os.path.dirname(Config.UPLOAD_FOLDER)
    full = os.path.normpath(os.path.join(static_dir, path))
    uploads_dir = os.path.normpath(Config.UPLOAD_FOLDER)
    if full.startswith(uploads_dir) and os.path.isfile(full):
        os.remove(full)
