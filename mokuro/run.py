from collections import Counter
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Sequence, Optional, Union, List
import zipfile
import re

import fire
from loguru import logger
from natsort import natsorted

from mokuro import MokuroGenerator
from mokuro import __version__
from mokuro.legacy.overlay_generator import generate_legacy_html
from mokuro.volume import VolumeCollection


def filter_volumes_by_position(volumes: List[Path], first: Optional[int] = None, last: Optional[int] = None) -> List[Path]:
    """
    Filter a list of volumes based on position (first N and/or last N).
    
    Args:
        volumes: List of volume paths to filter
        first: Take only the first N volumes
        last: Take only the last N volumes
    
    Returns:
        Filtered list of volume paths
    """
    if not volumes:
        return volumes
    
    # Sort volumes naturally to ensure consistent ordering
    sorted_volumes = natsorted(volumes, key=lambda p: p.name)
    
    # Apply filters
    selected = set()
    
    if first is not None and first > 0:
        selected.update(sorted_volumes[:first])
    
    if last is not None and last > 0:
        selected.update(sorted_volumes[-last:])
    
    # If neither first nor last specified, return all
    if first is None and last is None:
        return sorted_volumes
    
    # Return filtered volumes in original order
    return [v for v in sorted_volumes if v in selected]


def create_volume_zip(volume, zip_output_path=None):
    """
    Create a zip file containing the volume directory and all corresponding mokuro files.
    
    Args:
        volume: Volume object to zip
        zip_output_path: Optional path for the output zip file. If None, creates zip next to volume.
    
    Returns:
        Path to the created zip file
    """
    # Determine the volume directory path
    if volume.path_in.is_dir():
        volume_dir = volume.path_in
    else:
        # If it's already a zip/cbz, skip creating another zip
        logger.warning(f"Skipping zip creation for {volume.path_in} as it's already an archive")
        return None
    
    # Find all mokuro files for this volume in the parent directory
    # This includes *.mokuro, *.gl.mokuro, *.mo.mokuro, etc.
    parent_dir = volume.path_title
    mokuro_files = []
    
    # Look for all mokuro files that match this volume's name
    volume_name = volume_dir.name
    for mokuro_file in parent_dir.glob(f"{volume_name}*.mokuro"):
        if mokuro_file.is_file():
            mokuro_files.append(mokuro_file)
    
    # Create output zip path if not provided
    if zip_output_path is None:
        zip_output_path = parent_dir / f"{volume_name}_mokuro.zip"
    
    logger.info(f"Creating zip file: {zip_output_path}")
    logger.info(f"Including volume directory: {volume_dir}")
    logger.info(f"Including {len(mokuro_files)} mokuro file(s)")
    
    # Create the zip file
    with zipfile.ZipFile(zip_output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        # Add the volume directory and all its contents
        for file_path in volume_dir.rglob('*'):
            if file_path.is_file():
                # Calculate the archive name (relative path from parent)
                arcname = file_path.relative_to(parent_dir)
                zf.write(file_path, arcname)
        
        # Add all mokuro files
        for mokuro_file in mokuro_files:
            arcname = mokuro_file.relative_to(parent_dir)
            zf.write(mokuro_file, arcname)
    
    logger.info(f"Zip file created successfully: {zip_output_path}")
    return zip_output_path


def run(
    *paths: Optional[Sequence[Union[str, Path]]],
    parent_dir: Optional[Union[str, Path]] = None,
    root_dir: bool = False,
    first: Optional[int] = None,
    last: Optional[int] = None,
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
    zip: bool = False,
    skip_pattern: Optional[str] = None,
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
        root_dir: Process every folder in the current directory as a series (each folder is treated as a parent_dir).
        first: Process only the first N volumes from each series (position-based, works with any naming scheme).
        last: Process only the last N volumes from each series (position-based, works with any naming scheme).
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
        zip: After processing, create a zip file containing the volume directory and all corresponding mokuro files (*.mokuro, *.gl.mokuro, *.mo.mokuro, etc.).
        skip_pattern: Regex pattern to match page filenames that should be skipped during OCR (e.g., ".*_credits\\.png$" to skip credit pages). Stub JSON files will still be created for compatibility.
        version: Print the version of mokuro and exit.
    """

    if version:
        print(f"{__version__}")
        return

    if disable_ocr:
        logger.info("Running with OCR disabled")
    
    if skip_pattern:
        logger.info(f"Using skip pattern: {skip_pattern}")
        try:
            re.compile(skip_pattern)
        except re.error as e:
            logger.error(f"Invalid regex pattern: {e}")
            return
    
    if first is not None and first <= 0:
        logger.error("--first must be a positive number")
        return
    
    if last is not None and last <= 0:
        logger.error("--last must be a positive number")
        return
    
    if first or last:
        filter_msg = []
        if first:
            filter_msg.append(f"first {first}")
        if last:
            filter_msg.append(f"last {last}")
        logger.info(f"Volume filtering enabled: {' and '.join(filter_msg)} volumes per series")

    if legacy_html:
        logger.warning(
            "Legacy HTML output is deprecated and will not be further developed. "
            "It's recommended to use .mokuro format and web reader instead. "
            "Legacy HTML will be disabled by default in the future. To explicitly enable it, run with option --legacy-html."
        )
        # legacy HTML works only with unzipped output
        unzip = True

    logger.info("Scanning paths...")

    # Handle root_dir mode - process each folder as a series
    if root_dir:
        if paths:
            logger.error("Cannot use --root_dir with explicit paths. Use either --root_dir alone or provide paths.")
            return
        if parent_dir is not None:
            logger.error("Cannot use --root_dir with --parent_dir. Use one or the other.")
            return
        
        # Get current directory
        current_dir = Path.cwd()
        logger.info(f"Root directory mode: Processing all series in {current_dir}")
        
        # Find all directories in current directory (each is a series)
        series_dirs = []
        for item in current_dir.iterdir():
            if item.is_dir() and not item.name.startswith('.') and item.name != '_ocr':
                series_dirs.append(item)
        
        if not series_dirs:
            logger.error("No series directories found in current directory")
            return
        
        logger.info(f"Found {len(series_dirs)} series to process:")
        for series in sorted(series_dirs):
            logger.info(f"  - {series.name}")
        
        # Process each series directory
        all_paths = []
        for series_dir in series_dirs:
            # Find all volumes in this series directory
            series_volumes = []
            for p in series_dir.iterdir():
                if (p.is_dir() and p.stem != "_ocr") or (p.is_file() and p.suffix.lower() in {".zip", ".cbz"}):
                    series_volumes.append(p)
            
            # Apply first/last filters to this series
            if series_volumes:
                filtered_volumes = filter_volumes_by_position(series_volumes, first, last)
                if first or last:
                    logger.info(f"  {series_dir.name}: {len(filtered_volumes)}/{len(series_volumes)} volumes selected")
                all_paths.extend(filtered_volumes)
        
        paths = all_paths
        logger.info(f"Total volumes to process: {len(paths)}")
        
    else:
        # Normal mode - process provided paths
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
            parent_volumes = []
            for p in Path(parent_dir).expanduser().absolute().iterdir():
                if (
                    p not in paths
                    and (p.is_dir() and p.stem != "_ocr")
                    or (p.is_file() and p.suffix.lower() in {".zip", ".cbz"})
                ):
                    parent_volumes.append(p)
            
            # Apply first/last filters if specified
            if parent_volumes:
                filtered_volumes = filter_volumes_by_position(parent_volumes, first, last)
                if first or last:
                    logger.info(f"Parent dir: {len(filtered_volumes)}/{len(parent_volumes)} volumes selected")
                paths.extend(filtered_volumes)
            else:
                paths.extend(parent_volumes)

    vc = VolumeCollection()

    for path_in in paths:
        vc.add_path_in(path_in)

    if len(vc) == 0:
        logger.error("Found no paths to process. Did you set the paths correctly?")
        return

    for title in vc.titles.values():
        title.set_uuid()

    status_counter = Counter()

    print(f"\nFound {len(vc)} volumes")
    
    # For large collections, show summary instead of listing all volumes
    if len(vc) > 10:
        for volume in vc:
            status_counter[volume.status] += 1
        
        # Show status summary
        print("\nVolume status summary:")
        for status, count in status_counter.items():
            print(f"  {status}: {count}")
        
        # If root_dir mode, show per-series breakdown
        if root_dir:
            print("\nVolumes per series:")
            series_volume_counts = {}
            for volume in vc:
                series_name = volume.path_in.parent.name
                if series_name not in series_volume_counts:
                    series_volume_counts[series_name] = 0
                series_volume_counts[series_name] += 1
            
            for series_name in sorted(series_volume_counts.keys()):
                print(f"  {series_name}: {series_volume_counts[series_name]} volumes")
    else:
        # For small collections, show full list as before
        print()
        for volume in vc:
            print(volume)
            status_counter[volume.status] += 1
    
    msg = "\nEach path will be treated as one volume.\n"
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
                skip_pattern=skip_pattern,
            )

            num_sucessful = 0
            for i, volume in enumerate(vc):
                # Check if zip already exists when --zip flag is used
                if zip and volume.path_in.is_dir():
                    volume_name = volume.path_in.name
                    expected_zip_path = volume.path_title / f"{volume_name}_mokuro.zip"
                    if expected_zip_path.exists():
                        logger.info(f"Skipping {i + 1}/{len(vc)}: {volume.path_in} (zip already exists: {expected_zip_path.name})")
                        num_sucessful += 1  # Count as successful since zip exists
                        continue
                
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
        
        # Create zip files if requested
        if zip:
            logger.info("Creating zip files for processed volumes...")
            zip_count = 0
            for volume in vc:
                zip_path = create_volume_zip(volume)
                if zip_path:
                    zip_count += 1
            logger.info(f"Created {zip_count} zip file(s)")


if __name__ == "__main__":
    fire.Fire(run)
