FROM python:3.11-slim

# supercronic — cron runner that respects container PID 1 conventions
# TODO(security): pin a verified SHA1/SHA256 for the binary before publishing.
ARG SUPERCRONIC_VERSION=v0.2.29
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
    && curl -fsSLo /usr/local/bin/supercronic \
       "https://github.com/aptible/supercronic/releases/download/${SUPERCRONIC_VERSION}/supercronic-linux-amd64" \
    && chmod +x /usr/local/bin/supercronic \
    && apt-get purge -y curl && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY scout.py entrypoint.sh trigger_watcher.py argus_analysis.py ./
RUN chmod +x entrypoint.sh

CMD ["./entrypoint.sh"]
