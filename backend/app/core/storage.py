from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException, UploadFile, status

UPLOAD_ROOT = Path(__file__).resolve().parent.parent / 'storage' / 'uploads'
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
ALLOWED_IMAGE_TYPES = {'image/jpeg', 'image/jpg', 'image/pjpeg', 'image/png', 'image/webp'}


def ensure_upload_root() -> Path:
    UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
    return UPLOAD_ROOT


def save_upload_file(file: UploadFile, inspection_id: str) -> tuple[str, str]:
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Only JPEG, PNG and WEBP images are allowed.')

    if file.size is not None and file.size > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Image size exceeds the 10MB development limit.')

    file_bytes = file.file.read()
    if len(file_bytes) == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Empty file uploaded.')

    if file.content_type == 'image/png' and file_bytes[:8] != b'\x89PNG\r\n\x1a\n':
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Uploaded file is not a valid PNG image.')
    if file.content_type in ('image/jpeg', 'image/jpg', 'image/pjpeg') and file_bytes[:2] != b'\xff\xd8':
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Uploaded file is not a valid JPEG image.')
    if file.content_type == 'image/webp' and not file_bytes[:4] == b'RIFF':
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Uploaded file is not a valid WEBP image.')

    target_dir = ensure_upload_root() / inspection_id
    target_dir.mkdir(parents=True, exist_ok=True)

    import re

    raw_name = Path(file.filename or 'uploaded-image').name
    cleaned_name = re.sub(r'[^a-zA-Z0-9_.-]', '_', raw_name).strip('._')
    safe_name = cleaned_name if cleaned_name else 'uploaded-image'
    if '.' not in safe_name:
        ext = '.png' if file.content_type == 'image/png' else ('.webp' if file.content_type == 'image/webp' else '.jpg')
        safe_name += ext

    final_path = (target_dir / safe_name).resolve()
    target_dir_resolved = target_dir.resolve()
    if not final_path.is_relative_to(target_dir_resolved):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Invalid filename. Path traversal prohibited.')

    counter = 1
    while final_path.exists():
        new_name = f'{Path(safe_name).stem}_{counter}{Path(safe_name).suffix}'
        final_path = (target_dir / new_name).resolve()
        counter += 1

    final_path.write_bytes(file_bytes)
    relative_path = str(final_path.relative_to(Path(__file__).resolve().parent.parent)).replace('\\', '/')
    return str(final_path), relative_path
