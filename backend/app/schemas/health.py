"""health 응답 모델."""

from typing import Literal

from pydantic import BaseModel


class HealthRead(BaseModel):
    status: Literal["ok"]
