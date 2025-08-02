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

## Enhanced Dual OCR Fork

This is an enhanced fork of mokuro that supports **dual OCR engines** with separate file naming:

- 🔥 **[manga-ocr](https://github.com/kha-white/manga-ocr)** (default) - Fast, offline, specialized for Japanese manga
- 🌐 **[Google Lens OCR](https://github.com/dimdenGD/chrome-lens-ocr)** (`--lens` flag) - Multilingual, excellent for mixed content

Both engines use [comic-text-detector](https://github.com/dmMaze/comic-text-detector) for text detection, ensuring identical text localization with your choice of OCR recognition.

Try running on your manga in Colab: [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/kha-white/mokuro/blob/master/notebooks/mokuro_demo.ipynb)

See also:
- [mokuro-reader](https://github.com/ZXY101/mokuro-reader), a web reader for mokuro, developed by ZXY101
- [Mokuro2Pdf](https://github.com/Kartoffel0/Mokuro2Pdf), cli Ruby script to generate pdf files with selectable text from Mokuro's html overlay
- [Xelieu's guide](https://lazyguidejp.github.io/jp-lazy-guide/setupMangaOnPC/), a comprehensive guide on setting up a reading and mining workflow with manga-ocr/mokuro (and many other useful tips)

# Installation

## Prerequisites

- **Python 3.8+** (with pip) - Note: newest Python releases might not be supported due to PyTorch dependency. Refer to [PyTorch website](https://pytorch.org/get-started/locally/) for supported versions.
- **Node.js 16+** (with npm) - *Optional, only needed for Google Lens OCR*

Some users have reported problems with Python installed from Microsoft Store. If you see an error:
`ImportError: DLL load failed while importing fugashi: The specified module could not be found.`,
try installing Python from the [official site](https://www.python.org/downloads).

If you want to run with GPU, install PyTorch as described [here](https://pytorch.org/get-started/locally/#start-locally),
otherwise this step can be skipped.

## Install Enhanced Dual OCR Version 
This version supports both manga-ocr and Google Lens OCR engines with separate file naming:

```bash

# Clone with submodules (required for comic-text-detector)
git clone --recurse-submodules https://github.com/xrishox/mokuro.git
# conda install -c conda-forge nodejs=24
cd mokuro
requirements-server.txt
# Optional: Install Node.js dependencies for Google Lens OCR
npm install chrome-lens-ocr
# Install Python dependencies
pip install -e .
```

## Install Original Version (PyPI)

For the original manga-ocr only version:

```bash
pip3 install mokuro
```

**Note:** The PyPI version only supports manga-ocr. For dual OCR engine support (manga-ocr + Google Lens), use the installation above.

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

## Supported Image Formats

mokuro supports the following image formats:
- **JPEG** (.jpg, .jpeg) - Standard manga format
- **PNG** (.png) - Lossless format
- **WebP** (.webp) - Modern web format
- **AVIF** (.avif) - Advanced image format with excellent compression

Note: AVIF requires Pillow 10.0.0 or later.

## Choose OCR Engine

By default, mokuro uses manga-ocr. You can explicitly choose an OCR engine:

```bash
# Use manga-ocr (default) - creates .mo.html and .mo.mokuro files
mokuro /path/to/manga/vol1

# Use Google Lens OCR - creates .gl.html and .gl.mokuro files  
mokuro /path/to/manga/vol1 --lens

# Explicitly specify manga-ocr
mokuro /path/to/manga/vol1 --manga-ocr

# Process multiple volumes with different engines
mokuro --parent-dir /path/to/manga --lens    # All volumes with Google Lens
mokuro --parent-dir /path/to/manga           # All volumes with manga-ocr
```

## File Output Comparison

Each OCR engine creates separate output files, allowing you to compare results:

```
manga-volume/
├── manga-volume.mo.html     ← manga-ocr HTML output  
├── manga-volume.mo.mokuro   ← manga-ocr mokuro format
├── manga-volume.gl.html     ← Google Lens HTML output
├── manga-volume.gl.mokuro   ← Google Lens mokuro format
└── _ocr/
    ├── manga-volume.mo/     ← manga-ocr cache (*.mo.json)
    └── manga-volume.gl/     ← Google Lens cache (*.gl.json)
```

## Cache System

Each OCR engine maintains separate cache directories:
- `_ocr/volume.mo/` - manga-ocr results (*.mo.json files)
- `_ocr/volume.gl/` - Google Lens results (*.gl.json files)

This allows switching between OCR engines without losing previous results.

## Troubleshooting

### Google Lens OCR Issues

If you encounter issues with `--lens`:

```bash
# Run the setup script first
./setup_lens.sh

# Check Node.js version (requires 16+)
node --version

# Manual install if setup script fails
npm install chrome-lens-ocr
```

### Performance Tips

- **manga-ocr**: Faster, works offline, best for pure Japanese manga
- **Google Lens**: Slower but handles mixed languages and non-standard fonts better
- Use `--force_cpu` if you have GPU memory issues (affects text detection only)
- Both engines use the same text detection, so text localization is identical

### Submodule Issues

If comic-text-detector is missing after cloning:

```bash
# Initialize submodules in existing repo
git submodule update --init --recursive
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
--disable_confirmation: Disable confirmation prompt. If False, the user will be prompted to confirm the list of volumes to be processed.
--disable_ocr: Disable OCR processing. Generate mokuro/HTML files without OCR results.
--ignore_errors: Continue processing volumes even if an error occurs.
--no_cache: Do not use cached OCR results from previous runs (_ocr directories).
--unzip: Extract volumes in zip/cbz format in their original location.
--disable_html: Disable legacy HTML output. If True, acts as if --unzip is True.
--as_one_file: Applies only to legacy HTML. If False, generate separate CSS and JS files instead of embedding them in the HTML file.
--version: Print the version of mokuro and exit.
```

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
