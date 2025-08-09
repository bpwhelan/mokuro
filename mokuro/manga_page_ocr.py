import cv2
import numpy as np
from PIL import Image
from loguru import logger
from scipy.signal.windows import gaussian

from comic_text_detector.inference import TextDetector
from manga_ocr import MangaOcr
from mokuro import __version__
from mokuro.cache import cache
from mokuro.utils import imread
import torch


class InvalidImage(Exception):
    def __init__(self, message="Animation file, Corrupted file or Unsupported type"):
        super().__init__(message)


class MangaPageOcr:
    def __init__(
        self,
        pretrained_model_name_or_path="kha-white/manga-ocr-base",
        force_cpu=False,
        detector_input_size=1024,
        text_height=64,
        max_ratio_vert=16,
        max_ratio_hor=8,
        anchor_window=2,
        disable_ocr=False,
        ocr_engine: str = "manga_ocr",
        owocr_config=None,
    ):
        self.text_height = text_height
        self.max_ratio_vert = max_ratio_vert
        self.max_ratio_hor = max_ratio_hor
        self.anchor_window = anchor_window
        self.disable_ocr = disable_ocr

        # language/source code to tag outputs (None for native manga-ocr)
        self.lang_code = None

        if not self.disable_ocr:
            cuda = torch.cuda.is_available()
            device = "cuda" if cuda and not force_cpu else "cpu"
            logger.info(f"Initializing text detector, using device {device}")
            self.text_detector = TextDetector(
                model_path=cache.comic_text_detector, input_size=detector_input_size, device=device, act="leaky"
            )
            # Select OCR engine
            self._ocr_callable = None
            engine = (ocr_engine or "manga_ocr").lower()
            if engine == "manga_ocr" or engine == "mocr" or engine == "manga-ocr":
                self._ocr_callable = MangaOcr(pretrained_model_name_or_path, force_cpu)
                # native manga-ocr has no lang_code as per requirement
            elif engine.startswith("owocr:"):
                provider = engine.split(":", 1)[1].strip().lower()
                try:
                    from owocr import ocr as ow
                except Exception as e:
                    raise RuntimeError(
                        "Selected OCR engine requires owocr. Please install owocr and any provider-specific extras."
                    ) from e

                # Config per provider (optional)
                config_map = owocr_config or {}

                # Factory returning an instance or None
                def make_provider(p: str):
                    p = p.lower()
                    cfg = config_map.get(p, {}) if isinstance(config_map, dict) else {}
                    if p in ("mangaocr", "mocr", "manga-ocr"):
                        self.lang_code = "mo"
                        return ow.MangaOcr({
                            "pretrained_model_name_or_path": pretrained_model_name_or_path,
                            "force_cpu": force_cpu,
                        })
                    if p in ("easyocr", "easy"):
                        self.lang_code = "eo"
                        use_gpu = torch.cuda.is_available() and not force_cpu
                        return ow.EasyOCR({"gpu": use_gpu})
                    if p in ("rapidocr", "rapid"):
                        self.lang_code = "ro"
                        return ow.RapidOCR()
                    if p in ("gvision", "googlevision", "google_vision"):
                        self.lang_code = "gv"
                        return ow.GoogleVision()
                    if p in ("glens", "googlelens", "lens"):
                        self.lang_code = "gl"
                        return ow.GoogleLens()
                    if p in ("glensweb", "lensweb", "googlelensweb"):
                        self.lang_code = "gw"
                        return ow.GoogleLensWeb()
                    if p in ("bing",):
                        self.lang_code = "bo"
                        return ow.Bing()
                    if p in ("azure", "azureimageanalysis", "azure_image_analysis"):
                        self.lang_code = "az"
                        return ow.AzureImageAnalysis(cfg)
                    if p in ("ocrspace", "ocr_space"):
                        self.lang_code = "os"
                        return ow.OCRSpace(cfg)
                    if p in ("avision", "applevision", "apple_vision"):
                        self.lang_code = "av"
                        return ow.AppleVision()
                    if p in ("alivetext", "applelivetext", "apple_live_text"):
                        self.lang_code = "al"
                        return ow.AppleLiveText()
                    if p in ("winrtocr", "winrt", "winrt_ocr"):
                        self.lang_code = "wo"
                        return ow.WinRTOCR(cfg)
                    if p in ("oneocr", "one_ocr"):
                        self.lang_code = "oo"
                        return ow.OneOCR(cfg)
                    raise ValueError(
                        f"Unsupported owocr provider '{p}'."
                    )

                if provider == "auto":
                    import sys as _sys
                    if _sys.platform == "darwin":
                        priority = [
                            "alivetext",
                            "avision",
                            "mangaocr",
                            "rapidocr",
                            "easyocr",
                            "gvision",
                            "azure",
                            "ocrspace",
                            "glens",
                            "glensweb",
                            "bing",
                        ]
                    elif _sys.platform == "win32":
                        priority = [
                            "oneocr",
                            "winrtocr",
                            "mangaocr",
                            "rapidocr",
                            "easyocr",
                            "gvision",
                            "azure",
                            "ocrspace",
                            "glens",
                            "glensweb",
                            "bing",
                        ]
                    else:
                        priority = [
                            "mangaocr",
                            "rapidocr",
                            "easyocr",
                            "gvision",
                            "azure",
                            "ocrspace",
                            "glens",
                            "glensweb",
                            "bing",
                        ]

                    engine_instance = None
                    for p in priority:
                        try:
                            candidate = make_provider(p)
                            if getattr(candidate, "available", False):
                                engine_instance = candidate
                                break
                        except Exception:
                            continue
                    if engine_instance is None:
                        raise RuntimeError(
                            "No owocr providers are available. Install owocr extras or configure credentials as needed."
                        )
                else:
                    engine_instance = make_provider(provider)
                    if not getattr(engine_instance, "available", False):
                        raise RuntimeError(
                            f"owocr provider '{provider}' is not available on this system or missing dependencies/config."
                        )

                self._owocr_engine = engine_instance

                def _call_with_owocr(img_pil):
                    ok, text = self._owocr_engine(img_pil)
                    return text if ok else ""

                self._ocr_callable = _call_with_owocr
            else:
                raise ValueError(
                    f"Unknown ocr_engine '{ocr_engine}'. Use 'manga_ocr' or 'owocr:<provider>' (e.g. owocr:easyocr)"
                )

    def __call__(self, img_path):
        img = imread(img_path)
        if img is None:
            raise InvalidImage()
        H, W, *_ = img.shape
        result = {"version": __version__, "img_width": W, "img_height": H, "blocks": []}
        if self.lang_code:
            result["lang_code"] = self.lang_code

        if self.disable_ocr:
            return result

        mask, mask_refined, blk_list = self.text_detector(img, refine_mode=1, keep_undetected_mask=True)
        for blk_idx, blk in enumerate(blk_list):
            result_blk = {
                "box": list(blk.xyxy),
                "vertical": blk.vertical,
                "font_size": blk.font_size,
                "lines_coords": [],
                "lines": [],
            }

            for line_idx, line in enumerate(blk.lines_array()):
                if blk.vertical:
                    max_ratio = self.max_ratio_vert
                else:
                    max_ratio = self.max_ratio_hor

                line_crops, cut_points = self.split_into_chunks(
                    img,
                    mask_refined,
                    blk,
                    line_idx,
                    textheight=self.text_height,
                    max_ratio=max_ratio,
                    anchor_window=self.anchor_window,
                )

                line_text = ""
                for line_crop in line_crops:
                    if blk.vertical:
                        line_crop = cv2.rotate(line_crop, cv2.ROTATE_90_CLOCKWISE)
                    # self._ocr_callable can be MangaOcr instance or a function wrapper
                    if hasattr(self._ocr_callable, "__call__"):
                        line_text += self._ocr_callable(Image.fromarray(line_crop))
                    else:
                        # Fallback (should not happen): empty string
                        line_text += ""

                result_blk["lines_coords"].append(line.tolist())
                result_blk["lines"].append(line_text)

            result["blocks"].append(result_blk)

        return result

    @staticmethod
    def split_into_chunks(img, mask_refined, blk, line_idx, textheight, max_ratio=16, anchor_window=2):
        line_crop = blk.get_transformed_region(img, line_idx, textheight)

        h, w, *_ = line_crop.shape
        ratio = w / h

        if ratio <= max_ratio:
            return [line_crop], []

        else:
            k = gaussian(textheight * 2, textheight / 8)

            line_mask = blk.get_transformed_region(mask_refined, line_idx, textheight)
            num_chunks = int(np.ceil(ratio / max_ratio))

            anchors = np.linspace(0, w, num_chunks + 1)[1:-1]

            line_density = line_mask.sum(axis=0)
            line_density = np.convolve(line_density, k, "same")
            line_density /= line_density.max()

            anchor_window *= textheight

            cut_points = []
            for anchor in anchors:
                anchor = int(anchor)

                n0 = np.clip(anchor - anchor_window // 2, 0, w)
                n1 = np.clip(anchor + anchor_window // 2, 0, w)

                p = line_density[n0:n1].argmin()
                p += n0

                cut_points.append(p)

            return np.split(line_crop, cut_points, axis=1), cut_points
