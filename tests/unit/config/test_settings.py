"""Unit tests for age_calculator.config.Settings."""

import importlib
import pytest
from pydantic import ValidationError


@pytest.mark.unit
class TestSettings:
    def test_loads_model_arn_from_env(self, monkeypatch):
        monkeypatch.setenv("MODEL_ARN", "arn:aws:bedrock:us-east-1::foundation-model/my-model")
        import age_calculator.config as cfg_module
        importlib.reload(cfg_module)
        assert cfg_module.Settings().model_arn == "arn:aws:bedrock:us-east-1::foundation-model/my-model"

    def test_raises_when_model_arn_absent(self, monkeypatch):
        monkeypatch.delenv("MODEL_ARN", raising=False)
        # Also remove any .env influence by pointing at a non-existent file
        from pydantic_settings import BaseSettings, SettingsConfigDict
        from pydantic import Field

        class IsolatedSettings(BaseSettings):
            model_config = SettingsConfigDict(env_file=".nonexistent", case_sensitive=False)
            model_arn: str = Field(..., alias="MODEL_ARN")

        with pytest.raises(ValidationError):
            IsolatedSettings()

    def test_model_arn_attribute_matches_env(self, monkeypatch):
        expected = "arn:aws:bedrock:us-west-2::foundation-model/test"
        monkeypatch.setenv("MODEL_ARN", expected)
        import age_calculator.config as cfg_module
        importlib.reload(cfg_module)
        assert cfg_module.Settings().model_arn == expected

    def test_case_insensitive_env_var(self, monkeypatch):
        monkeypatch.setenv("model_arn", "arn:aws:bedrock:eu-west-1::foundation-model/lower")
        import age_calculator.config as cfg_module
        importlib.reload(cfg_module)
        s = cfg_module.Settings()
        assert s.model_arn == "arn:aws:bedrock:eu-west-1::foundation-model/lower"
