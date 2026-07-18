"""YOLO clothing crops with a GPT-box comparison fallback."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from api.llm import BoundingBox, GarmentSlot


class CropDependencyError(RuntimeError):
    """Raised when live crop support was not installed with the vision extra."""


@dataclass(frozen=True, slots=True)
class PixelBox:
    """An image-space detection box."""

    left: int
    top: int
    right: int
    bottom: int
    label: str
    confidence: float


@dataclass(frozen=True, slots=True)
class GarmentCrop:
    """A persisted crop that may be matched to a decomposed garment slot."""

    path: Path
    box: PixelBox
    source: str


def pad_box(box: PixelBox, width: int, height: int, padding: float = 0.12) -> PixelBox:
    """Pad and clamp a detected box without making a crop exceed the source image."""

    x_padding = round((box.right - box.left) * padding)
    y_padding = round((box.bottom - box.top) * padding)
    return PixelBox(
        left=max(0, box.left - x_padding),
        top=max(0, box.top - y_padding),
        right=min(width, box.right + x_padding),
        bottom=min(height, box.bottom + y_padding),
        label=box.label,
        confidence=box.confidence,
    )


def detect_yolo_crops(
    image_path: Path,
    output_directory: Path,
    model_name: str = "kesimeg/yolov8n-clothing-detection",
    padding: float = 0.12,
) -> list[GarmentCrop]:
    """Run YOLOv8n clothing detection and write padded crops to disk.

    Install the optional vision extra before calling this in live mode:
    ``uv sync --extra vision``.
    """

    try:
        from PIL import Image  # type: ignore[import-not-found]
        from ultralytics import YOLO  # type: ignore[import-not-found]
    except ImportError as error:
        raise CropDependencyError(
            "Install the vision extra before running YOLO clothing crops."
        ) from error

    output_directory.mkdir(parents=True, exist_ok=True)
    image = Image.open(image_path).convert("RGB")
    model = YOLO(model_name)
    prediction = model(image, verbose=False)[0]
    names = prediction.names
    crops: list[GarmentCrop] = []
    for index, raw_box in enumerate(prediction.boxes):
        left, top, right, bottom = (round(value) for value in raw_box.xyxy[0].tolist())
        class_id = int(raw_box.cls[0].item())
        label = str(names[class_id])
        box = pad_box(
            PixelBox(left, top, right, bottom, label, float(raw_box.conf[0].item())),
            image.width,
            image.height,
            padding,
        )
        crop_path = output_directory / f"yolo-{index}-{box.label}.jpg"
        crop = image.crop((box.left, box.top, box.right, box.bottom))
        crop.save(crop_path, quality=92)
        crops.append(GarmentCrop(crop_path, box, "yolo"))
    return crops


def gpt_box_crops(
    image_path: Path,
    slots: list[GarmentSlot],
    output_directory: Path,
) -> list[GarmentCrop]:
    """Write crop candidates from normalized GPT-5.6 boxes for visual comparison."""

    try:
        from PIL import Image
    except ImportError as error:
        raise CropDependencyError(
            "Install the vision extra before writing GPT crops."
        ) from error

    output_directory.mkdir(parents=True, exist_ok=True)
    image = Image.open(image_path).convert("RGB")
    crops: list[GarmentCrop] = []
    for index, slot in enumerate(slots):
        if slot.box is None:
            continue
        box = _normalized_box(slot.box, image.width, image.height, slot.garment_type)
        crop_path = output_directory / f"gpt-{index}-{slot.garment_type}.jpg"
        crop = image.crop((box.left, box.top, box.right, box.bottom))
        crop.save(crop_path, quality=92)
        crops.append(GarmentCrop(crop_path, box, "gpt"))
    return crops


def _normalized_box(
    box: BoundingBox,
    width: int,
    height: int,
    label: str,
) -> PixelBox:
    left, right = sorted((round(box.left * width), round(box.right * width)))
    top, bottom = sorted((round(box.top * height), round(box.bottom * height)))
    return pad_box(PixelBox(left, top, right, bottom, label, 1.0), width, height)
