from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
import json

from mokuro import __version__
from mokuro.manga_page_ocr import MangaPageOcr, InvalidImage
from mokuro.api_server.registry import (
    api_to_provider,
    build_engine_registry,
    detect_supported_formats,
    provider_lang_code,
)
from mokuro.utils import NumpyEncoder


MAX_UPLOAD_BYTES = 50 * 1024 * 1024


def create_app() -> FastAPI:
    app = FastAPI(title="Mokuro API Server")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    engine_descs, engine_avail = build_engine_registry()
    formats = detect_supported_formats()

    # warm pool of OCR engines: (provider_id, force_cpu) -> MangaPageOcr
    engine_pool: Dict[tuple, MangaPageOcr] = {}

    def _get_engine(api_name: str, force_cpu: bool) -> MangaPageOcr:
        provider = api_to_provider(api_name, engine_descs)
        key = (provider or "manga_ocr", bool(force_cpu))
        if key not in engine_pool:
            if provider and provider.startswith("owocr:"):
                mp = MangaPageOcr(force_cpu=force_cpu, disable_ocr=False, ocr_engine=provider)
            else:
                mp = MangaPageOcr(force_cpu=force_cpu, disable_ocr=False, ocr_engine="manga_ocr")
            engine_pool[key] = mp
        return engine_pool[key]

    def _ext_allowed(filename: str) -> bool:
        ext = Path(filename).suffix.lower().lstrip(".")
        return ext in set(formats)

    @app.get("/health")
    def health():
        available = [name for name, ok in engine_avail.items() if ok]
        return {"available_engines": available, "status": "healthy", "version": __version__}

    @app.get("/api/info")
    def api_info():
        endpoints = {
            "/api/ocr": {
                "method": "POST",
                "description": "Process a single image",
                "parameters": {
                    "image": "Image file (required)",
                    "ocr_engine": "One of available engines (default: manga-ocr)",
                    "force_cpu": "boolean (optional, default: false)",
                },
            },
            "/api/ocr/batch": {
                "method": "POST",
                "description": "Process multiple images",
                "parameters": {
                    "images": "Multiple image files (required)",
                    "ocr_engine": "One of available engines (default: manga-ocr)",
                    "force_cpu": "boolean (optional, default: false)",
                },
            },
        }

        engines_simple = {}
        engines_detailed = {}
        for name, desc in engine_descs.items():
            available = bool(engine_avail.get(name))
            # Human-friendly descriptions
            engines_simple[name] = desc.display_name
            engines_detailed[name] = {
                "available": available,
                "requirements": desc.requirements,
                "suggested_language_code": desc.suggested_language_code,
            }

        return {
            "name": "Mokuro API Server",
            "version": __version__,
            "supported_formats": formats,
            "max_file_size": "50MB",
            "endpoints": endpoints,
            "ocr_engines": engines_simple,
            "ocr_engines_detailed": engines_detailed,
        }

    def _bad_request(msg: str) -> JSONResponse:
        return JSONResponse(status_code=400, content={"error": msg})

    def _payload_too_large() -> JSONResponse:
        return JSONResponse(status_code=413, content={"error": "File too large. Maximum size is 50MB"})

    def _internal_error() -> JSONResponse:
        return JSONResponse(status_code=500, content={"error": "Internal server error"})

    def _bool_flag(val: Optional[str]) -> bool:
        return str(val).lower() == "true"

    def _json_response(obj) -> Response:
        data = json.dumps(obj, ensure_ascii=False, cls=NumpyEncoder).encode("utf-8")
        return Response(content=data, media_type="application/json")

    @app.post("/api/ocr")
    async def api_ocr(
        image: UploadFile = File(...),
        ocr_engine: Optional[str] = Form(None),
        force_cpu: Optional[str] = Form(None),
    ):
        try:
            data = await image.read()
            if len(data) > MAX_UPLOAD_BYTES:
                return _payload_too_large()

            engine = (ocr_engine or "manga-ocr").strip()
            if engine not in engine_avail or not engine_avail[engine]:
                available = ", ".join([n for n, ok in engine_avail.items() if ok])
                return _bad_request(f"Invalid OCR engine. Available engines: {available}")

            if not _ext_allowed(image.filename or ""):
                allowed = ", ".join(detect_supported_formats())
                return _bad_request(f"Invalid file type. Allowed types: {allowed}")

            # Write to a temp file for processing
            with tempfile.TemporaryDirectory() as td:
                tmp_path = Path(td) / (image.filename or "upload")
                tmp_path.write_bytes(data)

                mp = _get_engine(engine, _bool_flag(force_cpu))
                result = mp(tmp_path)

            # enrich
            result = dict(result)
            result["filename"] = image.filename
            result["ocr_engine"] = engine
            result["version"] = __version__
            # Optionally include language code for non-native engines
            lc = provider_lang_code(engine, engine_descs)
            if lc:
                result.setdefault("lang_code", lc)
            return _json_response(result)
        except InvalidImage:
            return _bad_request("Invalid image provided")
        except Exception as e:
            # surface server-side error for debugging while keeping shape
            try:
                import logging

                logging.getLogger(__name__).exception("/api/ocr error")
            except Exception:
                pass
            return _internal_error()

    @app.post("/api/ocr/batch")
    async def api_ocr_batch(
        images: List[UploadFile] = File(...),
        ocr_engine: Optional[str] = Form(None),
        force_cpu: Optional[str] = Form(None),
    ):
        engine = (ocr_engine or "manga-ocr").strip()
        if engine not in engine_avail or not engine_avail[engine]:
            available = ", ".join([n for n, ok in engine_avail.items() if ok])
            return _bad_request(f"Invalid OCR engine. Available engines: {available}")

        results = []
        for f in images:
            try:
                data = await f.read()
                if len(data) > MAX_UPLOAD_BYTES:
                    results.append({"filename": f.filename, "error": "File too large. Maximum size is 50MB"})
                    continue
                if not _ext_allowed(f.filename or ""):
                    allowed = ", ".join(detect_supported_formats())
                    results.append({"filename": f.filename, "error": f"Invalid file type. Allowed types: {allowed}"})
                    continue

                with tempfile.TemporaryDirectory() as td:
                    tmp_path = Path(td) / (f.filename or "upload")
                    tmp_path.write_bytes(data)
                    mp = _get_engine(engine, _bool_flag(force_cpu))
                    result = mp(tmp_path)

                item = dict(result)
                item["filename"] = f.filename
                item["ocr_engine"] = engine
                item["version"] = __version__
                lc = provider_lang_code(engine, engine_descs)
                if lc:
                    item.setdefault("lang_code", lc)
                results.append(item)
            except InvalidImage:
                results.append({"filename": f.filename, "error": "Invalid image provided"})
            except Exception:
                try:
                    import logging

                    logging.getLogger(__name__).exception("/api/ocr/batch error")
                except Exception:
                    pass
                results.append({"filename": f.filename, "error": "Internal server error"})

        return _json_response({"results": results})

    return app


def main():
    import uvicorn

    host = os.environ.get("MOKURO_API_HOST", "0.0.0.0")
    port = int(os.environ.get("MOKURO_API_PORT", "7331"))
    uvicorn.run(create_app(), host=host, port=port)
