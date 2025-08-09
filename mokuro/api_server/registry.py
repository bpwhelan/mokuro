from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PIL import Image


@dataclass
class EngineDescriptor:
    api_name: str
    provider_id: str  # e.g. 'manga_ocr' or 'owocr:glens'
    display_name: str
    suggested_language_code: Optional[str]
    requirements: List[str]
    os_only: Optional[str] = None  # 'darwin' | 'win32' | None


def _env_truthy(val: Optional[str]) -> bool:
    return str(val).lower() in {"1", "true", "yes", "on"}


def detect_supported_formats() -> List[str]:
    # Base formats always handled
    formats = {"jpg", "jpeg", "png", "webp"}
    # Detect optional ones via Pillow registered extensions
    try:
        if ".avif" in Image.registered_extensions():
            formats.add("avif")
    except Exception:
        pass
    try:
        if ".jxl" in Image.registered_extensions():
            formats.add("jxl")
    except Exception:
        pass
    return sorted(formats)


def _has_module(mod: str) -> bool:
    try:
        __import__(mod)
        return True
    except Exception:
        return False


def _has_gvision_credentials() -> bool:
    cfg = Path.home() / ".config" / "google_vision.json"
    return cfg.is_file()


def _has_azure_credentials() -> bool:
    return bool(os.environ.get("AZURE_VISION_ENDPOINT") and os.environ.get("AZURE_VISION_API_KEY"))


def _has_ocrspace_key() -> bool:
    return bool(os.environ.get("OCRSPACE_API_KEY"))


def build_engine_registry() -> Tuple[Dict[str, EngineDescriptor], Dict[str, bool]]:
    """
    Returns (descriptors_by_api_name, availability_by_api_name)
    Availability reflects OS constraints and import/credential presence at runtime.
    """
    descriptors: List[EngineDescriptor] = [
        EngineDescriptor(
            api_name="manga-ocr",
            provider_id="manga_ocr",
            display_name="Manga OCR",
            suggested_language_code="mo",
            requirements=["manga-ocr", "torch", "transformers"],
        ),
        EngineDescriptor(
            api_name="lens",
            provider_id="owocr:glens",
            display_name="Google Lens",
            suggested_language_code="gl",
            requirements=["owocr[lens]", "betterproto==2.0.0b7"],
        ),
        EngineDescriptor(
            api_name="lensweb",
            provider_id="owocr:glensweb",
            display_name="Google Lens (web)",
            suggested_language_code="gw",
            requirements=["owocr[lensweb]", "pyjson5"],
        ),
        EngineDescriptor(
            api_name="easyocr",
            provider_id="owocr:easyocr",
            display_name="EasyOCR",
            suggested_language_code="eo",
            requirements=["owocr[easyocr]", "easyocr"],
        ),
        EngineDescriptor(
            api_name="rapidocr",
            provider_id="owocr:rapidocr",
            display_name="RapidOCR",
            suggested_language_code="ro",
            requirements=["owocr[rapidocr]", "onnxruntime", "rapidocr_onnxruntime"],
        ),
        EngineDescriptor(
            api_name="gvision",
            provider_id="owocr:gvision",
            display_name="Google Vision",
            suggested_language_code="gv",
            requirements=["owocr[gvision]", "google-cloud-vision", "~/.config/google_vision.json"],
        ),
        EngineDescriptor(
            api_name="azure",
            provider_id="owocr:azure",
            display_name="Azure Image Analysis",
            suggested_language_code="az",
            requirements=["owocr[azure]", "AZURE_VISION_ENDPOINT", "AZURE_VISION_API_KEY"],
        ),
        EngineDescriptor(
            api_name="bing",
            provider_id="owocr:bing",
            display_name="Bing",
            suggested_language_code="bo",
            requirements=["owocr"],
        ),
        EngineDescriptor(
            api_name="ocrspace",
            provider_id="owocr:ocrspace",
            display_name="OCRSpace",
            suggested_language_code="os",
            requirements=["owocr", "OCRSPACE_API_KEY"],
        ),
        EngineDescriptor(
            api_name="avision",
            provider_id="owocr:avision",
            display_name="Apple Vision",
            suggested_language_code="av",
            requirements=["owocr", "pyobjc"],
            os_only="darwin",
        ),
        EngineDescriptor(
            api_name="alivetext",
            provider_id="owocr:alivetext",
            display_name="Apple Live Text",
            suggested_language_code="al",
            requirements=["owocr", "pyobjc"],
            os_only="darwin",
        ),
        EngineDescriptor(
            api_name="winrtocr",
            provider_id="owocr:winrtocr",
            display_name="WinRT OCR",
            suggested_language_code="wo",
            requirements=["owocr[winocr]"],
            os_only="win32",
        ),
        EngineDescriptor(
            api_name="oneocr",
            provider_id="owocr:oneocr",
            display_name="OneOCR",
            suggested_language_code="oo",
            requirements=["oneocr"],
            os_only="win32",
        ),
    ]

    desc_by_name = {d.api_name: d for d in descriptors}

    avail: Dict[str, bool] = {}
    for d in descriptors:
        # OS constraint
        if d.os_only and d.os_only != sys.platform:
            avail[d.api_name] = False
            continue
        # Core mapping import check
        ok = True
        if d.provider_id.startswith("owocr:"):
            ok = _has_module("owocr.ocr")
        elif d.provider_id == "manga_ocr":
            ok = _has_module("manga_ocr")

        # Additional deps per engine
        if ok and d.api_name == "lens":
            ok = _has_module("betterproto")
        if ok and d.api_name == "lensweb":
            ok = _has_module("pyjson5")
        if ok and d.api_name == "easyocr":
            ok = _has_module("easyocr")
        if ok and d.api_name == "rapidocr":
            ok = _has_module("rapidocr_onnxruntime")
        if ok and d.api_name == "gvision":
            ok = _has_module("google.cloud.vision") and _has_gvision_credentials()
        if ok and d.api_name == "azure":
            ok = _has_module("azure.ai.vision.imageanalysis") and _has_azure_credentials()
        if ok and d.api_name == "ocrspace":
            ok = _has_ocrspace_key()

        avail[d.api_name] = bool(ok)

    return desc_by_name, avail


def api_to_provider(api_name: str, descs: Dict[str, EngineDescriptor]) -> Optional[str]:
    d = descs.get(api_name)
    return d.provider_id if d else None


def provider_lang_code(api_name: str, descs: Dict[str, EngineDescriptor]) -> Optional[str]:
    d = descs.get(api_name)
    return d.suggested_language_code if d else None

