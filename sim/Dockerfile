# Enclave camera simulator: FFmpeg publishing looped clips to MediaMTX as RTSP main + sub streams.
FROM alpine:3.23.8
RUN apk add --no-cache ffmpeg jq font-dejavu tzdata bash \
 && adduser -D -u 10001 sim \
 && mkdir -p /cache && chown sim:sim /cache
COPY --chmod=0755 sim/entrypoint.sh sim/render-scene.sh /sim/
COPY --chmod=0644 sim/cameras.json /sim/cameras.json
COPY --chmod=0755 sim/clips/ /clips/
ENV TZ=Africa/Nairobi
USER sim
WORKDIR /sim
ENTRYPOINT ["bash", "/sim/entrypoint.sh"]
