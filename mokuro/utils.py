import json
import shutil
import zipfile
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

try:
    # Optional plugins to add AVIF/HEIF support if installed
    from pillow_heif import register_heif_opener as _register_heif

    _register_heif()
except Exception:
    pass

_jxl_registered = False
for _mod in (
    "pillow_jxl",  # some dists expose this name
    "pillow_jxl_plugin",  # others use this
    "PIL.JpegXLImagePlugin",  # plugin module inside PIL namespace
):
    try:
        __import__(_mod)
        _jxl_registered = True
        break
    except Exception:
        continue


class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, np.generic):
            return obj.item()
        return json.JSONEncoder.default(self, obj)


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def dump_json(obj, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, cls=NumpyEncoder)


def imread(path, flags=cv2.IMREAD_COLOR):
    """Read image from path.

    Strategy:
    - Try Pillow first (supports AVIF/JXL when plugins are installed). Reject animated images.
    - Convert to NumPy BGR to match OpenCV expectations.
    - Fallback to OpenCV imdecode (also handles unicode paths via fromfile).
    """
    # Try Pillow path
    try:
        img = Image.open(str(path))
        # Reject animated images
        n_frames = getattr(img, "n_frames", 1)
        if n_frames and n_frames > 1:
            return None
        if flags == cv2.IMREAD_GRAYSCALE:
            img = img.convert("L")
            arr = np.array(img)
            return arr
        else:
            img = img.convert("RGB")
            arr = np.array(img)
            # Convert RGB -> BGR for OpenCV-style arrays
            arr = arr[:, :, ::-1]
            return arr
    except Exception:
        pass

    # Fallback to OpenCV
    try:
        return cv2.imdecode(np.fromfile(path, dtype=np.uint8), flags)
    except Exception:
        return None


def get_path_format(path: Path):
    if path.is_dir():
        return ""
    else:
        return path.suffix.lower()


def unzip(path_src: Path, path_dst: Path, correct_duplicated_root=True):
    with zipfile.ZipFile(path_src, "r") as zip_ref:
        zip_ref.extractall(path_dst)

    if correct_duplicated_root:
        # check if there's only one directory in the extracted directory and it has the same name as the archive
        extracted_content = list(path_dst.iterdir())
        if len(extracted_content) == 1:
            extracted_dir = extracted_content[0]
            if extracted_dir.is_dir():
                archive_name = path_src.stem  # remove extension
                if archive_name == extracted_dir.name:
                    for item in extracted_dir.iterdir():
                        shutil.move(str(item), str(path_dst))
                    extracted_dir.rmdir()
