from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

_REPO_ROOT = Path(__file__).resolve().parents[2]
_ENV_FILE = _REPO_ROOT / '.env' if (_REPO_ROOT / 'pyproject.toml').is_file() else Path.cwd() / '.env'


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        populate_by_name=True,
        env_file=_ENV_FILE,
        extra='ignore',
    )

    pf_domain: str = Field(default='', alias='PF_DOMAIN')
    pf_username: str = Field(default='', alias='PF_USERNAME')
    pf_password: SecretStr = Field(default=SecretStr(''), alias='PF_PASSWORD')
    pf_lang: str = Field(default='Ru', alias='PF_LANG')
    browser_bin: str = Field(default='', alias='PF_BROWSER_BIN')
    browser_timeout: float = Field(default=60.0, alias='PF_BROWSER_TIMEOUT')
    rps: float = Field(default=1.0, alias='PF_RPS')
    log_level: str = Field(default='INFO', alias='LOGGING_LEVEL')


SETTINGS = Settings()
