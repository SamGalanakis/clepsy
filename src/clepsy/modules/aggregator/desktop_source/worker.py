import asyncio
import re

from aiocache import cached
from baml_py.errors import BamlError
from loguru import logger
from unidecode import unidecode

from baml_client.async_client import b
import baml_client.types as baml_types
from clepsy import utils
from clepsy.config import config
from clepsy.db import get_db_connection
from clepsy.db.queries import select_user_settings
from clepsy.entities import (
    BamlErrorSignal,
    DesktopInputEvent,
    DesktopInputScreenshotEvent,
    ImageProcessingApproach,
    LLMConfig,
    ProcessedDesktopCheckScreenshotEventOCR,
    ProcessedDesktopCheckScreenshotEventVLM,
    ShutdownEvent,
    UserSettings,
)
from clepsy.event_bus import EventBus
from clepsy.llm import create_client_registry
from clepsy.modules.ocr.ocr import ocr_ui_text
from clepsy.modules.pii.pii import (
    DEFAULT_PII_ENTITY_TYPES,
    anonymize_text,
)
from clepsy.utils import pil_image_to_baml
from clepsy.workers import AbstractWorker


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
            lang_code="en",  # TODO: make configurable in UI or use multi lang by default
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
        target_height=config.screenshot_size[0],
        target_width=config.screenshot_size[1],
        inplace=True,
    )

    active_window = baml_types.WindowInfo(
        title=desktop_check_input.active_window.title,
        app_name=desktop_check_input.active_window.app_name,
        is_active=desktop_check_input.active_window.is_active,
    )
    desktop_check_input_llm_call = baml_types.DesktopCheckInput(
        screenshot=pil_image_to_baml(screenshot),
        active_window=active_window,
    )

    client = create_client_registry(
        llm_config=image_model_config,
        name="MainClientDesktopCheck",
        set_primary=True,
        #  max_tokens=500,  # TODO: find a way to reliably use this for thinking models
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


class DesktopCheckWorker(AbstractWorker):
    def __init__(
        self,
        event_bus: EventBus,
        input_queue: asyncio.Queue[DesktopInputEvent | ShutdownEvent],
        name: str = "DesktopCheckWorker",
        max_parallelism: int = 3,
    ):
        super().__init__(input_queue, name)
        self.event_bus = event_bus
        self.sem = asyncio.Semaphore(max_parallelism)
        self.tasks = set()

    async def handle_event(
        self,
        evt: DesktopInputScreenshotEvent,
        settings: UserSettings,
    ):
        async with self.sem:
            try:
                processed = await process_desktop_check(evt, user_settings=settings)
            except BamlError as e:
                logger.exception(
                    "BAML error processing screenshot for app '{app}' (title='{title}') at {ts}: {error}",
                    app=evt.active_window.app_name,
                    title=evt.active_window.title,
                    ts=evt.timestamp,
                    error=e,
                )
                error_signal = BamlErrorSignal(exception=e)
                self.signal(error_signal)
                return
            except Exception as e:  # noqa: BLE001
                logger.exception(
                    "Unexpected error processing screenshot for app '{app}' (title='{title}') at {ts}: {error}",
                    app=evt.active_window.app_name,
                    title=evt.active_window.title,
                    ts=evt.timestamp,
                    error=e,
                )
                return
            else:
                self.signal_success()
                await self.event_bus.publish(processed)
                logger.trace("Screenshot processed")
            finally:
                # Always mark the queue item as done
                self.input_queue.task_done()

    async def run(self):
        user_settings_cached = cached(ttl=60)(select_user_settings)

        async with get_db_connection(include_uuid_func=False) as conn:
            while not self.shutdown_received:
                desktop_check_input_event = await self.input_queue.get()

                if isinstance(desktop_check_input_event, ShutdownEvent):
                    self.shutdown_received = True
                    # Mark the shutdown event as processed and exit loop
                    self.input_queue.task_done()
                    break

                if not isinstance(
                    desktop_check_input_event, DesktopInputScreenshotEvent
                ):
                    # Unknown/unsupported event for this worker
                    logger.warning(
                        "DesktopCheckWorker received unsupported event type: {}",
                        type(desktop_check_input_event),
                    )
                    self.input_queue.task_done()
                    continue

                # Cache the current settings for this specific event
                user_settings = await user_settings_cached(conn)

                task = asyncio.create_task(
                    self.handle_event(desktop_check_input_event, user_settings)
                )
                self.tasks.add(task)
                task.add_done_callback(self.tasks.discard)

            # After breaking out of the loop, wait for all in-flight tasks to finish
            if self.tasks:
                await asyncio.gather(*self.tasks, return_exceptions=True)
