"""
Local File Storage Service
Handles file uploads, downloads, and management for task attachments.
Files are stored on the local filesystem under static/uploads/.

Note: This replaces the previous Supabase Storage integration.
For production (AWS), consider upgrading to Amazon S3 storage.
"""

import os
import shutil
import mimetypes
import time
import hashlib
import logging
from typing import Optional, List

logger = logging.getLogger(__name__)

# Base upload dir — relative to project root
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), '..', 'static', 'uploads')

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf', 'json', 'csv', 'txt'}
ALLOWED_MIME_TYPES = {
    'image/png', 'image/jpeg', 'image/jpg',
    'application/pdf', 'application/json',
    'text/csv', 'text/plain'
}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB


def _ensure_upload_dir(folder: str = "") -> str:
    """Ensure upload directory exists and return the full path."""
    path = os.path.join(UPLOAD_DIR, folder) if folder else UPLOAD_DIR
    os.makedirs(path, exist_ok=True)
    return path


class StorageService:
    """
    Local filesystem storage service for task attachments.

    Files are stored under:  static/uploads/<folder>/<filename>
    URLs returned as:        /static/uploads/<folder>/<filename>
    """

    MAX_FILE_SIZE = MAX_FILE_SIZE
    ALLOWED_MIME_TYPES = ALLOWED_MIME_TYPES
    ALLOWED_EXTENSIONS = ALLOWED_EXTENSIONS

    @staticmethod
    def validate_file(filename: str, file_size: int = None) -> tuple:
        """
        Validate file type and size.

        Returns:
            (is_valid: bool, error_message: str or None)
        """
        if '.' not in filename:
            return False, "File must have an extension"

        ext = filename.rsplit('.', 1)[1].lower()
        if ext not in StorageService.ALLOWED_EXTENSIONS:
            return False, f"File type .{ext} not allowed. Allowed: {', '.join(StorageService.ALLOWED_EXTENSIONS)}"

        if file_size and file_size > StorageService.MAX_FILE_SIZE:
            size_mb = StorageService.MAX_FILE_SIZE / (1024 * 1024)
            return False, f"File too large. Maximum size: {size_mb:.0f} MB"

        return True, None

    @staticmethod
    def generate_secure_filename(original_filename: str, user_id: int = None) -> str:
        """Generate secure, unique filename with timestamp and hash."""
        timestamp = int(time.time())
        hash_input = f"{user_id or 'anon'}_{timestamp}_{original_filename}"
        file_hash = hashlib.md5(hash_input.encode()).hexdigest()[:8]
        ext = original_filename.rsplit('.', 1)[1] if '.' in original_filename else ''
        if user_id:
            return f"{user_id}_{timestamp}_{file_hash}.{ext}"
        return f"{timestamp}_{file_hash}.{ext}"

    @staticmethod
    def upload_file(file_path: str, file_name: str, folder: str = "") -> dict:
        """
        Upload a file from local path to the uploads directory.

        Returns:
            dict with 'success', 'path', 'url', or 'error'
        """
        try:
            file_size = os.path.getsize(file_path)
            is_valid, error = StorageService.validate_file(file_name, file_size)
            if not is_valid:
                return {'success': False, 'error': error}

            dest_dir = _ensure_upload_dir(folder)
            dest_path = os.path.join(dest_dir, file_name)
            shutil.copy2(file_path, dest_path)

            storage_path = f"{folder}/{file_name}" if folder else file_name
            url = f"/static/uploads/{storage_path}"
            mime_type, _ = mimetypes.guess_type(file_name)

            return {
                'success': True,
                'path': storage_path,
                'url': url,
                'size': file_size,
                'mime_type': mime_type
            }

        except Exception as e:
            logger.error("upload_file error: %s", e)
            return {'success': False, 'error': str(e)}

    @staticmethod
    def upload_from_bytes(file_bytes: bytes, file_name: str, folder: str = "", mime_type: str = None) -> dict:
        """
        Upload file from bytes (for Flask file uploads).

        Returns:
            dict with 'success', 'path', 'url', or 'error'
        """
        try:
            file_size = len(file_bytes)
            is_valid, error = StorageService.validate_file(file_name, file_size)
            if not is_valid:
                return {'success': False, 'error': error}

            if not mime_type:
                mime_type, _ = mimetypes.guess_type(file_name)

            if mime_type and mime_type not in StorageService.ALLOWED_MIME_TYPES:
                return {'success': False, 'error': f"MIME type {mime_type} not allowed"}

            dest_dir = _ensure_upload_dir(folder)
            dest_path = os.path.join(dest_dir, file_name)
            with open(dest_path, 'wb') as f:
                f.write(file_bytes)

            storage_path = f"{folder}/{file_name}" if folder else file_name
            url = f"/static/uploads/{storage_path}"

            return {
                'success': True,
                'path': storage_path,
                'url': url,
                'size': file_size,
                'mime_type': mime_type
            }

        except Exception as e:
            logger.error("upload_from_bytes error: %s", e)
            return {'success': False, 'error': str(e)}

    @staticmethod
    def download_file(storage_path: str) -> Optional[bytes]:
        """
        Read a file from local storage.

        Returns:
            File bytes or None on error
        """
        try:
            full_path = os.path.join(UPLOAD_DIR, storage_path)
            with open(full_path, 'rb') as f:
                return f.read()
        except Exception as e:
            logger.error("download_file error: %s", e)
            return None

    @staticmethod
    def delete_file(storage_path: str) -> bool:
        """
        Delete a file from local storage.

        Returns:
            True if deleted successfully
        """
        try:
            full_path = os.path.join(UPLOAD_DIR, storage_path)
            if os.path.exists(full_path):
                os.remove(full_path)
            return True
        except Exception as e:
            logger.error("delete_file error: %s", e)
            return False

    @staticmethod
    def list_files(folder: str = "") -> List[dict]:
        """
        List files in a folder.

        Returns:
            List of file info dicts with 'name', 'size', 'url'
        """
        try:
            target = _ensure_upload_dir(folder)
            files = []
            for fname in os.listdir(target):
                fpath = os.path.join(target, fname)
                if os.path.isfile(fpath):
                    storage_path = f"{folder}/{fname}" if folder else fname
                    files.append({
                        'name': fname,
                        'size': os.path.getsize(fpath),
                        'url': f"/static/uploads/{storage_path}"
                    })
            return files
        except Exception as e:
            logger.error("list_files error: %s", e)
            return []

    @staticmethod
    def get_public_url(storage_path: str) -> str:
        """
        Get public URL for a stored file.

        Returns:
            URL path string
        """
        return f"/static/uploads/{storage_path}"

    @staticmethod
    def create_signed_url(storage_path: str, expires_in: int = 3600) -> Optional[str]:
        """
        Returns the same public URL (no signing needed for local storage).
        Signature kept for API compatibility.
        """
        return StorageService.get_public_url(storage_path)
