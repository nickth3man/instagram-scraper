from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class AppConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    output_dir: Path = Path("data")
    limit: int | None = Field(default=None, ge=1)
