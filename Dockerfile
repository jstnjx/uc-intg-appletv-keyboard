FROM python:3.11-slim-bookworm AS builder

WORKDIR /build

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN python -m pip install --no-cache-dir --upgrade pip setuptools wheel \
    && python -m pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt

FROM python:3.11-slim-bookworm

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    UC_DISABLE_MDNS_PUBLISH=false \
    UC_MDNS_LOCAL_HOSTNAME="" \
    UC_INTEGRATION_INTERFACE=0.0.0.0 \
    UC_INTEGRATION_HTTP_PORT=9090 \
    UC_CONFIG_HOME=/config

COPY requirements.txt ./
COPY --from=builder /wheels /wheels
RUN python -m pip install --no-cache-dir --no-index --find-links=/wheels -r requirements.txt \
    && python -c "import miniaudio, pyatv, ucapi, ucapi_framework" \
    && rm -rf /wheels \
    && mkdir -p /config

COPY driver.json LICENSE ./
COPY intg-appletv-keyboard ./intg-appletv-keyboard

EXPOSE 9090
VOLUME ["/config"]

LABEL org.opencontainers.image.source="https://github.com/jstnjx/uc-intg-appletv-keyboard"

CMD ["python3", "-u", "intg-appletv-keyboard/driver.py"]
