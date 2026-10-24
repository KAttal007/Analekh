# Recalculation service: headless LibreOffice behind a small HTTP server (design doc 16.5, 22.1).
# LibreOffice lives here and nowhere else, so the application image carries none of its Debian
# packages. Only Python's standard library is used: no pip packages, no application code.
# Run it on an internal Docker network only (docker-compose.yml: `recalc`, `internal: true`).
#
# The apt pattern matches the application image: HTTPS mirror (some networks stall plain-HTTP
# downloads from deb.debian.org), retries for the odd bad mirror reply, package lists cleared first
# so a truncated list left in the cache mount cannot break later builds, and an upgrade that takes
# the Debian security fixes released after the base image was built.

FROM python:3.12-slim
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    sed -i 's|http://deb.debian.org|https://deb.debian.org|g' /etc/apt/sources.list.d/debian.sources \
    && rm -rf /var/lib/apt/lists/* \
    && rm -f /etc/apt/apt.conf.d/docker-clean \
    && apt-get -o Acquire::Retries=5 update \
    && apt-get -o Acquire::Retries=5 upgrade -y \
    && apt-get -o Acquire::Retries=5 install -y --no-install-recommends libreoffice-calc-nogui

# Non-root, and no setuid/setgid programs (the service never needs su, mount or passwd).
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin recalc \
    && find / -xdev -perm /6000 -type f -exec chmod a-s {} +

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
COPY server.py /srv/server.py
USER recalc
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/healthz' % os.environ.get('RECALC_PORT', '8080'), timeout=3)"]
CMD ["python", "/srv/server.py"]
