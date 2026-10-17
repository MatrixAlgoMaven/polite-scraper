
from pydantic import BaseModel, HttpUrl, Field


class Book(BaseModel):
    title: str = Field(min_length=1)
    product_url: HttpUrl
    price_text: str = Field(min_length=1)
    price_gbp: float = Field(gt=0)
    
    availability_text: str = Field(min_length=1)
    rating_text: str = Field(min_length=1)
    description: str = Field(min_length=1)
    source_page: int = Field(ge=1, le=3)
    fetched_at: str = Field(min_length=1)
