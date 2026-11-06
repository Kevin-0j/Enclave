#!/usr/bin/env bash
# Render one synthetic 60 s scene at 1080p25 (H.264, no B-frames, 1 s GOP) to $2.
# Scenes are deliberately plain: dim, noisy "night camera" plates with something moving through,
# so motion detection and the UI have real pixels to work with. Real footage: drop MP4s in sim/clips/.
#   render-scene.sh <scene> <out.mp4> <label> <motion_test:true|false>
set -euo pipefail
scene=$1 out=$2 label=$3 motion_test=${4:-false}
font=/usr/share/fonts/dejavu/DejaVuSans.ttf

case $scene in
  gate)      bg=0x1b232b; ground=0x2a3138; obj=0x8a7f6a; ow=420; oh=220; oy=700 ;;
  parking)   bg=0x161d24; ground=0x262c31; obj=0x6c7a86; ow=360; oh=180; oy=760 ;;
  lobby)     bg=0x2b2a27; ground=0x3a3833; obj=0x23262b; ow=90;  oh=320; oy=560 ;;
  perimeter) bg=0x121a17; ground=0x1f2a24; obj=0x58625a; ow=80;  oh=260; oy=640 ;;
  *)         bg=0x1b232b; ground=0x2a3138; obj=0x777777; ow=200; oh=200; oy=700 ;;
esac

# Moving object: crosses continuously, or only at 10-15 s and 40-45 s for the motion-test camera.
if [[ $motion_test == true ]]; then
  enable="between(t,10,15)+between(t,40,45)"
  xexpr="if(lt(mod(t,30),15), (mod(t,30)-10)*450-${ow}, 0)"
else
  enable="1"
  xexpr="mod(t*140,2200)-${ow}"
fi

ffmpeg -hide_banner -loglevel error -y \
  -f lavfi -i "color=c=${bg}:s=1920x1080:r=25:d=60" \
  -f lavfi -i "color=c=${obj}:s=${ow}x${oh}:r=25:d=60" \
  -filter_complex "
    [0]drawbox=x=0:y=820:w=iw:h=260:color=${ground}:t=fill,
       drawbox=x=0:y=812:w=iw:h=4:color=0x3d464e:t=fill,
       drawbox=x=160:y=240:w=40:h=580:color=0x323b43:t=fill,
       drawbox=x=1720:y=240:w=40:h=580:color=0x323b43:t=fill[bgp];
    [bgp][1]overlay=x='${xexpr}':y=${oy}:enable='${enable}',
       noise=alls=10:allf=t,
       vignette=PI/4,
       drawtext=fontfile=${font}:text='${label}':x=48:y=h-80:fontsize=40:fontcolor=white@0.85:box=1:boxcolor=black@0.35:boxborderw=12
  " \
  -t 60 -c:v libx264 -preset veryfast -crf 27 -pix_fmt yuv420p -profile:v main -bf 0 -g 25 -keyint_min 25 -sc_threshold 0 \
  -an -movflags +faststart "$out"
