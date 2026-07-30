import multiprocessing
import os

bind = "0.0.0.0:8001"
worker_class = "uvicorn.workers.UvicornWorker"
# Override with WEB_CONCURRENCY if set. Capped at 4 by default — this is a
# small shop app, not a high-throughput service, and each worker holds its
# own DB connection pool, so unbounded "cpu_count * 2 + 1" over-provisions
# badly on beefy build machines/CI runners.
workers = int(os.getenv("WEB_CONCURRENCY", min(multiprocessing.cpu_count() * 2 + 1, 4)))
timeout = 60
accesslog = "-"
errorlog = "-"

# Trust X-Forwarded-* headers from nginx — needed so the app sees the real
# client IP, not nginx's. uvicorn's forwarded_allow_ips only accepts exact
# IPs or "*", not CIDR ranges (a CIDR value here crashes gunicorn on boot).
# "*" is fine here: in the intended prod topology nginx is the only thing
# that can reach this container directly (its port isn't published to the
# host except via the local-testing-only docker-compose.override.yml), and
# the app itself never trusts request.client.host for security decisions —
# rate limiting uses app.lang.client_ip, which reads X-Real-IP/
# X-Forwarded-For directly and ignores this setting.
forwarded_allow_ips = "*"
