import yaml
from pydantic import BaseModel
from pathlib import Path

class ModuleConfig(BaseModel):
    enabled: bool = False
    sensitivity: float = 0.5

class Settings(BaseModel):
    modules: dict

def load_config(path="config/system_config.yaml"):
    with open(path, "r") as f:
        data = yaml.safe_load(f)
    return Settings(**data)

# Singleton pattern for settings
_settings = None
def get_settings():
    global _settings
    if _settings is None:
        _settings = load_config()
    return _settings
