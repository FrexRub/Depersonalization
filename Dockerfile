# syntax=docker/dockerfile:1.7
FROM python:3.11-slim-bookworm AS builder

ARG TORCH_VERSION=2.7.1
ENV VIRTUAL_ENV=/opt/venv \
    PATH=/opt/venv/bin:$PATH \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

RUN python -m venv "$VIRTUAL_ENV" \
    && apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.lock /tmp/requirements.lock
RUN pip install --index-url https://download.pytorch.org/whl/cpu "torch==${TORCH_VERSION}" \
    && pip install -r /tmp/requirements.lock

FROM python:3.11-slim-bookworm AS runtime

ENV VIRTUAL_ENV=/opt/venv \
    PATH=/opt/venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HOME=/home/app \
    OPF_MODEL_PATH=/models/privacy-filter

RUN groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --create-home --shell /usr/sbin/nologin app \
    && mkdir -p /app /models/privacy-filter \
    && chown -R app:app /app /models /home/app

COPY --from=builder /opt/venv /opt/venv
COPY --chown=app:app app /app/app
COPY --chown=app:app scripts /app/scripts

USER app
WORKDIR /app
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15m --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/ready', timeout=3)" || exit 1

ENTRYPOINT ["/app/scripts/docker-entrypoint.sh"]

