from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any, List

from loguru import logger
import numpy as np
from paddleocr import PaddleOCR
from PIL import Image


@dataclass
class BoxText:
    text: str
    conf: float
    xmin: float
    xmax: float
    ymin: float
    ymax: float
    ymid: float
    height: float


@lru_cache(maxsize=1)
def get_ocr(lang_code: str = "en", ocr_version: str = "PP-OCRv5") -> PaddleOCR:
    return PaddleOCR(
        lang=lang_code,
        ocr_version=ocr_version,
        use_textline_orientation=True,
        use_doc_unwarping=False,
    )


def parse_results(ocr_result: list[Any]) -> List[BoxText]:
    if not ocr_result:
        return []
    items = []
    for result in ocr_result:
        texts: list[str] = result.get("rec_texts", []) or []
        scores: list[float] = result.get("rec_scores", []) or []

        boxes = result.get("rec_polys")
        if isinstance(boxes, np.ndarray):
            boxes = boxes.tolist()

        if not boxes:
            rb = result.get("rec_boxes")
            if isinstance(rb, np.ndarray):
                rb = rb.tolist()
            if rb is None:
                rb = []
            boxes = rb

        for txt, conf, box in zip(texts, scores, boxes):
            box_arr = np.asarray(box, dtype=float).reshape(-1, 2)
            xs, ys = box_arr[:, 0], box_arr[:, 1]
            xmin, xmax = float(xs.min()), float(xs.max())
            ymin, ymax = float(ys.min()), float(ys.max())
            ymid = (ymin + ymax) / 2.0
            height = ymax - ymin

            items.append(BoxText(txt, conf, xmin, xmax, ymin, ymax, ymid, height))

    return items


def group_lines(items: List[BoxText]) -> List[List[BoxText]]:
    if not items:
        return []
    items = sorted(items, key=lambda it: it.ymid)
    heights = sorted(it.height for it in items if it.height > 0)
    med_h = heights[len(heights) // 2] if heights else 16.0
    y_thresh = max(8.0, 0.6 * med_h)

    lines: List[List[BoxText]] = []
    current: List[BoxText] = [items[0]]
    current_y = items[0].ymid

    for it in items[1:]:
        if abs(it.ymid - current_y) <= y_thresh:
            current.append(it)
            current_y = (current_y * (len(current) - 1) + it.ymid) / len(current)
        else:
            lines.append(sorted(current, key=lambda x: x.xmin))
            current = [it]
            current_y = it.ymid
    lines.append(sorted(current, key=lambda x: x.xmin))
    return lines


def ocr_ui_text(
    image: Image.Image,
    lang_code: str = "en",
    ocr_version: str = "PP-OCRv5",
) -> str:
    ocr = get_ocr(lang_code, ocr_version)

    image_rgb = image.convert("RGB")

    numpydata = np.array(image_rgb)
    try:
        result = ocr.predict(
            input=numpydata,
            use_doc_orientation_classify=False,  # screenshots aren't rotated
            use_doc_unwarping=False,
            use_textline_orientation=False,
            text_det_limit_side_len=1920,
            text_det_limit_type="max",
            text_det_thresh=0.3,
            text_det_box_thresh=0.55,
            text_det_unclip_ratio=1.6,
            text_rec_score_thresh=0.85,
            return_word_box=False,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "PaddleOCR prediction failed for image {width}x{height}: {error}",
            width=image_rgb.width,
            height=image_rgb.height,
            error=exc,
        )
        return ""
    items = parse_results(result)
    if not items:
        return ""

    lines = group_lines(items)
    text_lines: list[str] = []
    for line in lines:
        words = [w.text.strip() for w in line if w.text.strip()]
        joined = " ".join(words)
        joined = (
            joined.replace(" ,", ",")
            .replace(" .", ".")
            .replace(" :", ":")
            .replace(" ;", ";")
        )
        text_lines.append(joined)
    return "\n".join(text_lines)
