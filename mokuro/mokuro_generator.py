from json import JSONDecodeError

from loguru import logger
from tqdm import tqdm

from mokuro import __version__
from mokuro.manga_page_ocr import MangaPageOcr
from mokuro.utils import dump_json, load_json
from mokuro.volume import Volume


class MokuroGenerator:
    def __init__(
        self, pretrained_model_name_or_path="kha-white/manga-ocr-base", force_cpu=False, disable_ocr=False, **kwargs
    ):
        self.pretrained_model_name_or_path = pretrained_model_name_or_path
        self.force_cpu = force_cpu
        self.disable_ocr = disable_ocr
        self.kwargs = kwargs
        self.mpocr = None
        self.ocr_engine = kwargs.get("ocr_engine", "manga_ocr")

    @staticmethod
    def _engine_code_from_arg(ocr_engine: str | None):
        if not ocr_engine:
            return None
        e = ocr_engine.lower()
        if e in ("manga_ocr", "mocr", "manga-ocr"):
            return None  # native manga-ocr has no code
        if not e.startswith("owocr:"):
            return None
        p = e.split(":", 1)[1].strip().lower()
        mapping = {
            "mangaocr": "mo",
            "mocr": "mo",
            "manga-ocr": "mo",
            "easyocr": "eo",
            "easy": "eo",
            "rapidocr": "ro",
            "rapid": "ro",
            "gvision": "gv",
            "googlevision": "gv",
            "google_vision": "gv",
            "glens": "gl",
            "googlelens": "gl",
            "lens": "gl",
            "glensweb": "gw",
            "lensweb": "gw",
            "googlelensweb": "gw",
            "bing": "bo",
            "azure": "az",
            "azureimageanalysis": "az",
            "azure_image_analysis": "az",
            "ocrspace": "os",
            "ocr_space": "os",
            "avision": "av",
            "applevision": "av",
            "apple_vision": "av",
            "alivetext": "al",
            "applelivetext": "al",
            "apple_live_text": "al",
            "winrtocr": "wo",
            "winrt": "wo",
            "winrt_ocr": "wo",
            "oneocr": "oo",
            "one_ocr": "oo",
        }
        return mapping.get(p)

    def init_models(self):
        if self.mpocr is None:
            self.mpocr = MangaPageOcr(
                self.pretrained_model_name_or_path,
                force_cpu=self.force_cpu,
                disable_ocr=self.disable_ocr,
                **self.kwargs,
            )

    def process_volume(self, volume: Volume, ignore_errors=False, no_cache=False):
        # decide engine-specific cache directory
        code = self._engine_code_from_arg(self.ocr_engine)
        base_cache_dir = volume.path_ocr_cache
        if code:
            cache_dir = base_cache_dir.parent / (base_cache_dir.name + f".{code}")
        else:
            cache_dir = base_cache_dir

        cache_dir.mkdir(parents=True, exist_ok=True)

        if volume.mokuro_data is not None:
            for page in volume.mokuro_data["pages"]:
                json_path = (cache_dir / page["img_path"]).with_suffix(".json")
                if json_path.is_file():
                    continue
                json_path.parent.mkdir(parents=True, exist_ok=True)
                page = page.copy()
                page.pop("img_path")
                dump_json(page, json_path)

        img_paths = volume.get_img_paths()

        for img_path_rel in tqdm(img_paths.values(), desc="Processing pages..."):
            try:
                json_path = (cache_dir / img_path_rel).with_suffix(".json")

                try:
                    load_json(json_path)
                    already_processed = True
                except (FileNotFoundError, JSONDecodeError, UnicodeDecodeError):
                    already_processed = False

                if no_cache or not already_processed:
                    self.init_models()
                    result = self.mpocr(volume.path_in / img_path_rel)
                    json_path.parent.mkdir(parents=True, exist_ok=True)
                    dump_json(result, json_path)
            except Exception as e:
                if ignore_errors:
                    logger.error(e)
                else:
                    raise e

        self.generate_mokuro_file(volume, cache_dir=cache_dir, lang_code=code, ignore_errors=ignore_errors)

    @staticmethod
    def generate_mokuro_file(volume: Volume, cache_dir, lang_code=None, ignore_errors=False):
        # gather jsons from the selected cache dir
        from natsort import natsorted
        json_paths = natsorted(p.relative_to(cache_dir) for p in cache_dir.glob("**/*.json"))
        json_paths = {p.with_suffix(""): p for p in json_paths}
        img_paths = volume.get_img_paths()

        out = {
            "version": __version__,
            "title": volume.title.name,
            "title_uuid": volume.title.uuid,
            "volume": volume.name,
            "volume_uuid": volume.uuid,
            "pages": [],
        }
        if lang_code:
            out["lang_code"] = lang_code

        for key, json_path_rel in json_paths.items():
            try:
                img_path_rel = img_paths[key]
                page_json = load_json(cache_dir / json_path_rel)
                page_json["img_path"] = str(img_path_rel).replace("\\", "/")
                out["pages"].append(page_json)
            except Exception as e:
                if ignore_errors:
                    logger.error(e)
                else:
                    raise e

        # choose output path; include lang code if provided (native manga-ocr has no code)
        if lang_code:
            out_name = f"{volume.path_in.name}.{lang_code}.mokuro"
        else:
            out_name = f"{volume.path_in.name}.mokuro"
        out_path = volume.path_title / out_name
        dump_json(out, out_path)
