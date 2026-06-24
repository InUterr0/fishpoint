FROM caddy:2-alpine

COPY Caddyfile /etc/caddy/Caddyfile
COPY . /usr/share/caddy

# Pliki robocze/skrypty nie są potrzebne na produkcji
RUN rm -f /usr/share/caddy/Dockerfile /usr/share/caddy/Caddyfile \
    /usr/share/caddy/*.py /usr/share/caddy/.dockerignore 2>/dev/null || true
