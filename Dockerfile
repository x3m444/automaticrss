FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    transmission-daemon \
    supervisor \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /config/transmission /downloads /watch \
    && chmod -R 777 /config /downloads /watch

RUN cat > /config/transmission/settings.json <<'EOF'
{
    "download-dir": "/downloads",
    "watch-dir": "/watch",
    "watch-dir-enabled": true,
    "rpc-port": 9091,
    "rpc-bind-address": "0.0.0.0",
    "rpc-whitelist-enabled": false,
    "rpc-authentication-required": false,
    "umask": 2,
    "peer-port": 51413,
    "dht-enabled": true
}
EOF

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

COPY supervisord.conf /etc/supervisor/conf.d/automaticrss.conf

EXPOSE 8080 9091 51413

ENV PYTHONUNBUFFERED=1 \
    TRANSMISSION_HOST=localhost \
    TRANSMISSION_PORT=9091

CMD ["/usr/bin/supervisord", "-n", "-c", "/etc/supervisor/supervisord.conf"]
