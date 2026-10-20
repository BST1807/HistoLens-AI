import io
import math
from typing import Dict, Any, List, Tuple
import numpy as np
from PIL import Image
from scipy import ndimage
from skimage import color, morphology, measure, filters

class DigitalPathologyAI:
    """
    AI & Computer Vision Pipeline for Whole Slide Digital Pathology.
    Implements:
      1. Tissue Background Segmentation (Otsu + HSV Chroma filter)
      2. Ruifrok & Johnston Optical Density Stain Deconvolution (Hematoxylin vs Eosin)
      3. Patch-level Tumor Probability Inference
      4. Single-cell Nuclei Detection & Morphometry
      5. Full-Slide Heatmap Generation
    """

    def __init__(self):
        # Ruifrok & Johnston stain matrix for H&E
        # Rows: [Hematoxylin, Eosin, Residual]
        # Normalized optical density vectors
        self.he_matrix = np.array([
            [0.650, 0.704, 0.286],  # Hematoxylin
            [0.072, 0.990, 0.105],  # Eosin
            [0.268, 0.570, 0.776]   # Residual
        ])
        # Invert stain matrix for deconvolution
        self.inv_he_matrix = np.linalg.pinv(self.he_matrix)

    def segment_tissue(self, image: Image.Image, thumbnail_size: int = 1024) -> Tuple[np.ndarray, Image.Image]:
        """
        Segment tissue from clear glass background using HSV saturation + Otsu thresholding.
        Returns:
          binary_mask: 2D boolean array (True = tissue, False = glass background)
          mask_rgb: PIL Image preview showing segmented tissue contours
        """
        # Downsample for fast macro processing
        img_np = np.array(image)
        if img_np.ndim == 2:
            img_np = np.stack([img_np]*3, axis=-1)
        elif img_np.shape[2] == 4:
            img_np = img_np[:, :, :3]

        # Convert to HSV
        hsv = color.rgb2hsv(img_np)
        saturation = hsv[:, :, 1]
        value = hsv[:, :, 2]

        # In histology, glass background is bright white (high value, low saturation)
        # Tissue has color (higher saturation) and absorbs light (lower value)
        sat_thresh = filters.threshold_otsu(saturation) * 0.4
        val_thresh = 0.92

        tissue_mask = (saturation > sat_thresh) & (value < val_thresh)
        
        # Morphological cleanup: remove small dust particles, fill small luminal holes
        tissue_mask = morphology.remove_small_objects(tissue_mask, min_size=64)
        tissue_mask = ndimage.binary_fill_holes(tissue_mask)
        tissue_mask = morphology.binary_dilation(tissue_mask, morphology.disk(2))

        # Create colorful visual mask
        mask_overlay = img_np.copy()
        mask_overlay[~tissue_mask] = (mask_overlay[~tissue_mask] * 0.25).astype(np.uint8)
        mask_img = Image.fromarray(mask_overlay)

        return tissue_mask, mask_img

    def deconvolve_he(self, rgb_patch: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Performs Beer-Lambert optical density deconvolution to separate:
          - Hematoxylin channel (stains DNA/cell nuclei purple)
          - Eosin channel (stains proteins/cytoplasm/stroma pink)
        """
        # Clip to avoid log(0)
        rgb_norm = np.clip(rgb_patch.astype(np.float64) / 255.0, 1e-6, 1.0)
        # Optical Density: OD = -log10(I)
        od = -np.log10(rgb_norm)

        # Deconvolve: C = OD * inv(M)
        stains = np.dot(od.reshape(-1, 3), self.inv_he_matrix)
        stains = np.maximum(stains, 0)
        stains = stains.reshape(rgb_patch.shape)

        h_channel = stains[:, :, 0]
        e_channel = stains[:, :, 1]
        return h_channel, e_channel

    def analyze_patch(self, patch: Image.Image) -> Dict[str, Any]:
        """
        High-magnification (40x/20x) diagnostic analysis of a single tile/patch.
        Detects cell nuclei, computes nuclear crowding, pleomorphism, and tumor probability.
        """
        patch_np = np.array(patch.convert("RGB"))
        h, w, _ = patch_np.shape

        # Step 1: Check if patch is mostly blank glass
        gray = color.rgb2gray(patch_np)
        mean_lum = np.mean(gray)
        hsv = color.rgb2hsv(patch_np)
        mean_sat = np.mean(hsv[:, :, 1])

        if mean_lum > 0.88 and mean_sat < 0.08:
            return {
                "classification": "Background / Glass",
                "tumor_probability": 0.0,
                "confidence": 0.99,
                "nuclei_count": 0,
                "nuclei_density_per_mm2": 0.0,
                "mean_nuclear_area": 0.0,
                "stroma_ratio": 0.0,
                "centroids": []
            }

        # Step 2: Separate Hematoxylin & Eosin
        h_channel, e_channel = self.deconvolve_he(patch_np)

        # Step 3: Segment Cell Nuclei from Hematoxylin Channel
        h_smooth = filters.gaussian(h_channel, sigma=1.0)
        h_thresh = filters.threshold_otsu(h_smooth) * 0.85
        nuclei_binary = h_smooth > h_thresh
        nuclei_binary = morphology.remove_small_objects(nuclei_binary, min_size=15)
        nuclei_binary = ndimage.binary_fill_holes(nuclei_binary)

        # Label nuclei instances
        labeled_nuclei, num_nuclei = ndimage.label(nuclei_binary)
        properties = measure.regionprops(labeled_nuclei)

        centroids = []
        nuclear_areas = []
        eccentricities = []
        for prop in properties:
            centroids.append([int(prop.centroid[1]), int(prop.centroid[0])])  # x, y
            nuclear_areas.append(prop.area)
            eccentricities.append(prop.eccentricity)

        avg_nuclear_area = float(np.mean(nuclear_areas)) if nuclear_areas else 0.0
        avg_eccentricity = float(np.mean(eccentricities)) if eccentricities else 0.0

        # Histopathology magnification scaling: assume 0.5 um/pixel (standard 20x)
        # Patch is 256x256 px = 128x128 um = 0.016384 mm2
        patch_area_mm2 = (w * 0.5 / 1000.0) * (h * 0.5 / 1000.0)
        density_per_mm2 = float(num_nuclei / patch_area_mm2) if patch_area_mm2 > 0 else 0.0

        # Step 4: Stroma vs Epithelial / Tumor Ratio
        e_mean = float(np.mean(e_channel))
        h_mean = float(np.mean(h_channel))
        stroma_ratio = float(e_mean / (h_mean + e_mean + 1e-6))

        # Step 5: Pathological Malignancy Scoring (Tumor Criteria)
        # Tumor characteristics: high nuclear density (> 3000/mm2), enlarged nuclear size, high pleomorphism
        score = 0.0
        if density_per_mm2 > 2500:
            score += 0.35 * min(1.0, (density_per_mm2 - 2500) / 4000)
        if avg_nuclear_area > 75:
            score += 0.35 * min(1.0, (avg_nuclear_area - 75) / 100)
        if avg_eccentricity > 0.65:
            score += 0.15 * min(1.0, (avg_eccentricity - 0.65) / 0.3)
        if stroma_ratio < 0.45:  # Tumor replaces normal stroma
            score += 0.15

        tumor_prob = float(np.clip(score, 0.02, 0.98))

        if tumor_prob > 0.60:
            classification = "Infiltrating Tumor / Malignant"
        elif tumor_prob > 0.35:
            classification = "Atypical / Suspicious Stroma"
        else:
            classification = "Benign / Normal Tissue"

        return {
            "classification": classification,
            "tumor_probability": round(tumor_prob, 3),
            "confidence": round(float(max(tumor_prob, 1 - tumor_prob)), 3),
            "nuclei_count": int(num_nuclei),
            "nuclei_density_per_mm2": round(density_per_mm2, 1),
            "mean_nuclear_area": round(avg_nuclear_area, 1),
            "stroma_ratio": round(stroma_ratio, 3),
            "centroids": centroids[:100]  # First 100 centroids for visual inspection overlay
        }

    def generate_slide_heatmap(self, base_image: Image.Image, grid_step: int = 64) -> Dict[str, Any]:
        """
        Scans across the entire slide in a grid, runs patch inference,
        and generates a multi-scale probability heatmap overlay.
        """
        w, h = base_image.size
        # For full slide heatmap, compute on downsampled overview for near-instant 1-second generation
        eval_w = min(1024, w)
        eval_h = int(h * (eval_w / w))
        eval_img = base_image.resize((eval_w, eval_h), Image.Resampling.BILINEAR)

        # Tissue mask
        tissue_mask, _ = self.segment_tissue(eval_img)

        cols = int(math.ceil(eval_w / grid_step))
        rows = int(math.ceil(eval_h / grid_step))
        
        prob_matrix = np.zeros((rows, cols), dtype=np.float32)
        total_tissue_tiles = 0
        tumor_tiles = 0

        for r in range(rows):
            for c in range(cols):
                x1 = c * grid_step
                y1 = r * grid_step
                x2 = min(eval_w, x1 + grid_step)
                y2 = min(eval_h, y1 + grid_step)

                # Check if center is tissue
                cx = (x1 + x2) // 2
                cy = (y1 + y2) // 2
                if not tissue_mask[min(cy, eval_h - 1), min(cx, eval_w - 1)]:
                    prob_matrix[r, c] = 0.0
                    continue

                total_tissue_tiles += 1
                tile_crop = eval_img.crop((x1, y1, x2, y2))
                res = self.analyze_patch(tile_crop)
                p = res["tumor_probability"]
                prob_matrix[r, c] = p

                if p >= 0.50:
                    tumor_tiles += 1

        tumor_burden_pct = round((tumor_tiles / max(1, total_tissue_tiles)) * 100, 2)

        # Generate RGBA color heatmap image
        # High probability = Fire / Crimson Red
        # Mid probability = Amber Yellow
        # Low probability = Cyan / Blue
        heatmap_rgba = np.zeros((rows, cols, 4), dtype=np.uint8)
        for r in range(rows):
            for c in range(cols):
                p = prob_matrix[r, c]
                if p <= 0.02:
                    heatmap_rgba[r, c] = [0, 0, 0, 0]  # Transparent
                elif p < 0.35:
                    # Blue to Cyan
                    norm = p / 0.35
                    heatmap_rgba[r, c] = [0, int(150 * norm), 255, 140]
                elif p < 0.65:
                    # Amber / Yellow
                    norm = (p - 0.35) / 0.30
                    heatmap_rgba[r, c] = [255, int(165 + 70 * norm), 0, 180]
                else:
                    # Bright Crimson Red
                    norm = (p - 0.65) / 0.35
                    heatmap_rgba[r, c] = [255, int(50 * (1 - norm)), int(50 * (1 - norm)), 220]

        # Resize heatmap image to match full slide dimensions
        heatmap_img = Image.fromarray(heatmap_rgba, mode="RGBA").resize((w, h), Image.Resampling.BILINEAR)
        buf = io.BytesIO()
        heatmap_img.save(buf, format="PNG")
        heatmap_bytes = buf.getvalue()

        return {
            "tumor_burden_pct": tumor_burden_pct,
            "total_tissue_tiles": total_tissue_tiles,
            "tumor_tiles": tumor_tiles,
            "grid_size": {"rows": rows, "cols": cols},
            "heatmap_png_bytes": heatmap_bytes
        }
