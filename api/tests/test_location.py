"""Pure payload coverage for consented ZIP lookup."""

import pytest

from api.location import LocationLookupError, _zip_from_nominatim_payload


def test_extracts_primary_zip_from_us_reverse_geocode() -> None:
    payload = {"address": {"country_code": "us", "postcode": "94103-1234"}}

    assert _zip_from_nominatim_payload(payload) == "94103"


def test_rejects_non_us_reverse_geocode() -> None:
    payload = {"address": {"country_code": "ca", "postcode": "M5V 3A8"}}

    with pytest.raises(LocationLookupError):
        _zip_from_nominatim_payload(payload)
