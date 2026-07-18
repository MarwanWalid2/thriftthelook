"""Typed models shared across the ThriftTheLook API."""

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Listing(BaseModel):
    """A normalized eBay listing, with delivery cost kept separate and explicit."""

    model_config = ConfigDict(frozen=True)

    id: str
    title: str
    price: Decimal = Field(ge=0)
    shipping: Decimal | None = Field(default=None, ge=0)
    total: Decimal | None = Field(default=None, ge=0)
    image_url: str | None = None
    item_url: str | None = None
    condition: str | None = None
    currency: str = "USD"

    @model_validator(mode="before")
    @classmethod
    def set_delivery_total(cls, values: object) -> object:
        """Only present a total when eBay supplied a shipping price."""

        if not isinstance(values, dict):
            return values
        price = values.get("price")
        shipping = values.get("shipping")
        if price is None or shipping is None:
            values["total"] = None
            return values
        try:
            values["total"] = Decimal(str(price)) + Decimal(str(shipping))
        except ArithmeticError:
            values["total"] = None
        return values
