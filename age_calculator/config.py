"""Runtime configuration for the age_calculator package.

Settings are loaded in priority order:
  1. Environment variables (highest priority)
  2. .env file in the project root
  3. Validation error if a required variable is missing

Usage::

    from age_calculator.config import settings

    print(settings.model_arn)
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    model_arn: str = Field(
        ...,
        alias="MODEL_ARN",
        description="AWS Bedrock application inference profile ARN.",
    )


settings = Settings()
