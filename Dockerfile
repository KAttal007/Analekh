# Application image: API, Celery workers and scheduler (design doc 22.1, Appendix G.1, G.8).
# Runtime: Python only. Headless LibreOffice (recalculation on Apply) lives in its own image,
# deploy/recalc, and is reached over HTTP (RECALC_URL).
#
# Two stages, so the slow parts build side by side and stay out of each other's cache:
#   builder  Python packages into /opt/venv (changes when requirements.txt changes)
#   runtime  Debian security upgrades from apt, then the venv and code
# Cache mounts keep apt's and uv's downloads between builds, so a layer that must rebuild does not
# fetch everything again. They need BuildKit, which Docker 23 and later use by default.

FROM python:3.12-slim AS builder
ENV UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir uv && uv venv /opt/venv
WORKDIR /app
COPY requirements.txt ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install -r requirements.txt
COPY pyproject.toml README.md ./
COPY analekh ./analekh
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --no-deps .

FROM python:3.12-slim AS runtime
# No LibreOffice here (deploy/recalc has it). OCR of scanned pages is RapidOCR (a Python package
# with its own ONNX models), so no OCR binary is installed either.
# Retries cover the odd bad mirror reply; docker-clean is removed so the cache mount keeps the .debs.
# The mirror is fetched over HTTPS: some networks stall plain-HTTP downloads from deb.debian.org.
# The package lists are cleared first (a few seconds to fetch again), so a truncated list left in the
# cache mount by an interrupted build cannot break every later one. The upgrade takes Debian security
# fixes released after the base image was built (container scanning flags them otherwise).
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    sed -i 's|http://deb.debian.org|https://deb.debian.org|g' /etc/apt/sources.list.d/debian.sources \
    && rm -rf /var/lib/apt/lists/* \
    && rm -f /etc/apt/apt.conf.d/docker-clean \
    && apt-get -o Acquire::Retries=5 update \
    && apt-get -o Acquire::Retries=5 upgrade -y

ENV PATH="/opt/venv/bin:$PATH"
COPY --from=builder /opt/venv /opt/venv
WORKDIR /app
COPY alembic.ini ./
# alembic.ini points at analekh/db/migrations relative to /app, so the migration scripts
# must sit there too (the installed package alone is not enough for the migrate service).
COPY analekh/db/migrations ./analekh/db/migrations
# lxml's wheels bundle libxml2 and libxslt, so the Debian packages are not installed. LibreOffice
# used to pull in shared libraries as dependencies; this import check fails the build if any
# compiled package still needs one. If it does, add that package to the apt line above (for lxml:
# `libxml2 libxslt1.1`).
RUN python -c "import lxml.etree, lxml.objectify, cv2, pymupdf, onnxruntime"
# The OCR settings file must have been installed with the package (RapidOCR would otherwise
# quietly fall back to its own defaults).
RUN python -c "from analekh.docs.pdf import OCR_CONFIG; assert OCR_CONFIG.is_file(), OCR_CONFIG"

# No setuid/setgid programs: the app never needs su, mount or passwd, and this closes the local
# privilege-escalation paths in util-linux, login and shadow that container scanning reports.
RUN useradd --create-home --uid 10001 analekh \
    && find / -xdev -perm /6000 -type f -exec chmod a-s {} +
USER analekh
EXPOSE 8000
CMD ["uvicorn", "analekh.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
