"""
Create deployment ZIP for AWS EC2 — run from project root.
Excludes: venv, __pycache__, .env, .git, uploads, *.pyc, tmp files.
Output: excuseai_deploy.zip in project root.
"""
import zipfile
import os

PROJECT_DIR = r"c:\Users\aswin\OneDrive\Documents\new project"
OUTPUT_ZIP  = os.path.join(PROJECT_DIR, 'excuseai_deploy.zip')

SKIP_DIRS = {
    'venv', '.venv', 'env', 'ENV',
    '__pycache__', '.git',
    'node_modules', '.pytest_cache', '.mypy_cache',
    'dist', 'build',
}
SKIP_FILES   = {'.env', '.env.local', '.env.production', 'excuseai_deploy.zip'}
SKIP_EXTENSIONS = {'.pyc', '.pyo', '.pyd', '.log'}

count = 0
with zipfile.ZipFile(OUTPUT_ZIP, 'w', zipfile.ZIP_DEFLATED) as zf:
    for root, dirs, files in os.walk(PROJECT_DIR):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for file in files:
            if file in SKIP_FILES:
                continue
            if any(file.endswith(ext) for ext in SKIP_EXTENSIONS):
                continue
            abs_path = os.path.join(root, file)
            if abs_path == OUTPUT_ZIP:
                continue
            rel_path = os.path.relpath(abs_path, PROJECT_DIR)
            zf.write(abs_path, rel_path)
            count += 1

size_mb = os.path.getsize(OUTPUT_ZIP) / (1024 * 1024)
print(f"Created : {OUTPUT_ZIP}")
print(f"Files   : {count}")
print(f"Size    : {size_mb:.1f} MB")
