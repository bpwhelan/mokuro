import cv2
import numpy as np
import json
import subprocess
import tempfile
import time
import os
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


class GoogleLensOCR:
    def __init__(self):
        # Check if our Node.js wrapper exists
        wrapper_path = os.path.join(os.path.dirname(__file__), '..', 'lens_ocr_wrapper.js')
        if not os.path.exists(wrapper_path):
            logger.error("lens_ocr_wrapper.js not found. Make sure Node.js wrapper is in the project root.")
            raise Exception("Google Lens OCR wrapper not found")
        
        self.wrapper_path = wrapper_path
        
        # Check if Node.js is available
        try:
            subprocess.run(['node', '--version'], capture_output=True, check=True)
        except (FileNotFoundError, subprocess.CalledProcessError):
            logger.error("Node.js not found. Please install Node.js to use Google Lens OCR")
            raise Exception("Node.js not installed")
    
    def __call__(self, pil_image):
        """
        Process a PIL Image using Google Lens OCR
        Returns the extracted text as a string
        """
        # Save the image to a temporary file
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
            temp_path = temp_file.name
            pil_image.save(temp_path, 'PNG')
        
        try:
            # Call our Node.js wrapper
            result = subprocess.run(['node', self.wrapper_path, temp_path], 
                                    capture_output=True, text=True, check=True)
            
            # Parse the JSON output
            try:
                ocr_result = json.loads(result.stdout)
                # Extract text from all segments
                text_parts = []
                if 'segments' in ocr_result:
                    for segment in ocr_result['segments']:
                        if 'text' in segment:
                            text_parts.append(segment['text'])
                
                # Add rate limiting delay for Google Lens OCR
                time.sleep(0.5)
                return ''.join(text_parts)
            except json.JSONDecodeError:
                # If JSON parsing fails, return the raw output
                logger.warning("Failed to parse JSON from Google Lens OCR, using raw output")
                # Add rate limiting delay even for failed JSON parsing (successful OCR call)
                time.sleep(0.5)
                return result.stdout.strip()
                
        except subprocess.CalledProcessError as e:
            logger.error(f"Google Lens OCR failed: {e.stderr}")
            return ""
        finally:
            # Clean up the temporary file
            if os.path.exists(temp_path):
                os.unlink(temp_path)


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
        ocr_engine="manga-ocr",  # "manga-ocr" or "lens"
    ):
        self.text_height = text_height
        self.max_ratio_vert = max_ratio_vert
        self.max_ratio_hor = max_ratio_hor
        self.anchor_window = anchor_window
        self.disable_ocr = disable_ocr
        self.ocr_engine = ocr_engine

        if not self.disable_ocr:
            cuda = torch.cuda.is_available()
            device = "cuda" if cuda and not force_cpu else "cpu"
            logger.info(f"Initializing text detector, using device {device}")
            self.text_detector = TextDetector(
                model_path=cache.comic_text_detector, input_size=detector_input_size, device=device, act="leaky"
            )
            
            if self.ocr_engine == "lens":
                logger.info("Initializing Google Lens OCR")
                self.ocr_model = GoogleLensOCR()
            else:  # Default to manga-ocr
                logger.info("Initializing Manga OCR")
                self.ocr_model = MangaOcr(pretrained_model_name_or_path, force_cpu)

    def __call__(self, img_path):
        img = imread(img_path)
        if img is None:
            raise InvalidImage()
        H, W, *_ = img.shape
        result = {"version": __version__, "img_width": W, "img_height": H, "blocks": []}

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
                    line_text += self.ocr_model(Image.fromarray(line_crop))

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
