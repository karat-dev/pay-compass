"""Redact card numbers, MRZ, faces and payment QR codes before a photo is kept.

Pillow re-encodes the pixels into a new JPEG, which drops EXIF. OpenCV finds
faces (Haar cascade shipped with the library) and QR codes. Tesseract reads
the text so card numbers and MRZ lines can be covered. If a detector does not
run, or its confidence is below community.photo.confidence_min, the photo is
not published and the original is not kept.
"""

from __future__ import annotations

import io
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from PIL import Image, ImageDraw

from database.community import need, require_community
from database.config_error import ConfigError


def redact_bytes(raw: bytes, config: Dict[str, Any]) -> Dict[str, Any]:
    require_community(config)
    photo = need(config, "community", "photo")
    if len(raw) > photo["max_bytes"]:
        return _unpublished(photo, photo["detector_failed_confidence"])
    try:
        image = Image.open(io.BytesIO(raw))
        image.load()
    except Exception:
        return _unpublished(photo, photo["detector_failed_confidence"])
    clean = _pixels_only(image)
    detected = _detect(clean, config)
    if detected["confidence"] < photo["confidence_min"]:
        return _unpublished(photo, detected["confidence"])
    _paint(clean, detected["regions"], photo)
    return {
        "publish": True,
        "status": photo["clean_status"],
        "image": _jpeg(clean, photo),
        "confidence": detected["confidence"],
        "path": None,
    }


def consume_upload(source: Path, config: Dict[str, Any], directory: Path, photo_id: str) -> Dict[str, Any]:
    """Read an upload, delete it immediately, and keep only a redacted JPEG."""
    path = Path(source)
    raw = path.read_bytes()
    path.unlink()
    result = redact_bytes(raw, config)
    if result["publish"] and result.get("image"):
        directory.mkdir(parents=True, exist_ok=True)
        dest = directory / f"{photo_id}.jpg"
        dest.write_bytes(result["image"])
        result["path"] = str(dest)
    return result


def _unpublished(photo: Dict[str, Any], confidence: Any) -> Dict[str, Any]:
    return {
        "publish": False,
        "status": photo["review_status"],
        "image": None,
        "confidence": confidence,
        "path": None,
    }


def _pixels_only(image: Image.Image) -> Image.Image:
    rgb = image.convert("RGB")
    clean = Image.new("RGB", rgb.size)
    clean.paste(rgb)
    return clean


def _jpeg(image: Image.Image, photo: Dict[str, Any]) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=int(photo["jpeg_quality"]))
    return buffer.getvalue()


def _paint(image: Image.Image, regions: List[tuple], photo: Dict[str, Any]) -> None:
    color = tuple(photo["redaction_rgb"])
    draw = ImageDraw.Draw(image)
    for box in regions:
        draw.rectangle(box, fill=color)


def _detect(image: Image.Image, config: Dict[str, Any]) -> Dict[str, Any]:
    photo = need(config, "community", "photo")
    regions: List[tuple] = []
    confidences = []
    for detector in (_detect_qr, _detect_faces, _detect_text):
        found = detector(image, photo)
        regions.extend(found["regions"])
        confidences.append(found["confidence"])
    if not confidences:
        return {"regions": regions, "confidence": photo["detector_failed_confidence"]}
    return {"regions": regions, "confidence": min(confidences)}


def _detect_qr(image: Image.Image, photo: Dict[str, Any]) -> Dict[str, Any]:
    try:
        import cv2
        import numpy as np
    except Exception:
        return {"regions": [], "confidence": photo["detector_failed_confidence"]}
    try:
        array = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
        data, points, _straight = cv2.QRCodeDetector().detectAndDecode(array)
        regions = []
        if points is not None:
            for polygon in points:
                xs = [pair[0] for pair in polygon]
                ys = [pair[1] for pair in polygon]
                regions.append((min(xs), min(ys), max(xs), max(ys)))
        _ = data
        return {"regions": regions, "confidence": photo["detector_ran_confidence"]}
    except Exception:
        return {"regions": [], "confidence": photo["detector_failed_confidence"]}


def _detect_faces(image: Image.Image, photo: Dict[str, Any]) -> Dict[str, Any]:
    try:
        import cv2
        import numpy as np
    except Exception:
        return {"regions": [], "confidence": photo["detector_failed_confidence"]}
    try:
        cascade_path = cv2.data.haarcascades + photo["face_cascade"]
        cascade = cv2.CascadeClassifier(cascade_path)
        if cascade.empty():
            return {"regions": [], "confidence": photo["detector_failed_confidence"]}
        gray = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2GRAY)
        boxes = cascade.detectMultiScale(
            gray,
            scaleFactor=photo["face_scale_factor"],
            minNeighbors=photo["face_min_neighbors"],
        )
        regions = [(int(x), int(y), int(x + w), int(y + h)) for x, y, w, h in boxes]
        return {"regions": regions, "confidence": photo["detector_ran_confidence"]}
    except Exception:
        return {"regions": [], "confidence": photo["detector_failed_confidence"]}


def _detect_text(image: Image.Image, photo: Dict[str, Any]) -> Dict[str, Any]:
    try:
        import pytesseract
    except Exception:
        return {"regions": [], "confidence": photo["detector_failed_confidence"]}
    try:
        data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
    except Exception:
        return {"regions": [], "confidence": photo["detector_failed_confidence"]}
    scale = photo["ocr_confidence_scale"]
    if scale == 0:
        raise ConfigError("community.photo.ocr_confidence_scale не может быть нулём")
    unknown = photo["ocr_unknown_confidence"]
    texts = data.get("text") or []
    confs = data.get("conf") or []
    left = data.get("left") or []
    top = data.get("top") or []
    width = data.get("width") or []
    height = data.get("height") or []
    pattern = re.compile(rf"\d{{{int(photo['card_min_digits'])},{int(photo['card_max_digits'])}}}")
    marker = str(photo["mrz_marker"]) * int(photo["mrz_min_chevrons"])
    regions = []
    scores = []
    for index, text in enumerate(texts):
        token = str(text or "").strip()
        if not token:
            continue
        try:
            score = float(confs[index])
        except (TypeError, ValueError, IndexError):
            score = photo["detector_failed_confidence"]
        if score == unknown:
            continue
        scores.append(score / scale)
        compact = token.replace(" ", "")
        if pattern.search(compact) or marker in token:
            regions.append((
                left[index],
                top[index],
                left[index] + width[index],
                top[index] + height[index],
            ))
    if not scores:
        return {"regions": regions, "confidence": photo["empty_ocr_confidence"]}
    return {"regions": regions, "confidence": min(scores)}
