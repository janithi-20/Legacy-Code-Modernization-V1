from typing import Literal
from pydantic import BaseModel, Field


class TradeIn(BaseModel):
    symbol: str = Field(min_length=1, max_length=12)
    side: Literal["BUY", "SELL"]
    quantity: int = Field(gt=0)
    price: float = Field(gt=0)