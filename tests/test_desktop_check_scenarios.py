from datetime import datetime, timezone
from typing import Union

from loguru import logger
from PIL import Image
from pydantic import BaseModel
import pytest

from baml_client.async_client import b
import baml_client.types as baml_types
from clepsy.entities import (
    Bbox,
    DesktopInputScreenshotEvent,
    LLMConfig,
    ProcessedDesktopCheckScreenshotEventOCR,
    ProcessedDesktopCheckScreenshotEventVLM,
    WindowInfo,
)
from clepsy.llm import create_client_registry
from clepsy.modules.aggregator.desktop_source.worker import (
    process_desktop_check_using_ocr,
    process_desktop_check_vlm,
)
from clepsy.utils import pil_image_to_baml
from tests.llm_configs import (
    build_openrouter_config,
    gemini_2_5,
    llm_as_judge_config,
    openrouter_model_names,
)


if llm_as_judge_config is None:
    pytest.skip(
        "GOOGLE_API_KEY environment variable not set; skipping LLM desktop check scenarios.",
        allow_module_level=True,
    )


llm_config_params = []

if gemini_2_5 is not None:
    llm_config_params.append(pytest.param(gemini_2_5, id="gemini_2_5"))

for model_name in openrouter_model_names:
    openrouter_config = build_openrouter_config(model_name)
    if openrouter_config is not None:
        llm_config_params.append(
            pytest.param(openrouter_config, id=model_name.replace("/", "_"))
        )

if not llm_config_params:
    pytest.skip(
        "No LLM configs available; skipping LLM desktop check scenarios.",
        allow_module_level=True,
    )


class DesktopTestScenario(BaseModel):
    __test__ = False
    name: str
    input_event: DesktopInputScreenshotEvent
    expected_description: str
    description: str


async def validate_with_llm(
    generated_event: Union[
        ProcessedDesktopCheckScreenshotEventVLM, ProcessedDesktopCheckScreenshotEventOCR
    ],
    expected_description: str,
    input_event: DesktopInputScreenshotEvent,
    text_model_config: LLMConfig,
) -> baml_types.ValidationResultWithReasoning:
    client = create_client_registry(
        llm_config=text_model_config, name="ValidationClient", set_primary=True
    )

    if isinstance(generated_event, ProcessedDesktopCheckScreenshotEventVLM):
        generated_text = generated_event.llm_description
    else:
        generated_text = generated_event.image_text

    validation_result = await b.ValidateDesktopCheck(
        generated_description=generated_text,
        expected_description=expected_description,
        input=baml_types.DesktopCheckInput(
            screenshot=pil_image_to_baml(input_event.screenshot),
            active_window=baml_types.WindowInfo(
                title=input_event.active_window.title,
                app_name=input_event.active_window.app_name,
                is_active=input_event.active_window.is_active,
            ),
        ),
        baml_options={"client_registry": client},
    )
    return validation_result


test_scenarios = [
    DesktopTestScenario(
        name="vscode_with_multiple_panes",
        input_event=DesktopInputScreenshotEvent(
            screenshot=Image.open("test_images/vscode.png"),
            active_window=WindowInfo(
                title="test_aggregator_llm.py - clepsy [Dev Container: Existing Dockerfile @ desktop-linux]",
                app_name="Visual Studio Code",
                is_active=True,
                bbox=Bbox(left=0, top=0, width=1920, height=1080),
            ),
            timestamp=datetime.now(timezone.utc),
        ),
        expected_description="User is writing python tests in VSCode.",
        description="A test case with VSCode open, showing a test file being edited.",
    ),
    DesktopTestScenario(
        name="spotify_main_view",
        input_event=DesktopInputScreenshotEvent(
            screenshot=Image.open("test_images/spotify.png"),
            active_window=WindowInfo(
                title="Spotify",
                app_name="Spotify",
                is_active=True,
                bbox=Bbox(left=0, top=0, width=1920, height=1080),
            ),
            timestamp=datetime.now(timezone.utc),
        ),
        expected_description="User is listening to music on Spotify.",
        description="A test case with Spotify open, showing the main view.",
    ),
    DesktopTestScenario(
        name="vscode_coding",
        input_event=DesktopInputScreenshotEvent(
            screenshot=Image.open("test_images/vscode_coding.png"),
            active_window=WindowInfo(
                title="aggregator_worker.py - clepsy [Dev Container: Existing Dockerfile @ desktop-linux]",
                app_name="Visual Studio Code",
                is_active=True,
                bbox=Bbox(left=0, top=0, width=1920, height=1080),
            ),
            timestamp=datetime.now(timezone.utc),
        ),
        expected_description="User is writing python code in VSCode.",
        description="A test case with VSCode open, showing a python file being edited.",
    ),
    DesktopTestScenario(
        name="nordvpn_main_view",
        input_event=DesktopInputScreenshotEvent(
            screenshot=Image.open("test_images/nordvpn.png"),
            active_window=WindowInfo(
                title="NordVPN",
                app_name="NordVPN",
                is_active=True,
                bbox=Bbox(left=0, top=0, width=1920, height=1080),
            ),
            timestamp=datetime.now(timezone.utc),
        ),
        expected_description="User is using NordVPN.",
        description="A test case with NordVPN open, showing the main view.",
    ),
    DesktopTestScenario(
        name="league_client_main_view",
        input_event=DesktopInputScreenshotEvent(
            screenshot=Image.open("test_images/league_client.png"),
            active_window=WindowInfo(
                title="League of Legends",
                app_name="League of Legends",
                is_active=True,
                bbox=Bbox(left=0, top=0, width=1920, height=1080),
            ),
            timestamp=datetime.now(timezone.utc),
        ),
        expected_description="User is in the League of Legends client.",
        description="A test case with the League of Legends client open, showing the main view.",
    ),
    DesktopTestScenario(
        name="steam_popup_main_view",
        input_event=DesktopInputScreenshotEvent(
            screenshot=Image.open("test_images/steam_popup.png"),
            active_window=WindowInfo(
                title="Steam",
                app_name="Steam",
                is_active=True,
                bbox=Bbox(left=0, top=0, width=1920, height=1080),
            ),
            timestamp=datetime.now(timezone.utc),
        ),
        expected_description="User is viewing a Steam summer sale popup.",
        description="A test case with a Steam popup open, showing the summer sale.",
    ),
    DesktopTestScenario(
        name="vlc_blank_main_view",
        input_event=DesktopInputScreenshotEvent(
            screenshot=Image.open("test_images/vlc_blank.png"),
            active_window=WindowInfo(
                title="VLC media player",
                app_name="VLC media player",
                is_active=True,
                bbox=Bbox(left=0, top=0, width=1920, height=1080),
            ),
            timestamp=datetime.now(timezone.utc),
        ),
        expected_description="User has VLC media player open.",
        description="A test case with VLC media player open, showing a blank screen.",
    ),
    DesktopTestScenario(
        name="steam_main_view",
        input_event=DesktopInputScreenshotEvent(
            screenshot=Image.open("test_images/steam.png"),
            active_window=WindowInfo(
                title="Steam",
                app_name="Steam",
                is_active=True,
                bbox=Bbox(left=0, top=0, width=1920, height=1080),
            ),
            timestamp=datetime.now(timezone.utc),
        ),
        expected_description="User is browsing the Steam store.",
        description="A test case with Steam open, showing the main store page.",
    ),
    DesktopTestScenario(
        name="file_explorer_main_view",
        input_event=DesktopInputScreenshotEvent(
            screenshot=Image.open("test_images/file_explorer.png"),
            active_window=WindowInfo(
                title="3dprint",
                app_name="File Explorer",
                is_active=True,
                bbox=Bbox(left=0, top=0, width=1920, height=1080),
            ),
            timestamp=datetime.now(timezone.utc),
        ),
        expected_description="User is browsing files in File Explorer.",
        description="A test case with File Explorer open, showing a directory.",
    ),
    DesktopTestScenario(
        name="razer_synapse_main_view",
        input_event=DesktopInputScreenshotEvent(
            screenshot=Image.open("test_images/razer.png"),
            active_window=WindowInfo(
                title="Razer Synapse",
                app_name="Razer Synapse",
                is_active=True,
                bbox=Bbox(left=0, top=0, width=1920, height=1080),
            ),
            timestamp=datetime.now(timezone.utc),
        ),
        expected_description="User is viewing the Razer Synapse application.",
        description="A test case with Razer Synapse open, showing the dashboard.",
    ),
    DesktopTestScenario(
        name="forticlient_vpn_main_view",
        input_event=DesktopInputScreenshotEvent(
            screenshot=Image.open("test_images/forticlient_vpn.png"),
            active_window=WindowInfo(
                title="FortiClient - Zero Trust Fabric Agent",
                app_name="FortiClient",
                is_active=True,
                bbox=Bbox(left=0, top=0, width=1920, height=1080),
            ),
            timestamp=datetime.now(timezone.utc),
        ),
        expected_description="User is viewing the FortiClient VPN application.",
        description="A test case with FortiClient VPN open, showing the main view.",
    ),
    DesktopTestScenario(
        name="calculator_main_view",
        input_event=DesktopInputScreenshotEvent(
            screenshot=Image.open("test_images/calculator.png"),
            active_window=WindowInfo(
                title="Calculator",
                app_name="Calculator",
                is_active=True,
                bbox=Bbox(left=0, top=0, width=1920, height=1080),
            ),
            timestamp=datetime.now(timezone.utc),
        ),
        expected_description="User is using the Calculator application.",
        description="A test case with Calculator open, showing the standard view.",
    ),
    DesktopTestScenario(
        name="notepad_elephants_main_view",
        input_event=DesktopInputScreenshotEvent(
            screenshot=Image.open("test_images/notepad_elephants.png"),
            active_window=WindowInfo(
                title="My thesis about pink transparent e",
                app_name="Notepad",
                is_active=True,
                bbox=Bbox(left=0, top=0, width=1920, height=1080),
            ),
            timestamp=datetime.now(timezone.utc),
        ),
        expected_description="User is writing a thesis in Notepad.",
        description="A test case with Notepad open, showing a thesis about pink transparent elephants.",
    ),
    DesktopTestScenario(
        name="paint_main_view",
        input_event=DesktopInputScreenshotEvent(
            screenshot=Image.open("test_images/paint.png"),
            active_window=WindowInfo(
                title="Untitled - Paint",
                app_name="Paint",
                is_active=True,
                bbox=Bbox(left=0, top=0, width=1920, height=1080),
            ),
            timestamp=datetime.now(timezone.utc),
        ),
        expected_description="User is drawing in Paint.",
        description="A test case with Paint open, showing a drawing of a house and sun.",
    ),
    DesktopTestScenario(
        name="discord_chat_view",
        input_event=DesktopInputScreenshotEvent(
            screenshot=Image.open("test_images/discord-2880x1620-8b18742c6a01.jpg"),
            active_window=WindowInfo(
                title="Discord",
                app_name="Discord",
                is_active=True,
                bbox=Bbox(left=0, top=0, width=2880, height=1620),
            ),
            timestamp=datetime.now(timezone.utc),
        ),
        expected_description="User is chatting on Discord.",
        description="A test case with Discord open, showing a chat channel.",
    ),
    DesktopTestScenario(
        name="task_manager_view",
        input_event=DesktopInputScreenshotEvent(
            screenshot=Image.open("test_images/task_manager.png"),
            active_window=WindowInfo(
                title="Task Manager",
                app_name="Task Manager",
                is_active=True,
                bbox=Bbox(left=0, top=0, width=1280, height=720),
            ),
            timestamp=datetime.now(timezone.utc),
        ),
        expected_description="User is viewing Task Manager.",
        description="A test case with Task Manager open, showing processes.",
    ),
    DesktopTestScenario(
        name="windows_store_main_view",
        input_event=DesktopInputScreenshotEvent(
            screenshot=Image.open("test_images/windows_store.png"),
            active_window=WindowInfo(
                title="Microsoft Store",
                app_name="Microsoft Store",
                is_active=True,
                bbox=Bbox(left=0, top=0, width=2560, height=1440),
            ),
            timestamp=datetime.now(timezone.utc),
        ),
        expected_description="User is browsing the Microsoft Store.",
        description="A test case with Microsoft Store open, showing the main view.",
    ),
    DesktopTestScenario(
        name="docker_desktop_main_view",
        input_event=DesktopInputScreenshotEvent(
            screenshot=Image.open("test_images/docker_desktop.png"),
            active_window=WindowInfo(
                title="Docker Desktop",
                app_name="Docker Desktop",
                is_active=True,
                bbox=Bbox(left=0, top=0, width=2560, height=1440),
            ),
            timestamp=datetime.now(timezone.utc),
        ),
        expected_description="User is viewing Docker Desktop.",
        description="A test case with Docker Desktop open, showing the containers view.",
    ),
    DesktopTestScenario(
        name="whatsapp_desktop_main_view",
        input_event=DesktopInputScreenshotEvent(
            screenshot=Image.open("test_images/whatsapp-windows.png"),
            active_window=WindowInfo(
                title="WhatsApp",
                app_name="WhatsApp",
                is_active=True,
                bbox=Bbox(left=0, top=0, width=1920, height=1080),
            ),
            timestamp=datetime.now(timezone.utc),
        ),
        expected_description="User is using WhatsApp Desktop.",
        description="A test case with WhatsApp Desktop open, showing the main chat view.",
    ),
    DesktopTestScenario(
        name="adobe_photoshop_main_view",
        input_event=DesktopInputScreenshotEvent(
            screenshot=Image.open("test_images/Adobe-Photoshop-Screenshot.png"),
            active_window=WindowInfo(
                title="Adobe Photoshop",
                app_name="Adobe Photoshop",
                is_active=True,
                bbox=Bbox(left=0, top=0, width=2560, height=1440),
            ),
            timestamp=datetime.now(timezone.utc),
        ),
        expected_description="User is editing an image in Adobe Photoshop.",
        description="A test case with Adobe Photoshop open, showing an image being edited.",
    ),
]


pytestmark = pytest.mark.llm


@pytest.mark.asyncio
@pytest.mark.parametrize("test_scenario", test_scenarios, ids=lambda s: s.name)
@pytest.mark.parametrize("llm_config", llm_config_params)
async def test_process_desktop_check_vlm(test_scenario, llm_config):
    logger.info(f"Testing VLM Scenario: {test_scenario.name} with {llm_config.model}")
    logger.info(f"Description: {test_scenario.description}")

    generated_event = await process_desktop_check_vlm(
        test_scenario.input_event, image_model_config=llm_config
    )

    validation_result = await validate_with_llm(
        generated_event=generated_event,
        expected_description=test_scenario.expected_description,
        input_event=test_scenario.input_event,
        text_model_config=llm_as_judge_config,
    )
    is_valid = validation_result.validation_result.grade >= 0.5

    logger.info(f"LLM Validation Result: {is_valid}")
    logger.debug(f"LLM Reasoning: {validation_result.reasoning}")

    assert is_valid, (
        f"LLM validation failed for scenario {test_scenario.name}: "
        f"{validation_result.validation_result.error_description}"
    )

    if validation_result.validation_result.grade < 0.7:
        logger.warning(
            f"LLM validation for scenario {test_scenario.name} is not perfect: "
            f"{validation_result.validation_result.error_description}"
        )

    logger.info(f"✓ Scenario {test_scenario.name} passed validation")
    logger.info(f"Reasoning: {validation_result.reasoning}")
    logger.info(f"Generated Description: {generated_event.llm_description}")


@pytest.mark.asyncio
@pytest.mark.parametrize("test_scenario", test_scenarios, ids=lambda s: s.name)
@pytest.mark.parametrize("llm_config", llm_config_params)
async def test_process_desktop_check_using_ocr(test_scenario, llm_config):
    logger.info(f"Testing OCR Scenario: {test_scenario.name} with {llm_config.model}")
    logger.info(f"Description: {test_scenario.description}")

    generated_event = await process_desktop_check_using_ocr(
        test_scenario.input_event, text_model_config=llm_config
    )

    validation_result = await validate_with_llm(
        generated_event=generated_event,
        expected_description=test_scenario.expected_description,
        input_event=test_scenario.input_event,
        text_model_config=llm_as_judge_config,
    )
    is_valid = validation_result.validation_result.grade >= 0.5

    logger.info(f"LLM Validation Result: {is_valid}")
    logger.debug(f"LLM Reasoning: {validation_result.reasoning}")

    assert is_valid, (
        f"LLM validation failed for scenario {test_scenario.name}: "
        f"{validation_result.validation_result.error_description}"
    )

    if validation_result.validation_result.grade < 0.7:
        logger.warning(
            f"LLM validation for scenario {test_scenario.name} is not perfect: "
            f"{validation_result.validation_result.error_description}"
        )

    logger.info(f"✓ Scenario {test_scenario.name} passed validation")
    logger.info(f"Reasoning: {validation_result.reasoning}")
    logger.info(f"Generated Text: {generated_event.image_text}")
