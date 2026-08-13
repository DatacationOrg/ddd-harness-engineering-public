from pathlib import Path
from typing import ClassVar
from urllib.parse import urlparse

from pydantic import HttpUrl, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).parents[1]


class Settings(BaseSettings):
    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env"
    )

    # Defaults to empty so importing the package, collecting tests, and running
    # CI all work without a key. The key is only required to talk to the model;
    # `require_api_key` is where that is enforced, with a message worth reading.
    MICROSOFT_FOUNDRY_KEY: SecretStr = SecretStr("")
    MICROSOFT_FOUNDRY_ENDPOINT: HttpUrl = HttpUrl(
        "https://datacation-deep-dive.services.ai.azure.com/api/projects/proj-default"
    )
    MICROSOFT_FOUNDRY_DEPLOYMENT: str = "gpt-5.6-luna"
    MICROSOFT_FOUNDRY_API_VERSION: str = "preview"

    @property
    def OPENAI_BASE_URL(self) -> str:
        parsed_endpoint = urlparse(str(self.MICROSOFT_FOUNDRY_ENDPOINT))
        return f"{parsed_endpoint.scheme}://{parsed_endpoint.netloc}/openai/v1"

    def require_api_key(self) -> SecretStr:
        if not self.MICROSOFT_FOUNDRY_KEY.get_secret_value():
            raise RuntimeError(
                "MICROSOFT_FOUNDRY_KEY is not set. "
                f"Copy .env.example to {PROJECT_ROOT / '.env'} and add your key."
            )
        return self.MICROSOFT_FOUNDRY_KEY


env = Settings()  # pyright: ignore[reportCallIssue]
