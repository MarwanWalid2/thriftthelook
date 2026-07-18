"""Coverage for consented marketplace and postcode lookup."""

import pytest

from api.location import LocationLookupError, _delivery_location_from_nominatim_payload


def test_extracts_us_marketplace_and_zip_from_reverse_geocode() -> None:
    payload = {"address": {"country_code": "us", "postcode": "94103-1234"}}

    location = _delivery_location_from_nominatim_payload(payload)

    assert location.marketplace == "EBAY_US"
    assert location.postal_code == "94103-1234"


def test_extracts_uk_marketplace_and_postcode_from_reverse_geocode() -> None:
    payload = {"address": {"country_code": "gb", "postcode": "SW1A 1AA"}}

    location = _delivery_location_from_nominatim_payload(payload)

    assert location.marketplace == "EBAY_GB"
    assert location.country == "GB"
    assert location.currency == "GBP"


def test_rejects_country_without_photo_search() -> None:
    payload = {"address": {"country_code": "ca", "postcode": "M5V 3A8"}}

    with pytest.raises(LocationLookupError):
        _delivery_location_from_nominatim_payload(payload)
