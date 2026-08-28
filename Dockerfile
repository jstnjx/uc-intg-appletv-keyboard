FROM python:3.11-slim-bookworm

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    UC_DISABLE_MDNS_PUBLISH=false \
    UC_MDNS_LOCAL_HOSTNAME="" \
    UC_INTEGRATION_INTERFACE=0.0.0.0 \
    UC_INTEGRATION_HTTP_PORT=9090 \
    UC_CONFIG_HOME=/config

COPY requirements.txt ./
RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir -r requirements.txt \
    && mkdir -p /config

COPY driver.json LICENSE ./
COPY intg-appletv-keyboard ./intg-appletv-keyboard

EXPOSE 9090
VOLUME ["/config"]

LABEL org.opencontainers.image.source="https://github.com/jstnjx/uc-intg-appletv-keyboard"

CMD ["python3", "-u", "intg-appletv-keyboard/driver.py"]
