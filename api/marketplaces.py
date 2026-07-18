"""The eBay marketplaces where ThriftTheLook supports photo-led searches."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Marketplace:
    """A supported delivery market with its eBay and postal context."""

    id: str
    country_code: str
    name: str
    currency: str


PHOTO_MARKETPLACES: tuple[Marketplace, ...] = (
    Marketplace("EBAY_US", "US", "United States", "USD"),
    Marketplace("EBAY_GB", "GB", "United Kingdom", "GBP"),
    Marketplace("EBAY_DE", "DE", "Germany", "EUR"),
    Marketplace("EBAY_AU", "AU", "Australia", "AUD"),
)

_BY_ID = {marketplace.id: marketplace for marketplace in PHOTO_MARKETPLACES}
_BY_COUNTRY = {
    marketplace.country_code.casefold(): marketplace
    for marketplace in PHOTO_MARKETPLACES
}


def marketplace_for_id(value: str) -> Marketplace | None:
    """Return an enabled market by the public eBay marketplace identifier."""

    return _BY_ID.get(value.upper())


def marketplace_for_country(value: str) -> Marketplace | None:
    """Return an enabled market by an ISO 3166-1 alpha-2 country code."""

    return _BY_COUNTRY.get(value.casefold())
