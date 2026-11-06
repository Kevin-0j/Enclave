#!/usr/bin/env bash
# For each camera in cameras.json: prepare a 1080p main loop and a 360p sub loop (cached in /cache),
# then publish both to MediaMTX forever, restarting a publisher if it exits.
# Main is published with -c copy (no CPU); sub is re-encoded live with a burned-in wall clock,
# which is how NFR1 (live latency) is measured.
set -euo pipefail
: "${MEDIAMTX_RTSP:?}" "${SIM_PUBLISH_USER:?}" "${SIM_PUBLISH_PASS:?}"
CONFIG=${CONFIG:-/sim/cameras.json}
font=/usr/share/fonts/dejavu/DejaVuSansMono.ttf

prepare() { # id scene name motion_test
  local id=$1 scene=$2 name=$3 motion=$4 main=/cache/$1-main.mp4 sub=/cache/$1-sub.mp4 src=""
  [[ -f $main && -f $sub ]] && return
  for c in "/clips/$id.mp4" "/clips/$scene.mp4"; do [[ -f $c ]] && src=$c && break; done
  if [[ -n $src && $motion != true ]]; then
    echo "[$name] using clip $src"
    ffmpeg -hide_banner -loglevel error -y -i "$src" -t 120 -an \
      -vf "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,fps=25" \
      -c:v libx264 -preset veryfast -crf 24 -pix_fmt yuv420p -bf 0 -g 25 -keyint_min 25 -sc_threshold 0 "$main.tmp.mp4"
  else
    echo "[$name] rendering synthetic scene '$scene'"
    bash /sim/render-scene.sh "$scene" "$main.tmp.mp4" "$name" "$motion"
  fi
  ffmpeg -hide_banner -loglevel error -y -i "$main.tmp.mp4" -vf scale=640:360 \
    -c:v libx264 -preset veryfast -crf 26 -pix_fmt yuv420p -bf 0 -g 25 -an "$sub.tmp.mp4"
  mv "$main.tmp.mp4" "$main"; mv "$sub.tmp.mp4" "$sub"
}

publish() { # label url args...
  local label=$1 url=$2; shift 2
  while true; do
    ffmpeg -hide_banner -loglevel warning -re -stream_loop -1 "$@" -f rtsp -rtsp_transport tcp "$url" || true
    echo "[$label] publisher exited; restarting in 3 s" >&2
    sleep 3
  done
}

auth="${SIM_PUBLISH_USER}:${SIM_PUBLISH_PASS}"
mapfile -t cams < <(jq -r '.tenants[] | .id as $t | .cameras[] | [$t, .id, .scene, .name, (.motion_test // false)] | @tsv' "$CONFIG")

for row in "${cams[@]}"; do
  IFS=$'\t' read -r tid cid scene name motion <<<"$row"
  prepare "$cid" "$scene" "$name" "$motion"
done

for row in "${cams[@]}"; do
  IFS=$'\t' read -r tid cid scene name motion <<<"$row"
  base="rtsp://${auth}@${MEDIAMTX_RTSP}/t/${tid}/c/${cid}"
  publish "$name/main" "$base/main" -fflags +genpts -i "/cache/$cid-main.mp4" -c copy &
  publish "$name/sub" "$base/sub" -fflags +genpts -i "/cache/$cid-sub.mp4" \
    -vf "drawtext=fontfile=${font}:text='%{localtime\:%Y-%m-%d %H\\\\\:%M\\\\\:%S}':x=w-tw-12:y=h-th-12:fontsize=16:fontcolor=white:box=1:boxcolor=black@0.5:boxborderw=6" \
    -c:v libx264 -preset ultrafast -tune zerolatency -pix_fmt yuv420p -bf 0 -g 25 -b:v 400k -maxrate 500k -bufsize 1M &
  echo "[$name] publishing t/$tid/c/$cid/{main,sub}"
done
wait
