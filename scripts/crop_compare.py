"""Write YOLO crops and optionally GPT-5.6 box crops for visual comparison."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.llm import OutfitDecomposition
from api.pipeline.crop import CropDependencyError, detect_yolo_crops, gpt_box_crops

logger = logging.getLogger(__name__)


def _load_slots(path: Path) -> OutfitDecomposition:
    """Parse a saved strict decomposition response without a model call."""

    payload: Any = json.loads(path.read_text(encoding="utf-8"))
    return OutfitDecomposition.model_validate(payload)


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare ThriftTheLook crop strategies.")
    parser.add_argument("image", type=Path)
    parser.add_argument("decomposition", type=Path, help="Saved strict slots JSON")
    parser.add_argument("--output", type=Path, default=Path("crop-comparison"))
    parser.add_argument(
        "--gpt-boxes", action="store_true", help="Also write normalized GPT box crops"
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    if not args.image.is_file() or not args.decomposition.is_file():
        raise ValueError("Both image and decomposition JSON must exist.")
    try:
        yolo = detect_yolo_crops(args.image, args.output / "yolo")
        logger.info("Wrote %d YOLO crops", len(yolo))
        if args.gpt_boxes:
            decomposition = _load_slots(args.decomposition)
            gpt = gpt_box_crops(args.image, decomposition.slots, args.output / "gpt")
            logger.info("Wrote %d GPT-box crops", len(gpt))
    except CropDependencyError as error:
        raise SystemExit(str(error)) from error


if __name__ == "__main__":
    main()
