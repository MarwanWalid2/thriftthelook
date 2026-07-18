"""Pure geometry and matching checks for padded clothing crops."""

from pathlib import Path

from api.llm import BoundingBox, GarmentSlot
from api.pipeline.crop import GarmentCrop, PixelBox, _normalized_box, pad_box
from api.pipeline.run import _closest_crop


def test_padding_is_clamped_to_image_edges() -> None:
    padded = pad_box(PixelBox(2, 3, 20, 30, "jacket", 0.9), 24, 32, padding=0.5)

    assert padded.left == 0
    assert padded.top == 0
    assert padded.right == 24
    assert padded.bottom == 32


def test_normalized_gpt_box_is_scaled_and_padded() -> None:
    box = _normalized_box(
        BoundingBox(left=0.25, top=0.25, right=0.75, bottom=0.75),
        200,
        100,
        "jacket",
    )

    assert (box.left, box.top, box.right, box.bottom) == (38, 19, 162, 81)
    assert box.label == "jacket"


def test_slot_matching_prefers_label_match_over_detection_order(
    tmp_path: Path,
) -> None:
    shoes_path = tmp_path / "shoes.jpg"
    jacket_path = tmp_path / "jacket.jpg"
    shoes_path.write_bytes(b"shoes")
    jacket_path.write_bytes(b"jacket")
    crops = [
        GarmentCrop(shoes_path, PixelBox(0, 0, 2, 2, "shoes", 0.9), "yolo"),
        GarmentCrop(jacket_path, PixelBox(0, 0, 2, 2, "jacket", 0.9), "yolo"),
    ]
    slot = GarmentSlot(
        garment_type="jacket",
        colors=["blue"],
        style_desc="denim jacket",
        search_keywords=["denim jacket"],
        price_band_guess="under $50",
    )

    assert _closest_crop(slot, 0, crops, b"source") == b"jacket"
