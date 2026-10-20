import os
import math
import io
from typing import Tuple, Dict, Any, Optional
import numpy as np
from PIL import Image

try:
    import tifffile
except ImportError:
    tifffile = None

class SlideEngine:
    """
    High-performance Digital Pathology Slide Engine.
    Handles pyramidal Whole Slide Images (.svs, .tiff) and high-resolution histology scans.
    Generates DeepZoom multi-resolution tiles dynamically without saving millions of small files.
    """
    def __init__(self, slide_path: str, tile_size: int = 256, overlap: int = 1):
        self.slide_path = slide_path
        self.tile_size = tile_size
        self.overlap = overlap
        self.is_svs = slide_path.lower().endswith(".svs")
        
        self.width = 0
        self.height = 0
        self.max_level = 0
        self.levels = []  # List of (w, h)
        self.base_image: Optional[Image.Image] = None
        self.pyramid_cache: Dict[int, Image.Image] = {}

        self._load_slide()

    def _load_slide(self):
        """Loads metadata and base image levels."""
        if not os.path.exists(self.slide_path):
            raise FileNotFoundError(f"Slide file not found at: {self.slide_path}")

        # Try loading via tifffile (standard for SVS / BigTIFF) or Pillow
        loaded = False
        if self.is_svs and tifffile is not None:
            try:
                with tifffile.TiffFile(self.slide_path) as tif:
                    # Page 0 is the primary baseline full-resolution image
                    page0 = tif.pages[0]
                    self.height, self.width = page0.shape[0], page0.shape[1]
                    # Load the image into PIL
                    raw_data = page0.asarray()
                    if raw_data.ndim == 3 and raw_data.shape[2] == 4:
                        self.base_image = Image.fromarray(raw_data[:, :, :3])
                    elif raw_data.ndim == 3:
                        self.base_image = Image.fromarray(raw_data)
                    else:
                        self.base_image = Image.fromarray(raw_data).convert("RGB")
                    loaded = True
            except Exception as e:
                print(f"Warning: tifffile failed on {self.slide_path} ({e}), falling back to PIL")

        if not loaded:
            # Fallback to PIL
            self.base_image = Image.open(self.slide_path).convert("RGB")
            self.width, self.height = self.base_image.size

        # Compute DeepZoom pyramid levels
        max_dim = max(self.width, self.height)
        self.max_level = int(math.ceil(math.log2(max_dim)))

        # Build dimensions for each level from 0 up to max_level
        self.levels = []
        for level in range(self.max_level + 1):
            scale = 0.5 ** (self.max_level - level)
            lvl_w = max(1, int(math.ceil(self.width * scale)))
            lvl_h = max(1, int(math.ceil(self.height * scale)))
            self.levels.append((lvl_w, lvl_h))

    def get_dzi_metadata(self) -> Dict[str, Any]:
        """Returns DeepZoom schema metadata for OpenSeadragon."""
        return {
            "Image": {
                "xmlns": "http://schemas.microsoft.com/deepzoom/2008",
                "Format": "jpg",
                "Overlap": self.overlap,
                "TileSize": self.tile_size,
                "Size": {
                    "Width": self.width,
                    "Height": self.height
                }
            }
        }

    def _get_level_image(self, level: int) -> Image.Image:
        """Returns or computes downsampled image for a given DeepZoom level."""
        if level in self.pyramid_cache:
            return self.pyramid_cache[level]

        target_w, target_h = self.levels[level]
        if level == self.max_level:
            img = self.base_image
        else:
            # High quality downsampling for histology
            img = self.base_image.resize((target_w, target_h), Image.Resampling.BILINEAR)

        # Cache thumbnail/overview levels, keep memory tight
        if target_w * target_h < 4000 * 4000:
            self.pyramid_cache[level] = img

        return img

    def get_tile(self, level: int, col: int, row: int, format: str = "JPEG", quality: int = 85) -> bytes:
        """
        Dynamically extracts and renders a 256x256 tile at the requested pyramid level.
        Handles overlap and edge boundaries seamlessly.
        """
        if level < 0 or level > self.max_level:
            raise ValueError(f"Invalid zoom level {level}, max is {self.max_level}")

        lvl_w, lvl_h = self.levels[level]
        
        # Calculate bounding box with overlap
        src_x = col * self.tile_size - (self.overlap if col > 0 else 0)
        src_y = row * self.tile_size - (self.overlap if row > 0 else 0)
        
        tile_w = self.tile_size + (self.overlap if col > 0 else 0) + (self.overlap if src_x + self.tile_size < lvl_w else 0)
        tile_h = self.tile_size + (self.overlap if row > 0 else 0) + (self.overlap if src_y + self.tile_size < lvl_h else 0)

        # Clamp to image boundaries
        crop_x1 = max(0, src_x)
        crop_y1 = max(0, src_y)
        crop_x2 = min(lvl_w, src_x + tile_w)
        crop_y2 = min(lvl_h, src_y + tile_h)

        if crop_x2 <= crop_x1 or crop_y2 <= crop_y1:
            # Blank tile
            blank = Image.new("RGB", (self.tile_size, self.tile_size), (255, 255, 255))
            buf = io.BytesIO()
            blank.save(buf, format=format, quality=quality)
            return buf.getvalue()

        level_img = self._get_level_image(level)
        tile_crop = level_img.crop((crop_x1, crop_y1, crop_x2, crop_y2))

        buf = io.BytesIO()
        tile_crop.save(buf, format=format, quality=quality)
        return buf.getvalue()

    def get_thumbnail(self, max_size: int = 1024) -> Image.Image:
        """Generates a fast overview thumbnail for macro analysis & tissue detection."""
        ratio = min(max_size / self.width, max_size / self.height)
        thumb_w = int(self.width * ratio)
        thumb_h = int(self.height * ratio)
        return self.base_image.resize((thumb_w, thumb_h), Image.Resampling.BILINEAR)

    def extract_patch(self, center_x: int, center_y: int, patch_size: int = 256) -> Image.Image:
        """Extracts a full-resolution 40x patch at (center_x, center_y)."""
        x1 = max(0, center_x - patch_size // 2)
        y1 = max(0, center_y - patch_size // 2)
        x2 = min(self.width, x1 + patch_size)
        y2 = min(self.height, y1 + patch_size)
        return self.base_image.crop((x1, y1, x2, y2))
