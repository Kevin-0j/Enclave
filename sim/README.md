# Camera simulator

Publishes every camera in `cameras.json` to MediaMTX as two RTSP streams:
`t/{tenant}/c/{camera}/main` (1080p, copied) and `.../sub` (360p, live-encoded, wall clock top right).

**Footage.** Drop licensed or royalty-free MP4s into `clips/` named after a scene (`gate.mp4`,
`parking.mp4`, `lobby.mp4`, `perimeter.mp4`) or a camera ID. Good free sources: Pexels and Pixabay
(check each clip's licence; avoid identifiable people). Without clips, synthetic scenes are rendered.
The motion-test camera ("Main gate") always uses the synthetic scene so that motion happens at known
times: 10–15 s and 40–45 s of every 60 s loop.

Rendered loops are cached in the `sim-cache` volume; `docker volume rm enclave_sim-cache` re-renders.
