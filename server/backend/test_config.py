from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class TestSettings(BaseSettings):
    allowed_origins: str | list[str] = Field(default_factory=list)

    @field_validator("allowed_origins", mode="before")
    def parse_allowed_origins(cls, value):
        if isinstance(value, str):
            return [v.strip() for v in value.split(",") if v.strip()]
        return value

print(TestSettings(_env_file=None, allowed_origins="http://localhost:3000,http://localhost:8080").allowed_origins)
