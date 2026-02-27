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

    def test_settings_is_singleton_at_module_level(self, monkeypatch):
        """The module-level ``settings`` object must be a Settings instance."""
        monkeypatch.setenv("MODEL_ARN", "arn:aws:bedrock:us-east-1::foundation-model/singleton")
        import age_calculator.config as cfg_module
        importlib.reload(cfg_module)
        from age_calculator.config import Settings
        assert isinstance(cfg_module.settings, Settings)

    def test_settings_has_exactly_one_field(self, monkeypatch):
        """Settings exposes only model_arn — no undocumented fields."""
        monkeypatch.setenv("MODEL_ARN", "arn:aws:bedrock:us-east-1::foundation-model/test")
        import age_calculator.config as cfg_module
        importlib.reload(cfg_module)
        fields = list(cfg_module.Settings.model_fields.keys())
        assert fields == ["model_arn"], (
            f"Settings has unexpected fields: {fields}. "
            "Only 'model_arn' should be declared."
        )

    def test_settings_rejects_extra_fields(self, monkeypatch):
        """Settings must not silently absorb undeclared fields (extra='forbid' behaviour)."""
        monkeypatch.setenv("MODEL_ARN", "arn:aws:bedrock:us-east-1::foundation-model/test")
        from pydantic import ValidationError
        import age_calculator.config as cfg_module
        importlib.reload(cfg_module)
        with pytest.raises((ValidationError, TypeError)):
            cfg_module.Settings(model_arn="arn:aws:bedrock:us-east-1::foundation-model/test", unexpected="bad")

    def test_env_file_encoding_is_utf8(self):
        """model_config must specify UTF-8 so non-ASCII ARN characters are handled correctly."""
        from age_calculator.config import Settings
        assert Settings.model_config["env_file_encoding"] == "utf-8"
