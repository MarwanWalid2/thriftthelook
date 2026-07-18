"""The only module allowed to call GPT-5.6 for ThriftTheLook."""

import base64
import logging
from typing import Any, cast

from openai import APIError, AsyncOpenAI
from openai.types.responses import ResponseInputParam
from pydantic import BaseModel, Field

from api.config import Settings, get_settings

logger = logging.getLogger(__name__)


class LlmConfigurationError(RuntimeError):
    """Raised when a live model operation is requested without a key."""


class GarmentSlot(BaseModel):
    """One visible garment described by GPT-5.6 Sol."""

    garment_type: str = Field(min_length=2, max_length=60)
    colors: list[str] = Field(min_length=1, max_length=4)
    style_desc: str = Field(min_length=3, max_length=240)
    search_keywords: list[str] = Field(min_length=1, max_length=8)
    price_band_guess: str = Field(min_length=2, max_length=80)
    box: "BoundingBox | None" = None


class BoundingBox(BaseModel):
    """Normalized image coordinates for the optional GPT-box crop comparison."""

    left: float = Field(ge=0, le=1)
    top: float = Field(ge=0, le=1)
    right: float = Field(ge=0, le=1)
    bottom: float = Field(ge=0, le=1)


class OutfitDecomposition(BaseModel):
    """Strict schema returned from the single outfit decomposition request."""

    slots: list[GarmentSlot] = Field(min_length=1, max_length=6)


class StylistNarration(BaseModel):
    """Structured Luna copy for the agent receipt feed."""

    note: str = Field(min_length=3, max_length=280)
    tradeoffs: list[str] = Field(min_length=1, max_length=4)


class RerankCandidate(BaseModel):
    """One eBay candidate supplied to the batched visual reranker."""

    id: str
    title: str
    image_url: str


class CandidateAssessment(BaseModel):
    """Strict assessment of one eBay candidate by GPT-5.6 Sol."""

    id: str
    match_score: int = Field(ge=0, le=100)
    reason: str = Field(min_length=3, max_length=180)
    reject_flag: bool


class RerankResult(BaseModel):
    """Strict output for one batched per-slot vision request."""

    candidates: list[CandidateAssessment]


def _client(settings: Settings | None = None) -> AsyncOpenAI:
    active_settings = settings or get_settings()
    if not active_settings.openai_api_key:
        raise LlmConfigurationError(
            "OPENAI_API_KEY is required for live GPT-5.6 calls."
        )
    return AsyncOpenAI(api_key=active_settings.openai_api_key)


def _gemini_client(settings: Settings) -> AsyncOpenAI:
    if not settings.gemini_api_key:
        raise LlmConfigurationError(
            "OpenAI or Gemini credentials are required for live model calls."
        )
    return AsyncOpenAI(
        api_key=settings.gemini_api_key,
        base_url=settings.gemini_base_url,
    )


def _use_gemini_fallback(settings: Settings, error: Exception) -> None:
    """Select Gemini only when a configured OpenAI request cannot proceed."""

    if not settings.gemini_api_key:
        raise error
    logger.warning(
        "OpenAI model request failed; using Gemini fallback: %s",
        type(error).__name__,
    )


async def _gemini_parse[ParsedModel: BaseModel](
    settings: Settings,
    schema: type[ParsedModel],
    messages: list[dict[str, object]],
) -> ParsedModel:
    """Use Gemini's OpenAI-compatible Chat Completions structured parsing."""

    completion = await _gemini_client(settings).beta.chat.completions.parse(
        model=settings.gemini_model,
        messages=cast(Any, messages),
        response_format=schema,
    )
    parsed = completion.choices[0].message.parsed
    if not isinstance(parsed, schema):
        raise RuntimeError("Gemini did not return the expected structured response.")
    return parsed


def _gemini_image_content(image_bytes: bytes, mime_type: str) -> dict[str, object]:
    """Build an OpenAI-compatible Gemini image content part."""

    encoded_image = base64.b64encode(image_bytes).decode("ascii")
    return {
        "type": "image_url",
        "image_url": {"url": f"data:{mime_type};base64,{encoded_image}"},
    }


async def decompose_outfit(
    image_bytes: bytes,
    mime_type: str,
    settings: Settings | None = None,
) -> OutfitDecomposition:
    """Use one strict-schema GPT-5.6 Sol vision request to identify outfit slots."""

    if not image_bytes:
        raise ValueError("An outfit image is required.")
    active_settings = settings or get_settings()
    prompt = (
        "Decompose visible clothes into purchasable slots. "
        "Do not infer unseen pieces. Give resale search terms."
    )
    encoded_image = base64.b64encode(image_bytes).decode("ascii")
    try:
        response = await _client(active_settings).responses.parse(
            model=active_settings.openai_sol_model,
            reasoning={"effort": "low"},
            text_format=OutfitDecomposition,
            input=cast(
                ResponseInputParam,
                [
                    {
                        "role": "user",
                        "content": [
                            {"type": "input_text", "text": prompt},
                            {
                                "type": "input_image",
                                "image_url": f"data:{mime_type};base64,{encoded_image}",
                            },
                        ],
                    }
                ],
            ),
        )
        if not isinstance(response.output_parsed, OutfitDecomposition):
            raise RuntimeError("GPT-5.6 Sol did not return an outfit decomposition.")
        return response.output_parsed
    except (APIError, LlmConfigurationError) as error:
        _use_gemini_fallback(active_settings, error)
        return await _gemini_parse(
            active_settings,
            OutfitDecomposition,
            [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        _gemini_image_content(image_bytes, mime_type),
                    ],
                }
            ],
        )


async def narrate_look(
    budget: str,
    total: str,
    selection_summary: str,
    settings: Settings | None = None,
) -> StylistNarration:
    """Use GPT-5.6 Luna to phrase the deterministic solver outcome warmly."""

    active_settings = settings or get_settings()
    prompt = (
        "Write a concise, warm receipt note for a deterministic outfit solver. "
        f"Budget: {budget}. Delivered total: {total}. Pieces: {selection_summary}. "
        "State the meaningful budget trade-off without inventing item facts."
    )
    try:
        response = await _client(active_settings).responses.parse(
            model=active_settings.openai_luna_model,
            text_format=StylistNarration,
            input=prompt,
        )
        if not isinstance(response.output_parsed, StylistNarration):
            raise RuntimeError("GPT-5.6 Luna did not return stylist narration.")
        return response.output_parsed
    except (APIError, LlmConfigurationError) as error:
        _use_gemini_fallback(active_settings, error)
        return await _gemini_parse(
            active_settings,
            StylistNarration,
            [{"role": "user", "content": prompt}],
        )


async def rerank_slot(
    crop_bytes: bytes,
    mime_type: str,
    garment_type: str,
    dominant_colors: list[str],
    candidates: list[RerankCandidate],
    style_profile: str,
    settings: Settings | None = None,
) -> RerankResult:
    """Rank a slot crop and all candidate thumbnails in one GPT-5.6 Sol call."""

    if not crop_bytes or not candidates:
        raise ValueError("A crop and at least one candidate are required.")
    color_summary = ", ".join(dominant_colors)
    prompt = (
        f"Target garment: {garment_type}. Colors: {color_summary}. "
        f"Style profile: {style_profile}. "
        "Reject wrong garment types or dominant colors. "
        "Score similarity 0 to 100 and give one reason per candidate."
    )
    encoded_crop = base64.b64encode(crop_bytes).decode("ascii")
    content: list[dict[str, str]] = [
        {
            "type": "input_text",
            "text": prompt,
        },
        {
            "type": "input_image",
            "image_url": f"data:{mime_type};base64,{encoded_crop}",
        },
    ]
    for candidate in candidates:
        content.extend(
            [
                {
                    "type": "input_text",
                    "text": f"Candidate id {candidate.id}: {candidate.title}",
                },
                {"type": "input_image", "image_url": candidate.image_url},
            ]
        )
    active_settings = settings or get_settings()
    try:
        response = await _client(active_settings).responses.parse(
            model=active_settings.openai_sol_model,
            reasoning={"effort": "low"},
            text_format=RerankResult,
            input=cast(ResponseInputParam, [{"role": "user", "content": content}]),
        )
        if not isinstance(response.output_parsed, RerankResult):
            raise RuntimeError("GPT-5.6 Sol did not return candidate reranking.")
        return response.output_parsed
    except (APIError, LlmConfigurationError) as error:
        _use_gemini_fallback(active_settings, error)
        gemini_content: list[dict[str, object]] = [
            {"type": "text", "text": prompt},
            _gemini_image_content(crop_bytes, mime_type),
        ]
        for candidate in candidates:
            gemini_content.extend(
                [
                    {
                        "type": "text",
                        "text": f"Candidate id {candidate.id}: {candidate.title}",
                    },
                    {"type": "image_url", "image_url": {"url": candidate.image_url}},
                ]
            )
        return await _gemini_parse(
            active_settings,
            RerankResult,
            [{"role": "user", "content": gemini_content}],
        )
