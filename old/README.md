# mokuro

Read Japanese manga with selectable text inside a browser.

**See demo: https://kha-white.github.io/manga-demo**

https://user-images.githubusercontent.com/22717958/164993274-3e8d1650-9be3-457d-84cb-f92f9598cd5a.mp4

<sup>Demo contains excerpt from [Manga109-s dataset](http://www.manga109.org/en/download_s.html). うちの猫’ず日記 © がぁさん</sup>

mokuro is aimed towards Japanese learners, who want to read manga in Japanese with a pop-up dictionary like [Yomitan](https://github.com/themoeway/yomitan).
It works like this:
1. Perform text detection and OCR for each page.
2. After processing a whole volume, generate a .mokuro file, which contains OCR results and metadata. All processing is done offline (before reading).
3. Load the .mokuro file together with manga images in [web reader](https://reader.mokuro.app/), which serves both as a manga reader and a catalog for processed series and volumes.

Alternatively, you can still use the old method from mokuro 0.1.*:
Instead of a .mokuro file, generate an HTML file, which you can open in a browser.
You can transfer the resulting HTML file together with manga images to another device (e.g. your mobile phone) and read there.
This method is still supported for backward compatibility, but it is recommended to use the new .mokuro format and the web reader.
For details, see [Legacy HTML vs. new .mokuro format](#legacy-html-vs-new-mokuro-format).

mokuro uses [comic-text-detector](https://github.com/dmMaze/comic-text-detector) for text detection
and [manga-ocr](https://github.com/kha-white/manga-ocr) for OCR.

Supported image formats: jpg, jpeg, png, webp, avif, jxl

Try running on your manga in Colab: [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/kha-white/mokuro/blob/master/notebooks/mokuro_demo.ipynb)

See also:
- [mokuro-reader](https://github.com/ZXY101/mokuro-reader), a web reader for mokuro, developed by ZXY101
- [Mokuro2Pdf](https://github.com/Kartoffel0/Mokuro2Pdf), cli Ruby script to generate pdf files with selectable text from Mokuro's html overlay
- [Xelieu's guide](https://lazyguidejp.github.io/jp-lazy-guide/setupMangaOnPC/), a comprehensive guide on setting up a reading and mining workflow with manga-ocr/mokuro (and many other useful tips)

# Installation

You need Python 3.6 or newer. Please note, that the newest Python release might not be supported due to a PyTorch dependency, 
which often breaks with new Python releases and needs some time to catch up.
Refer to [PyTorch website](https://pytorch.org/get-started/locally/) for a list of supported Python versions.

Some users have reported problems with Python installed from Microsoft Store. If you see an error:
`ImportError: DLL load failed while importing fugashi: The specified module could not be found.`,
try installing Python from the [official site](https://www.python.org/downloads).

If you want to run with GPU, install PyTorch as described [here](https://pytorch.org/get-started/locally/#start-locally),
otherwise this step can be skipped.

Run in command line:

```commandline
pip3 install mokuro
```

# Usage

## Run on one volume

```bash
mokuro /path/to/manga/vol1
```

This will generate `/path/to/manga/vol1.html` file, which you can open in a browser.

If your path contains spaces, enclose it in double quotes, like this:

```bash
mokuro "/path/to/manga/volume 1"
```

## Run on multiple volumes

```bash
mokuro /path/to/manga/vol1 /path/to/manga/vol2 /path/to/manga/vol3
```

For each volume, a separate HTML file will be generated.

## Run on a directory containing multiple volumes

If your directory structure looks somewhat like this:
```
manga_title/
├─vol1/
├─vol2/
├─vol3/
└─vol4/
```

You can process all volumes by running:

```bash
mokuro --parent_dir manga_title/
```

## Other options

```
--pretrained_model_name_or_path: Name or path of the manga-ocr model.
--force_cpu: Force the use of CPU even if CUDA is available.
--ocr_engine: OCR backend to use. Default 'manga_ocr'. To use owocr providers, set to 'owocr:<provider>' (e.g. 'owocr:easyocr', 'owocr:rapidocr', 'owocr:mangaocr', 'owocr:gvision', 'owocr:glens', 'owocr:glensweb', 'owocr:bing', 'owocr:azure', 'owocr:ocrspace', 'owocr:avision', 'owocr:alivetext', 'owocr:winrtocr', 'owocr:oneocr'). You can also use 'owocr:auto' to pick the best available for your OS.
--owocr_config: Optional path to a JSON file containing provider-specific configuration (e.g., Azure endpoint/api_key, OneOCR/WinRT server URL on non-Windows). Keys should match provider names (e.g., {"azure": {"endpoint": "...", "api_key": "..."}}).
--disable_confirmation: Disable confirmation prompt. If False, the user will be prompted to confirm the list of volumes to be processed.
--disable_ocr: Disable OCR processing. Generate mokuro/HTML files without OCR results.
--ignore_errors: Continue processing volumes even if an error occurs.
--no_cache: Do not use cached OCR results from previous runs (_ocr directories).
--unzip: Extract volumes in zip/cbz format in their original location.
--disable_html: Disable legacy HTML output. If True, acts as if --unzip is True.
--as_one_file: Applies only to legacy HTML. If False, generate separate CSS and JS files instead of embedding them in the HTML file.
--version: Print the version of mokuro and exit.
```

To enable additional engines via owocr, install the packages as needed, for example:
- `pip install owocr[mangaocr]` for Manga OCR via owocr
- `pip install owocr[easyocr]` for EasyOCR
- `pip install owocr[rapidocr]` for RapidOCR (downloads an ONNX model on first run)
- `pip install owocr[gvision]` for Google Vision (requires `~/.config/google_vision.json`)
- `pip install owocr[azure]` for Azure Image Analysis (requires `--owocr_config` with endpoint/api_key)
- `pip install owocr[lens]` for Google Lens (betterproto)
- `pip install owocr[lensweb]` for Google Lens (web)
- `pip install owocr[winocr]` for WinRT OCR (Windows only)
  - `pip install oneocr` for OneOCR (Windows only; see OneOCR README for system files)

Then run with `--ocr-engine owocr:easyocr` (or another provider). On macOS you can use `owocr:avision` or `owocr:alivetext`; on Windows `owocr:winrtocr` or `owocr:oneocr`.

Convenience: you can also install owocr (with all supported engines) alongside mokuro via extras:
- `pip install "mokuro[owocr]"`
  - Installs owocr plus all provider engine extras (EasyOCR, RapidOCR, Lens/LensWeb, Google Vision, Azure, WinRT OCR on Windows, and OneOCR on Windows). On macOS, Apple Vision/Live Text support comes via pyobjc from owocr’s base install. Some providers still require credentials or OS features.
  - Includes optional image plugins for AVIF and JXL support.

If you only need extended image formats: `pip install "mokuro[images]"`.

## Legacy HTML vs. new .mokuro format

Before version 0.2.0, mokuro generated a separate HTML file for each processed volume, which caused some usability issues:
- HTML files contained both the OCR results and the whole web reader GUI, so in order to update the GUI, all volumes needed to be updated with a new mokuro version
- images were stored separately and linked in HTML files, so any change in the directory structure could break the links
- transferring the manga to another device required transferring both the HTML files and the images
- there was no unified GUI for a whole catalog containing multiple volumes
- on some mobile devices, some workarounds were needed to open HTML files

Starting from version 0.2.0, a new .mokuro format is introduced, which is generated for each volume and contains only the OCR results and metadata necessary for the web reader GUI.
Web reader is now a separate web app, which can open manga volumes with their associated .mokuro files.

The old HTML format is still generated for backward compatibility, but it will not be developed further, and it is recommended to use the new .mokuro format and the web reader.

# Contact
For any inquiries, please feel free to contact me at kha-white@mail.com

# Acknowledgments

- https://github.com/dmMaze/comic-text-detector
- https://github.com/juvian/Manga-Text-Segmentation
Cache and language codes
- For non-native engines, per-page cache JSONs are written under `./_ocr/<VolumeName>.<code>/...` where `<code>` identifies the engine.
- The per-page JSONs include `lang_code`, and the top-level `.mokuro` file also includes `lang_code`.
- Codes:
  - gl: Google Lens, gw: Google Lens (web), gv: Google Vision, az: Azure
  - eo: EasyOCR, ro: RapidOCR, mo: MangaOCR via owocr (native manga-ocr has no code)
  - bo: Bing, os: OCRSpace
  - av: Apple Vision, al: Apple Live Text
  - wo: WinRT OCR, oo: OneOCR

## Docker (default: CUDA)

Default image includes CUDA (Ubuntu 24.04 + CUDA runtime + cuDNN):
- Build: `docker build -t mokuro-api:local .`
- Run: `docker run --rm --gpus all -p 7331:7331 mokuro-api:local`

Environment variables:
- `MOKURO_API_HOST` (default `0.0.0.0`), `MOKURO_API_PORT` (default `7331`)
- Cloud credentials (optional):
  - Google Vision: mount `~/.config/google_vision.json` into the container at `/home/appuser/.config/google_vision.json`
  - Azure: set `AZURE_VISION_ENDPOINT`, `AZURE_VISION_API_KEY`
  - OCRSpace: set `OCRSPACE_API_KEY`

Push to GHCR via GitHub Actions:
- Workflow `.github/workflows/publish-ghcr.yml` builds and pushes on branch/tag push.
- Image name: `ghcr.io/<owner>/<repo>:<tag>`

Manual push to GHCR:
- `docker build -t ghcr.io/<owner>/<repo>:latest .`
- `echo $GHCR_PAT | docker login ghcr.io -u <owner> --password-stdin`
- `docker push ghcr.io/<owner>/<repo>:latest`

CPU-only variants:
- Debian 13 (Trixie): `docker build -f Dockerfile.trixie -t mokuro-api:trixie .` then `docker run --rm -p 7331:7331 mokuro-api:trixie`

Notes:
- For CUDA: requires an NVIDIA host (recent driver) and `nvidia-container-toolkit` configured.
- The image installs CUDA-enabled PyTorch and onnxruntime-gpu. RapidOCR will leverage GPU if supported by ONNX Runtime.
- JPEG XL runtime comes from Ubuntu’s `libjxl0.7` (from the `jpeg-xl` source package) on 24.04. Tools are `libjxl-tools`. No source build needed.
