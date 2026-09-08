# syntax=docker/dockerfile:1.7

FROM python:3.13-slim

ARG MEDIAFLOW_UID=10001
ARG MEDIAFLOW_GID=10001

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MEDIAFLOW_CONFIG=/config/mediaflow.json \
    MEDIAFLOW_DATA_DIR=/data

RUN groupadd --gid "${MEDIAFLOW_GID}" mediaflow \
    && useradd --uid "${MEDIAFLOW_UID}" --gid "${MEDIAFLOW_GID}" \
        --home-dir /opt/mediaflow --create-home --shell /usr/sbin/nologin mediaflow

WORKDIR /opt/mediaflow

COPY pyproject.toml ./
COPY mediaflow ./mediaflow

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
