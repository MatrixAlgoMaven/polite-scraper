
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field, HttpUrl


class Book(BaseModel):
    title: Annotated[str, Field(min_length=1)]
    product_url: HttpUrl
    price_text: Annotated[str, Field(min_length=1)]
    price_gbp: Annotated[float, Field(gt=0)]
    availability_text: Annotated[str, Field(min_length=1)]
    rating_text: Annotated[str, Field(min_length=1)]
    description: Annotated[str, Field(min_length=1)]
    source_page: Annotated[int, Field(ge=1, le=3)]
    fetched_at: datetime
