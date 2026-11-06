# Builds the PWA and serves it with Caddy (TLS, security headers, reverse proxy).
FROM node:22.23.4-alpine3.23 AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web/ ./
RUN npm run build \
 && find dist -type d -exec chmod 0755 {} + && find dist -type f -exec chmod 0644 {} +

FROM caddy:2.11.7-alpine
RUN addgroup -S -g 10001 caddy-run && adduser -S -u 10001 -G caddy-run caddy-run \
 && mkdir -p /data /config && chown -R caddy-run:caddy-run /data /config
COPY --chmod=0644 infra/caddy/Caddyfile /etc/caddy/Caddyfile
COPY --from=web /web/dist /srv/web
ENV XDG_DATA_HOME=/data XDG_CONFIG_HOME=/config
USER caddy-run
