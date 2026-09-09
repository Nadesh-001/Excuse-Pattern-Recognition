import os

# Bind to port 80 (HTTP) on AWS EC2.
# Nginx will proxy :80 → Gunicorn on :8000
bind = f"0.0.0.0:{os.environ.get('PORT', '8000')}"

# t3.micro: 1 vCPU, 1 GB RAM — keep 1 worker to avoid OOM.
# Use 4 threads for concurrent request handling.
# Tip: add 1 GB swap on EC2 to prevent kernel OOM kills:
#   sudo fallocate -l 1G /swapfile && sudo chmod 600 /swapfile
#   sudo mkswap /swapfile && sudo swapon /swapfile
workers = int(os.environ.get("WEB_CONCURRENCY", "1"))
threads = 4
worker_class = "gthread"
timeout = 120       # Allow for ML model cold-start
keepalive = 5
graceful_timeout = 30

# Logging — systemd captures stdout/stderr on EC2
accesslog = "-"
errorlog  = "-"
loglevel  = "info"

# Process naming (visible in ps/top)
proc_name = "excuseai"
