from pydantic import BaseModel, ConfigDict, Field


class TitleResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=r"^t[0-9]+$")
    male_es: str = Field(min_length=1)
    female_es: str = Field(min_length=1)
    category: str = Field(min_length=1)


class ToolOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    results: list[TitleResult]
