from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

# user_model_favorites 의 CHECK(빈 값 금지, 앞뒤 공백 금지)와 같은 규칙이라 저장 전에 다듬는다
ExecutionProvider = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1)
]


class ModelFavoriteKey(BaseModel):
    """즐겨찾기 한 건을 가리키는 값. 설정(effort 등)은 저장하지 않으므로 모델과 Provider 뿐이다."""

    model_config = ConfigDict(extra="forbid")

    model_id: int  # models 표의 model_id
    execution_provider: ExecutionProvider


class ModelFavoriteRead(ModelFavoriteKey):
    # 서비스가 돌려주는 ORM 행(user_model_favorites)을 그대로 읽는다
    model_config = ConfigDict(from_attributes=True)

    created_at: datetime


class ModelFavoriteList(BaseModel):
    items: list[ModelFavoriteRead]
