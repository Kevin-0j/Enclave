"""Settings come only from the environment (rule 7). Nothing secret has a default."""

from functools import lru_cache
from ipaddress import IPv4Network, IPv6Network, ip_network

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    environment: str = "development"
    app_origin: str = "https://enclave.localhost"
    dev_origins: str = ""

    database_url: SecretStr
    redis_url: SecretStr

    jwt_secret: SecretStr
    stream_token_secret: SecretStr
    refresh_pepper: SecretStr
    camera_kek_b64: SecretStr

    access_token_minutes: int = 15
    refresh_token_days: int = 14
    stream_token_seconds: int = 60

    sim_publish_user: str = "sim"
    sim_publish_pass: SecretStr
    media_internal_user: str = "enclave-api"
    media_internal_pass: SecretStr
    media_hook_allowed_cidrs: str = "172.31.250.0/24"
    mediamtx_api_url: str = "http://mediamtx:9997"
    mediamtx_playback_url: str = "http://mediamtx:9996"

    login_rate_per_minute: int = 10
    stream_rate_per_minute: int = 120
    # Direct RTSP sources are pulled by the cloud media node. Private/LAN targets are refused unless
    # this is on (dev only); real sites connect through an edge gateway (M6).
    allow_private_camera_urls: bool = False

    seed_password: SecretStr | None = None
    cameras_json: str = Field(default="/app/cameras.json")

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def allowed_origins(self) -> list[str]:
        extra = (
            [o.strip() for o in self.dev_origins.split(",") if o.strip()] if not self.is_production else []
        )
        return [self.app_origin, *extra]

    @property
    def hook_networks(self) -> list[IPv4Network | IPv6Network]:
        return [ip_network(c.strip()) for c in self.media_hook_allowed_cidrs.split(",") if c.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
