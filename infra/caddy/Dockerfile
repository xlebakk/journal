# syntax=docker/dockerfile:1
# The web server: the production build of the frontend served by Caddy (stage 7).
# Build from the repository root:  docker build -f infra/caddy/Dockerfile .

FROM node:26-alpine AS build
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
# The PWA check fails the image if the service worker would cache the API.
RUN npm run build && npm run check:pwa

FROM caddy:2-alpine
# Not root; ports 80/443 are opened via the ip_unprivileged_port_start sysctl in compose.
RUN addgroup -S web && adduser -S -G web -H web \
    && mkdir -p /data /config && chown -R web:web /data /config
COPY --from=build /app/dist /srv
COPY infra/caddy/Caddyfile infra/caddy/common.caddy /etc/caddy/
USER web
