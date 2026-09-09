"""
File Upload Validation Utility
Validates file types and sizes to prevent malicious uploads
"""

import os

# Allowed MIME types for uploads
ALLOWED_MIME_TYPES = {
    "image/png",
    "image/jpeg",
    "image/jpg",
    "application/pdf",
    "application/json",
    "text/csv",
    "text/plain"
}

# Maximum file size in MB
MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "50"))


def validate_file(file):
    """
    Validate uploaded file for security.
    
    Args:
        file: Flask file object from request.files
        
    Raises:
        ValueError: If file is invalid or dangerous
        
    Returns:
        True if validation passes
    """
    # Check if file exists
    if not file or not file.filename:
        raise ValueError("No file provided")
    
    # Validate MIME type
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise ValueError(
            f"Invalid file type: {file.content_type}. "
            f"Allowed types: {', '.join(ALLOWED_MIME_TYPES)}"
        )
    
    # Check file size
    file.seek(0, 2)  # Move to end of file
    size_bytes = file.tell()
    file.seek(0)  # Reset to beginning
    
    size_mb = size_bytes / (1024 * 1024)
    
    if size_mb > MAX_FILE_SIZE_MB:
        raise ValueError(
            f"File too large: {size_mb:.2f} MB. "
            f"Maximum allowed: {MAX_FILE_SIZE_MB} MB"
        )
    
    # Check filename extension matches MIME type
    if '.' not in file.filename:
        raise ValueError("File must have an extension")
    
    ext = file.filename.rsplit('.', 1)[1].lower()
    valid_extensions = {'png', 'jpg', 'jpeg', 'pdf', 'json', 'csv', 'txt'}
    
    if ext not in valid_extensions:
        raise ValueError(
            f"Invalid file extension: .{ext}. "
            f"Allowed: {', '.join(valid_extensions)}"
        )
    
    return True


def get_safe_filename(filename):
    """
    Generate safe filename by removing dangerous characters.
    
    Args:
        filename: Original filename
        
    Returns:
        Safe filename string
    """
    import re
    import time
    import hashlib
    
    # Remove path components
    filename = os.path.basename(filename)
    
    # Get extension
    if '.' in filename:
        name, ext = filename.rsplit('.', 1)
    else:
        name, ext = filename, ''
    
    # Clean filename - remove non-alphanumeric except dash and underscore
    safe_name = re.sub(r'[^a-zA-Z0-9_-]', '_', name)
    
    # Add timestamp and hash for uniqueness
    timestamp = int(time.time())
    hash_part = hashlib.md5(filename.encode()).hexdigest()[:8]
    
    # Construct safe filename
    if ext:
        return f"{safe_name}_{timestamp}_{hash_part}.{ext}"
    return f"{safe_name}_{timestamp}_{hash_part}"
