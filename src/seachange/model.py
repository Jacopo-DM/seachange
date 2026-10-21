"""The base class for seachange's records."""

from pydantic import BaseModel, ConfigDict


class Model(BaseModel):
    """Base for every record in this package: immutable, no unknown fields."""

    model_config = ConfigDict(frozen=True, extra="forbid")
