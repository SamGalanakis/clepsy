import asyncio
import re

from loguru import logger
from unidecode import unidecode

from baml_client.async_client import b
import baml_client.types as baml_types
from clepsy import utils
from clepsy.config import config
from clepsy.entities import (
    DesktopInputScreenshotEvent,
    ImageProcessingApproach,
    LLMConfig,
    ProcessedDesktopCheckScreenshotEventOCR,
    ProcessedDesktopCheckScreenshotEventVLM,
    UserSettings,
)
from clepsy.llm import create_client_registry
from clepsy.modules.ocr.ocr import ocr_ui_text
from clepsy.modules.pii.pii import (
    DEFAULT_PII_ENTITY_TYPES,
    anonymize_text,
)
from clepsy.utils import pil_image_to_baml


_WHITESPACE_RE = re.compile(r"[ \t]+")
_NON_INFO_LINE_RE = re.compile(r"^[0-9\W_]+$")

paddle_ocr_semaphore = asyncio.Semaphore(1)


def prepare_ocr_text(
    raw_text: str,
    *,
    max_words: int = 150,
    max_chars: int = 1200,
) -> str:
    if not raw_text:
        return ""

    normalized_lines: list[str] = []
    seen: set[str] = set()

    for raw_line in raw_text.splitlines():
        transliterated = unidecode(raw_line)
        ascii_line = transliterated.encode("ascii", "ignore").decode("ascii")
        ascii_line = _WHITESPACE_RE.sub(" ", ascii_line).strip()

        if not ascii_line:
            continue

        digit_ratio = sum(1 for ch in ascii_line if ch.isdigit()) / len(ascii_line)
        if digit_ratio > 0.8:
            continue

        if len(ascii_line) < 3:
            continue

        if _NON_INFO_LINE_RE.fullmatch(ascii_line):
            continue

        if ascii_line in seen:
            continue

        seen.add(ascii_line)
        normalized_lines.append(ascii_line)

    cleaned_text = "\n".join(normalized_lines)

    if not cleaned_text:
        return ""

    try:
        truncated = utils.truncate_words(cleaned_text, max_words)
    except AssertionError:
        truncated = cleaned_text

    if len(truncated) > max_chars:
        cut = truncated[:max_chars]
        last_space = cut.rfind(" ")
        truncated = cut[:last_space] if last_space > 0 else cut

    return truncated


async def process_desktop_check(
    desktop_check_input: DesktopInputScreenshotEvent,
    user_settings: UserSettings,
) -> ProcessedDesktopCheckScreenshotEventVLM | ProcessedDesktopCheckScreenshotEventOCR:
    match user_settings.image_processing_approach:
        case ImageProcessingApproach.VLM:
            if user_settings.image_model_config:
                return await process_desktop_check_vlm(
                    desktop_check_input,
                    image_model_config=user_settings.image_model_config,
                )
            logger.error(
                "Image model config is not set in user settings, but VLM approach is selected. Using OCR instead."
            )
            return await process_desktop_check_using_ocr(
                desktop_check_input,
                text_model_config=user_settings.text_model_config,
            )

        case ImageProcessingApproach.OCR:
            return await process_desktop_check_using_ocr(
                desktop_check_input,
                text_model_config=user_settings.text_model_config,
            )
        case _:
            raise ValueError(
                f"Unknown image processing approach: {user_settings.image_processing_approach}"
            )


async def process_desktop_check_using_ocr(
    desktop_check_input: DesktopInputScreenshotEvent,
    text_model_config: LLMConfig,
) -> ProcessedDesktopCheckScreenshotEventOCR:
    async with paddle_ocr_semaphore:
        raw_ocr_text = await asyncio.to_thread(
            ocr_ui_text,
            image=desktop_check_input.screenshot,
            lang_code="en",
            ocr_version="PP-OCRv5",
        )

    cleaned_ocr_text = prepare_ocr_text(raw_ocr_text)
    ocr_text = cleaned_ocr_text if cleaned_ocr_text else raw_ocr_text.strip()

    n_words = utils.count_words(ocr_text)

    if ocr_text:
        ocr_text = await asyncio.to_thread(
            anonymize_text,
            text=ocr_text,
            entity_types=DEFAULT_PII_ENTITY_TYPES,
            threshold=config.gliner_pii_threshold,
        )

    if n_words > 50:
        client = create_client_registry(llm_config=text_model_config, name="TextClient")

        image_text = await b.InterpretImageDesktopOCR(
            baml_types.InterpretImageDesktopOCRInput(
                ocr_text=ocr_text,
                title=desktop_check_input.active_window.title,
                app_name=desktop_check_input.active_window.app_name,
            ),
            baml_options={"client_registry": client},
        )

        image_text_post_processed_by_llm = True
    else:
        image_text = ocr_text
        image_text_post_processed_by_llm = False

    return ProcessedDesktopCheckScreenshotEventOCR(
        image_text=image_text,
        active_window=desktop_check_input.active_window,
        timestamp=desktop_check_input.timestamp,
        image_text_post_processed_by_llm=image_text_post_processed_by_llm,
    )


async def process_desktop_check_vlm(
    desktop_check_input: DesktopInputScreenshotEvent,
    *,
    image_model_config: LLMConfig,
) -> ProcessedDesktopCheckScreenshotEventVLM:
    screenshot = utils.resize_image_with_thumbnail(
        image=desktop_check_input.screenshot,
        target_height=config.screenshot_max_size_vlm[0],
        target_width=config.screenshot_max_size_vlm[1],
        inplace=True,
    )

    active_window = baml_types.WindowInfo(
        title=desktop_check_input.active_window.title,
        app_name=desktop_check_input.active_window.app_name,
    )
    desktop_check_input_llm_call = baml_types.DesktopCheckInput(
        screenshot=pil_image_to_baml(screenshot),
        active_window=active_window,
    )

    client = create_client_registry(
        llm_config=image_model_config,
        name="MainClientDesktopCheck",
        set_primary=True,
    )

    response = await b.DescribeDesktopScreenshot(
        input=desktop_check_input_llm_call, baml_options={"client_registry": client}
    )

    if isinstance(response, Exception):
        raise response

    return ProcessedDesktopCheckScreenshotEventVLM(
        llm_description=response,
        active_window=desktop_check_input.active_window,
        timestamp=desktop_check_input.timestamp,
    )
