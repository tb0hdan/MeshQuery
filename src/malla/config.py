
from __future__ import annotations
import os
from dataclasses import dataclass

@dataclass
class AppConfig:
    # Postgres
    database_host: str = os.getenv("MALLA_DATABASE_HOST", "localhost")
    database_port: int = int(os.getenv("MALLA_DATABASE_PORT", "5432"))
    database_name: str = os.getenv("MALLA_DATABASE_NAME", "malla")
    database_user: str = os.getenv("MALLA_DATABASE_USER", "malla")
    database_password: str = os.getenv("MALLA_DATABASE_PASSWORD", "")
    # Legacy / optional SQLite support
    database_file: str | None = os.getenv("MALLA_DATABASE_FILE")  # may be None

    # MQTT (default to compose service name)
    mqtt_broker_address: str = os.getenv("MALLA_MQTT_BROKER_ADDRESS", "mqtt")
    mqtt_port: int = int(os.getenv("MALLA_MQTT_PORT", "1883"))
    mqtt_username: str | None = os.getenv("MALLA_MQTT_USERNAME")
    mqtt_password: str | None = os.getenv("MALLA_MQTT_PASSWORD")
    mqtt_topic: str = os.getenv("MALLA_MQTT_TOPIC", "msh/#")

    # Web
    web_host: str = os.getenv("MALLA_WEB_HOST", "0.0.0.0")
    web_port: int = int(os.getenv("MALLA_WEB_PORT", "8080"))
    # Back-compat aliases (old code expects cfg.host/port)
    @property
    def host(self) -> str:
        return self.web_host
    @property
    def port(self) -> int:
        return self.web_port

    # Misc
    log_level: str = os.getenv("MALLA_LOG_LEVEL", "INFO")
    debug: bool = os.getenv("MALLA_DEBUG", "false").lower() in ("true", "1", "yes")
    timezone: str = os.getenv("MALLA_TIMEZONE", "America/New_York")

def get_config() -> AppConfig:
    return AppConfig()
