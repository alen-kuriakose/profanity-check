"""
Configuration module for the application.
"""
import os
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field

class DatabaseConfig(BaseModel):
    """Database configuration."""
    host: str = Field(default="localhost")
    port: int = Field(default=5433)  # Updated to use port 5433
    name: str = Field(default="igot")
    user: str = Field(default="postgres")
    password: str = Field(default="postgres")  # Updated to match docker-compose password

class KafkaConfig(BaseModel):
    """Kafka configuration."""
    bootstrap_servers: List[str] = Field(default=["localhost:9092"])
    
class StorageConfig(BaseModel):
    """Storage configuration."""
    video_storage_path: str = Field(default="/tmp/igot/videos")

class ModuleConfig(BaseModel):
    """Module configuration."""
    enabled: bool = Field(default=True)
    
class Settings(BaseModel):
    """Application settings."""
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    kafka: KafkaConfig = Field(default_factory=KafkaConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    modules: Dict[str, ModuleConfig] = Field(default_factory=dict)

# Global settings instance
_settings = None

def get_settings() -> Settings:
    """Get the application settings."""
    global _settings
    if _settings is None:
        # Create default settings
        _settings = Settings(
            database=DatabaseConfig(
                host=os.getenv("DB_HOST", "localhost"),
                port=int(os.getenv("DB_PORT", "5433")),  # Updated to use port 5433
                name=os.getenv("DB_NAME", "igot"),
                user=os.getenv("DB_USER", "postgres"),
                password=os.getenv("DB_PASSWORD", "postgres")  # Updated to match docker-compose password
            ),
            kafka=KafkaConfig(
                bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092").split(",")
            ),
            storage=StorageConfig(
                video_storage_path=os.getenv("VIDEO_STORAGE_PATH", "/tmp/igot/videos")
            ),
            modules={
                "video_analysis": ModuleConfig(
                    enabled=os.getenv("ENABLE_VIDEO_ANALYSIS", "true").lower() == "true"
                )
            }
        )
    return _settings