from prometheus_client import Counter

LOGINS = Counter("enclave_logins_total", "Login attempts", ["result"])
STREAM_TOKENS = Counter("enclave_stream_tokens_total", "Stream tokens issued", ["variant"])
MEDIA_AUTH = Counter("enclave_media_auth_total", "Media auth hook decisions", ["action", "decision"])
