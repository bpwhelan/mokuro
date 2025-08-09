from collections import Counter
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Sequence, Optional, Union

import fire
from loguru import logger

from mokuro import MokuroGenerator
from mokuro import __version__
from mokuro.legacy.overlay_generator import generate_legacy_html
from mokuro.volume import VolumeCollection


def run(
    *paths: Optional[Sequence[Union[str, Path]]],
    parent_dir: Optional[Union[str, Path]] = None,
    pretrained_model_name_or_path: str = "kha-white/manga-ocr-base",
    force_cpu: bool = False,
    disable_confirmation: bool = False,
    disable_ocr: bool = False,
    ocr_engine: str = "manga_ocr",
    owocr_config: Optional[Union[str, Path]] = None,
    ignore_errors: bool = False,
    no_cache: bool = False,
    unzip: bool = False,
    legacy_html: bool = True,
    as_one_file: bool = True,
    version: bool = False,
):
    """
    Process manga volumes with mokuro.

    Basic usage:
        mokuro /path/to/Volume --disable_confirmation

    OWOCR (multiple OCR engines):
        1) Install once (all compatible engines):
           pip install -U "mokuro[owocr]"

        2) Select an engine with --ocr-engine:
           - manga_ocr (default): native Manga OCR (no extra install; no lang_code)
           - owocr:auto           : auto-picks the best available for your OS
           - owocr:<provider>     : choose a specific provider from the list below
           - Multiple providers: comma-separated list (run sequentially)
             Example: --ocr-engine "owocr:mangaocr,glens,easyocr"

        Providers (name -> code):
           - owocr:mangaocr -> mo   (Manga OCR via owocr)
           - owocr:easyocr  -> eo   (EasyOCR)
           - owocr:rapidocr -> ro   (RapidOCR)
           - owocr:glens    -> gl   (Google Lens)
           - owocr:glensweb -> gw   (Google Lens Web)
           - owocr:gvision  -> gv   (Google Vision; needs ~/.config/google_vision.json)
           - owocr:azure    -> az   (Azure Image Analysis; needs endpoint/api_key)
           - owocr:bing     -> bo   (Bing)
           - owocr:ocrspace -> os   (OCRSpace; needs api_key)
           - owocr:avision  -> av   (Apple Vision; macOS 13+)
           - owocr:alivetext-> al   (Apple Live Text; macOS 13+)
           - owocr:winrtocr -> wo   (WinRT OCR; Windows 10+)
           - owocr:oneocr   -> oo   (OneOCR; Windows 10+)

        Provider config file (JSON) via --owocr_config:
           Examples:
             {"azure": {"endpoint": "https://...", "api_key": "..."}}
             {"oneocr": {"url": "http://<win-vm>:<port>"}, "winrtocr": {"url": "http://..."}}

        Output tagging and cache layout:
           - Non-native engines include "lang_code" in per-page JSONs and in the top-level .mokuro file.
           - Cache is written under _ocr/<VolumeName>.<code>/ (e.g., _ocr/Volume 001.gl/).

    Args:
        paths: Paths to manga volumes. Volume can be a directory, a zip file or a cbz file.
        parent_dir: Parent directory to scan for volumes. If provided, all volumes inside this directory will be processed.
        pretrained_model_name_or_path: Name or path of the manga-ocr model.
        force_cpu: Force the use of CPU even if CUDA is available.
        disable_confirmation: Disable confirmation prompt. If False, the user will be prompted to confirm the list of volumes to be processed.
        disable_ocr: Disable OCR processing. Generate mokuro/HTML files without OCR results.
        ocr_engine: OCR backend to use (see OWOCR section above for options).
        owocr_config: Optional path to a JSON file with provider-specific configuration.
        ignore_errors: Continue processing volumes even if an error occurs.
        no_cache: Do not use cached OCR results from previous runs (_ocr directories).
        unzip: Extract volumes in zip/cbz format in their original location.
        legacy_html: Enable legacy HTML output. If True, acts as if --unzip is True.
        as_one_file: Applies only to legacy HTML. If False, generate separate CSS and JS files instead of embedding them in the HTML file.
        version: Print the version of mokuro and exit.
    """

    if version:
        print(f"{__version__}")
        return

    if disable_ocr:
        logger.info("Running with OCR disabled")

    if legacy_html:
        logger.warning(
            "Legacy HTML output is deprecated and will not be further developed. "
            "It's recommended to use .mokuro format and web reader instead. "
            "Legacy HTML will be disabled by default in the future. To explicitly enable it, run with option --legacy-html."
        )
        # legacy HTML works only with unzipped output
        unzip = True

    logger.info("Scanning paths...")

    paths_ = []
    for path in paths:
        path_normalized = Path(str(path)).expanduser().absolute()

        try:
            path_valid = path_normalized.exists()
        except OSError:
            path_valid = False

        if path_valid:
            paths_.append(path_normalized)
        else:
            logger.error(f"Invalid path: {path_normalized}")
            return

    paths = paths_

    if parent_dir is not None:
        for p in Path(parent_dir).expanduser().absolute().iterdir():
            if (
                p not in paths
                and (p.is_dir() and p.stem != "_ocr")
                or (p.is_file() and p.suffix.lower() in {".zip", ".cbz"})
            ):
                paths.append(p)

    vc = VolumeCollection()

    for path_in in paths:
        vc.add_path_in(path_in)

    if len(vc) == 0:
        logger.error("Found no paths to process. Did you set the paths correctly?")
        return

    for title in vc.titles.values():
        title.set_uuid()

    status_counter = Counter()

    print(f"\nFound {len(vc)} volumes:\n")

    for volume in vc:
        print(volume)
        status_counter[volume.status] += 1

    msg = "\nEach of the paths above will be treated as one volume.\n"
    print(msg)

    if not disable_confirmation:
        inp = input("\nContinue? [yes/no]")
        if inp.lower() not in ("y", "yes"):
            return

    # Load optional owocr config JSON file if provided
    owocr_cfg_dict = None
    if owocr_config is not None:
        try:
            cfg_path = Path(str(owocr_config)).expanduser().absolute()
            import json as _json

            with cfg_path.open("r", encoding="utf-8") as _f:
                owocr_cfg_dict = _json.load(_f)
        except Exception:
            logger.exception("Failed to load owocr_config; proceeding without it")

    # Expand engines (support multiple owocr providers comma-separated)
    def _expand_engines(engine_str: str):
        if not engine_str:
            return ["manga_ocr"]
        s = engine_str.strip()
        if "," in s:
            if s.startswith("owocr:"):
                suffix = s.split(":", 1)[1]
                providers = [p.strip() for p in suffix.split(",") if p.strip()]
                return [f"owocr:{p}" for p in providers]
            else:
                return [e.strip() for e in s.split(",") if e.strip()]
        return [s]

    engines_to_run = _expand_engines(ocr_engine)

    # OS compatibility pre-checks to skip incompatible engines gracefully
    def _is_engine_compatible(eng: str) -> bool:
        try:
            import sys as _sys
            if not eng.startswith("owocr:"):
                return True
            prov = eng.split(":", 1)[1].strip().lower()
            # macOS-only providers
            if prov in ("avision", "alivetext") and _sys.platform != "darwin":
                return False
            # Windows-only providers
            if prov in ("winrtocr", "winrt", "oneocr") and _sys.platform != "win32":
                return False
        except Exception:
            pass
        return True

    with TemporaryDirectory() as tmp_dir:
        tmp_dir = Path(tmp_dir)

        # unzip == True means that zipped volumes will be unzipped in their original location
        # in that case, we don't use a temporary directory
        if unzip:
            tmp_dir = None

        total_success = 0
        for eng in engines_to_run:
            if not _is_engine_compatible(eng):
                logger.warning(f"Skipping engine {eng}: not supported on this OS")
                continue
            logger.info(f"Running engine: {eng}")
            mg = MokuroGenerator(
                pretrained_model_name_or_path=pretrained_model_name_or_path,
                force_cpu=force_cpu,
                disable_ocr=disable_ocr,
                ocr_engine=eng,
                owocr_config=owocr_cfg_dict,
            )

            num_sucessful = 0
            for i, volume in enumerate(vc):
                logger.info(f"Processing {i + 1}/{len(vc)}: {volume.path_in}")

                try:
                    volume.unzip(tmp_dir)

                    # process and get engine-specific cache dir/code for downstream generators
                    code = mg._engine_code_from_arg(mg.ocr_engine)
                    base_cache_dir = volume.path_ocr_cache
                    cache_dir = (
                        base_cache_dir if not code else base_cache_dir.parent / (base_cache_dir.name + f".{code}")
                    )

                    mg.process_volume(volume, ignore_errors=ignore_errors, no_cache=no_cache)
                    if legacy_html:
                        generate_legacy_html(
                            volume,
                            as_one_file=as_one_file,
                            ignore_errors=ignore_errors,
                            cache_dir=cache_dir,
                            lang_code=code,
                        )

                except Exception:
                    logger.exception(f"Error while processing {volume.path_in}")
                else:
                    num_sucessful += 1

            total_success += num_sucessful
            logger.info(f"Engine {eng}: processed successfully {num_sucessful}/{len(vc)}")

        logger.info(f"Processed successfully across engines: {total_success}/{len(vc) * len(engines_to_run)}")


if __name__ == "__main__":
    fire.Fire(run)
