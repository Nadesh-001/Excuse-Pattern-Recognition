"""
Secure File Upload Service
Handles validated file uploads to local filesystem storage (static/uploads/).

Note: Previously used Supabase Storage. Now uses local storage via StorageService.
"""

import hashlib
import logging

from utils.file_validation import validate_file, get_safe_filename
from services.storage_service import StorageService

logger = logging.getLogger(__name__)


def upload_file(file, custom_filename=None, folder=""):
    """
    Upload file to local storage with validation.

    Args:
        file: Flask file object from request.files
        custom_filename: Optional custom filename (will be sanitized)
        folder: Optional folder path (e.g., "tasks/123")

    Returns:
        dict with 'success', 'url', 'path', or 'error'

    Example:
        file = request.files['file']
        result = upload_file(file, folder="tasks/42")
        if result['success']:
            print(f"Uploaded: {result['url']}")
    """
    try:
        # Validate file security
        validate_file(file)

        # Generate safe filename
        if custom_filename:
            safe_filename = get_safe_filename(custom_filename)
        else:
            safe_filename = get_safe_filename(file.filename)

        # Construct storage path

        # Read file content
        file_content = file.read()
        file.seek(0)  # Reset for potential reuse

        # File hash for integrity tracking
        file_hash = hashlib.sha256(file_content).hexdigest()

        # Upload to local filesystem via StorageService
        result = StorageService.upload_from_bytes(
            file_bytes=file_content,
            file_name=safe_filename,
            folder=folder,
            mime_type=file.content_type
        )

        if not result.get('success'):
            return result

        return {
            'success': True,
            'url': result['url'],
            'path': result['path'],
            'filename': safe_filename,
            'size': len(file_content),
            'mime_type': file.content_type,
            'hash': file_hash
        }

    except ValueError as e:
        return {'success': False, 'error': str(e)}
    except Exception as e:
        logger.error("upload_file error: %s", e)
        return {'success': False, 'error': f"Upload failed: {str(e)}"}


def delete_file(storage_path):
    """
    Delete file from local storage.

    Args:
        storage_path: Full path in storage (e.g., "tasks/123/file.pdf")

    Returns:
        bool: True if deleted successfully
    """
    return StorageService.delete_file(storage_path)


def get_file_url(storage_path):
    """
    Get public URL for a file.

    Args:
        storage_path: Full path in storage

    Returns:
        str: Public URL
    """
    return StorageService.get_public_url(storage_path)
