# syntax=docker/dockerfile:1

FROM python:3.12-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:0.12 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY pyproject.toml uv.lock .python-version ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --group docker

FROM python:3.12-slim

# Pango/HarfBuzz + a font for WeasyPrint PDF export.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0 fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# uid 1000 matches the default user on most Linux hosts, so files in the
# mounted data folder stay owned by the host user.
RUN useradd --uid 1000 --create-home --shell /usr/sbin/nologin kanplan

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    DATA_DIR=/data \
    DEBUG=False

WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY . .
RUN SECRET_KEY=collectstatic-only python manage.py collectstatic --noinput --verbosity 0

VOLUME /data
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/login/', timeout=4)"

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["gunicorn", "kanplan.wsgi", "--bind", "0.0.0.0:8000", "--workers", "1", "--threads", "4", "--timeout", "120", "--access-logfile", "-"]
