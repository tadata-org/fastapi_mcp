from pydantic import BaseModel, ConfigDict  # pragma: no cover


class BaseType(BaseModel):  # pragma: no cover
    model_config = ConfigDict(extra="forbid")  # pragma: no cover
