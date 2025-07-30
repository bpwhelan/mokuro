from collections import Counter
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Sequence, Optional, Union
import zipfile
import shutil

import fire
from loguru import logger

from mokuro import MokuroGenerator
from mokuro import __version__
from mokuro.legacy.overlay_generator import generate_legacy_html
from mokuro.volume import VolumeCollection, get_path_mokuro
from mokuro.ocr_engines import OCREngineFactory


def create_volume_zip(volume, ocr_engines):
    """Create a zip archive containing the chapter directory and all .mokuro files."""
    # Determine zip file name based on volume name
    if volume.path_in.is_dir():
        zip_name = volume.path_in.name + ".zip"
        zip_path = volume.path_in.parent / zip_name
    else:
        # For zip/cbz files, use the base name
        zip_name = volume.path_in.stem + "_complete.zip"
        zip_path = volume.path_in.parent / zip_name
    
    # Skip if zip already exists
    if zip_path.exists():
        logger.info(f"Zip archive already exists, skipping: {zip_path}")
        return
    
    logger.info(f"Creating zip archive: {zip_path}")
    
    try:
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            # Add the chapter directory contents
            if volume.path_in.is_dir():
                # Add all files from the chapter directory
                for file_path in volume.path_in.rglob('*'):
                    if file_path.is_file():
                        # Get relative path for the archive
                        arcname = volume.path_in.name / file_path.relative_to(volume.path_in)
                        zf.write(file_path, arcname)
            
            # Add all .mokuro files for this volume
            for engine in ocr_engines:
                mokuro_path = get_path_mokuro(volume.path_in, engine)
                if mokuro_path.exists():
                    zf.write(mokuro_path, mokuro_path.name)
                else:
                    logger.warning(f"Mokuro file not found: {mokuro_path}")
        
        logger.info(f"Successfully created zip archive: {zip_path}")
        
    except Exception as e:
        logger.error(f"Failed to create zip archive: {e}")


def run(
    *paths: Optional[Sequence[Union[str, Path]]],
    parent_dir: Optional[Union[str, Path]] = None,
    pretrained_model_name_or_path: str = "kha-white/manga-ocr-base",
    force_cpu: bool = False,
    disable_confirmation: bool = False,
    disable_ocr: bool = False,
    ignore_errors: bool = False,
    no_cache: bool = False,
    unzip: bool = False,
    legacy_html: bool = True,
    as_one_file: bool = True,
    version: bool = False,
    lens: bool = False,
    manga_ocr: bool = False,
    complete: bool = False,
    zip: bool = False,
):
    """
    Process manga volumes with mokuro.

    Args:
        paths: Paths to manga volumes. Volume can be a directory, a zip file or a cbz file.
        parent_dir: Parent directory to scan for volumes. If provided, all volumes inside this directory will be processed.
        pretrained_model_name_or_path: Name or path of the manga-ocr model (only used with manga-ocr engine).
        force_cpu: Force the use of CPU even if CUDA is available (only affects text detection and manga-ocr).
        disable_confirmation: Disable confirmation prompt. If False, the user will be prompted to confirm the list of volumes to be processed.
        disable_ocr: Disable OCR processing. Generate mokuro/HTML files without OCR results.
        ignore_errors: Continue processing volumes even if an error occurs.
        no_cache: Do not use cached OCR results from previous runs (_ocr directories).
        unzip: Extract volumes in zip/cbz format in their original location.
        legacy_html: Enable legacy HTML output. If True, acts as if --unzip is True.
        as_one_file: Applies only to legacy HTML. If False, generate separate CSS and JS files instead of embedding them in the HTML file.
        version: Print the version of mokuro and exit.
        lens: Use Google Lens OCR engine instead of manga-ocr.
        manga_ocr: Use manga-ocr engine (default behavior, explicit flag for clarity).
        complete: Process with all available OCR engines (currently manga-ocr and lens).
        zip: Create a zip archive containing the chapter directory and all .mokuro files after processing.
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

    # Determine OCR engines to use
    if complete:
        if lens or manga_ocr:
            logger.warning("--complete flag overrides --lens and --manga-ocr flags. Processing with all engines.")
        ocr_engines = OCREngineFactory.available_engines()
        logger.info(f"Running complete OCR with all engines: {', '.join(ocr_engines)}")
    else:
        if lens and manga_ocr:
            logger.error("Cannot specify both --lens and --manga-ocr flags. Choose one or use default (manga-ocr).")
            return
        ocr_engines = ["lens" if lens else "manga-ocr"]

    # Use the first engine for volume collection (to check processing status)
    # The actual OCR engine used for processing will be determined later
    vc = VolumeCollection(ocr_engine=ocr_engines[0])

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
    
    with TemporaryDirectory() as tmp_dir:
        tmp_dir = Path(tmp_dir)

        # unzip == True means that zipped volumes will be unzipped in their original location
        # in that case, we don't use a temporary directory
        if unzip:
            tmp_dir = None

        num_sucessful = 0
        
        # Process with each OCR engine
        for ocr_engine in ocr_engines:
            if len(ocr_engines) > 1:
                logger.info(f"\n{'='*60}")
                logger.info(f"Processing with {ocr_engine} OCR engine")
                logger.info(f"{'='*60}")
            else:
                if ocr_engine == "lens":
                    logger.info("Using Google Lens OCR engine")
                else:
                    logger.info("Using manga-ocr engine")
            
            # Update volume collection for current engine
            vc.ocr_engine = ocr_engine
            for volume in vc:
                volume.ocr_engine = ocr_engine
                volume.path_mokuro = get_path_mokuro(volume.path_in, ocr_engine)
            
            mg = MokuroGenerator(
                pretrained_model_name_or_path=pretrained_model_name_or_path,
                force_cpu=force_cpu, 
                disable_ocr=disable_ocr,
                ocr_engine=ocr_engine
            )
            
            for i, volume in enumerate(vc):
                logger.info(f"Processing {i + 1}/{len(vc)}: {volume.path_in}")

                try:
                    volume.unzip(tmp_dir)
                    mg.process_volume(volume, ignore_errors=ignore_errors, no_cache=no_cache)
                    if legacy_html and ocr_engine == ocr_engines[-1]:  # Only generate HTML for the last engine
                        generate_legacy_html(volume, as_one_file=as_one_file, ignore_errors=ignore_errors)

                except Exception:
                    logger.exception(f"Error while processing {volume.path_in} with {ocr_engine}")
                else:
                    num_sucessful += 1

        total_runs = len(vc) * len(ocr_engines)
        logger.info(f"\nProcessed successfully: {num_sucessful}/{total_runs} ({len(ocr_engines)} engine(s) × {len(vc)} volume(s))")
        
        # Create zip archives if requested
        if zip:
            logger.info("\nCreating zip archives...")
            for volume in vc:
                create_volume_zip(volume, ocr_engines)


if __name__ == "__main__":
    fire.Fire(run)
