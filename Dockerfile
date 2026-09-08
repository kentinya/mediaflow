# syntax=docker/dockerfile:1.7

# Frontend build stage. Node/Vite exists only here and is never copied into
# the final runtime image. `npm ci` installs exactly the committed
# web/package-lock.json and fails on any lockfile/package.json mismatch.
FROM node:22-bookworm-slim AS web-build

WORKDIR /build/web

COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY web/ ./
RUN npm run build \
    && test -f dist/index.html \
    && test -n "$(find dist -type f \( -name '*.js' -o -name '*.css' \) -print -quit)"

# Final Python/MediaFlow runtime. Only the built V2 static artifact crosses
# the stage boundary: no Node executable, npm, node_modules, frontend source,
# development server or second HTTP service is present or required at runtime.
FROM python:3.13-slim

ARG MEDIAFLOW_UID=10001
ARG MEDIAFLOW_GID=10001

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MEDIAFLOW_CONFIG=/config/mediaflow.json \
    MEDIAFLOW_DATA_DIR=/data \
    MEDIAFLOW_UI_V2_ASSET_ROOT=/opt/mediaflow/web/dist

RUN groupadd --gid "${MEDIAFLOW_GID}" mediaflow \
    && useradd --uid "${MEDIAFLOW_UID}" --gid "${MEDIAFLOW_GID}" \
        --home-dir /opt/mediaflow --create-home --shell /usr/sbin/nologin mediaflow

WORKDIR /opt/mediaflow

COPY pyproject.toml ./
COPY mediaflow ./mediaflow
COPY --from=web-build /build/web/dist /opt/mediaflow/web/dist

RUN python -m pip install --no-cache-dir --no-compile --disable-pip-version-check . \
    && mkdir -p /data /config \
    && chown -R "${MEDIAFLOW_UID}:${MEDIAFLOW_GID}" /data /config /opt/mediaflow \
    && find /usr/local/lib/python3.13/site-packages -type d -name __pycache__ \
        -prune -exec rm -rf {} + \
    && rm -rf mediaflow pyproject.toml build mediaflow.egg-info /root/.cache/pip \
        /opt/mediaflow/.bash_logout /opt/mediaflow/.bashrc /opt/mediaflow/.profile

VOLUME ["/data"]

USER "${MEDIAFLOW_UID}:${MEDIAFLOW_GID}"

ENTRYPOINT ["python", "-m", "mediaflow.container_entrypoint"]
