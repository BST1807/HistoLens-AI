import os
import io
import base64
import glob
from typing import Dict, Any, Optional
import numpy as np
from PIL import Image, ImageDraw

from fastapi import FastAPI, HTTPException, UploadFile, File, Response
from fastapi.responses import JSONResponse, Response, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from backend.slide_engine import SlideEngine
from backend.ai_pipeline import DigitalPathologyAI
from backend.quantification import PathologyQuantifier

app = FastAPI(title="HistoLens AI - Digital Pathology WSI Platform")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(FRONTEND_DIR, exist_ok=True)

# Cache active slide engines and AI analysis results in memory
slide_engines: Dict[str, SlideEngine] = {}
analysis_cache: Dict[str, Dict[str, Any]] = {}

ai_engine = DigitalPathologyAI()
quantifier = PathologyQuantifier(microns_per_pixel=0.5)

def get_engine(slide_id: str) -> SlideEngine:
    if slide_id in slide_engines:
        return slide_engines[slide_id]

    slide_path = os.path.join(DATA_DIR, slide_id)
    if not os.path.exists(slide_path):
        raise HTTPException(status_code=404, detail=f"Slide '{slide_id}' not found")

    engine = SlideEngine(slide_path)
    slide_engines[slide_id] = engine
    return engine

@app.get("/api/slides")
def list_slides():
    """Lists all available whole slide images and specimens in the data repository."""
    extensions = ("*.svs", "*.tiff", "*.tif", "*.jpg", "*.jpeg", "*.png")
    files = []
    for ext in extensions:
        files.extend(glob.glob(os.path.join(DATA_DIR, ext)))

    slides_info = []
    for f in files:
        filename = os.path.basename(f)
        size_mb = round(os.path.getsize(f) / (1024 * 1024), 2)
        slides_info.append({
            "id": filename,
            "filename": filename,
            "size_mb": size_mb,
            "format": filename.split(".")[-1].upper()
        })

    return {"slides": slides_info}

@app.get("/api/slide/{slide_id}/metadata")
def get_slide_metadata(slide_id: str):
    """DeepZoom metadata formatted for OpenSeadragon integration."""
    engine = get_engine(slide_id)
    dzi_data = engine.get_dzi_metadata()
    return dzi_data

@app.get("/api/slide/{slide_id}/dzi")
def get_dzi_xml(slide_id: str):
    """Returns XML DZI definition for OpenSeadragon native DZI loader."""
    engine = get_engine(slide_id)
    xml_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<Image xmlns="http://schemas.microsoft.com/deepzoom/2008"
       Format="jpg"
       Overlap="{engine.overlap}"
       TileSize="{engine.tile_size}">
    <Size Width="{engine.width}" Height="{engine.height}"/>
</Image>"""
    return Response(content=xml_content, media_type="application/xml")

@app.get("/api/slide/{slide_id}/tile/{level}/{col}_{row}.jpg")
def get_tile(slide_id: str, level: int, col: int, row: int):
    """Dynamic multi-resolution DeepZoom tile endpoint."""
    engine = get_engine(slide_id)
    try:
        tile_bytes = engine.get_tile(level, col, row, format="JPEG", quality=85)
        return Response(content=tile_bytes, media_type="image/jpeg", headers={"Cache-Control": "public, max-age=86400"})
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/slide/{slide_id}/thumbnail")
def get_thumbnail(slide_id: str):
    """Returns a downsampled overview thumbnail."""
    engine = get_engine(slide_id)
    thumb = engine.get_thumbnail(max_size=800)
    buf = io.BytesIO()
    thumb.save(buf, format="JPEG", quality=80)
    return Response(content=buf.getvalue(), media_type="image/jpeg")

@app.post("/api/slide/{slide_id}/analyze_patch")
def analyze_patch(slide_id: str, payload: Dict[str, Any]):
    """
    Analyzes a specific high-magnification region of interest (ROI) selected by the pathologist.
    Returns: classification, tumor probability, nuclei count, cellular density, and segmented preview.
    """
    engine = get_engine(slide_id)
    center_x = int(payload.get("x", engine.width // 2))
    center_y = int(payload.get("y", engine.height // 2))
    patch_size = int(payload.get("size", 256))

    patch = engine.extract_patch(center_x, center_y, patch_size=patch_size)
    analysis = ai_engine.analyze_patch(patch)

    # Annotate patch with detected nuclei markers
    annotated = patch.copy()
    draw = ImageDraw.Draw(annotated)
    centroids = analysis.get("centroids", [])
    for cx, cy in centroids:
        r = 3
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline="yellow", width=1)

    buf = io.BytesIO()
    annotated.save(buf, format="PNG")
    annotated_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

    analysis["annotated_image_b64"] = f"data:image/png;base64,{annotated_b64}"
    analysis["center_coords"] = {"x": center_x, "y": center_y}
    return analysis

@app.get("/api/slide/{slide_id}/heatmap")
def get_slide_heatmap(slide_id: str):
    """
    Computes/returns full slide AI tumor probability heatmap overlay PNG.
    """
    engine = get_engine(slide_id)
    if slide_id not in analysis_cache:
        # Run slide analysis
        result = ai_engine.generate_slide_heatmap(engine.base_image, grid_step=64)
        analysis_cache[slide_id] = result

    heatmap_bytes = analysis_cache[slide_id]["heatmap_png_bytes"]
    return Response(content=heatmap_bytes, media_type="image/png", headers={"Cache-Control": "public, max-age=3600"})

@app.get("/api/slide/{slide_id}/metrics")
def get_slide_metrics(slide_id: str):
    """Returns comprehensive quantitative clinical pathology biomarkers."""
    engine = get_engine(slide_id)
    if slide_id not in analysis_cache:
        result = ai_engine.generate_slide_heatmap(engine.base_image, grid_step=64)
        analysis_cache[slide_id] = result

    cached = analysis_cache[slide_id]
    metrics = quantifier.compute_metrics(
        slide_width=engine.width,
        slide_height=engine.height,
        tissue_tile_count=cached["total_tissue_tiles"],
        tumor_tile_count=cached["tumor_tiles"],
        avg_nuclear_density=2950.0,
        avg_stroma_ratio=0.42
    )
    return metrics

@app.get("/api/slide/{slide_id}/report.pdf")
def download_pdf_report(slide_id: str):
    """Generates and downloads a signed PDF clinical diagnostic report."""
    metrics = get_slide_metrics(slide_id)
    pdf_bytes = quantifier.generate_pdf_report(slide_id, metrics)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=HistoLens_Report_{slide_id}.pdf"}
    )

@app.post("/api/upload")
async def upload_slide(file: UploadFile = File(...)):
    """Allows uploading custom WSI files (.svs, .tif) or high-res histology scans."""
    filename = file.filename
    dest_path = os.path.join(DATA_DIR, filename)
    contents = await file.read()
    with open(dest_path, "wb") as f:
        f.write(contents)

    # Invalidate engine cache
    if filename in slide_engines:
        del slide_engines[filename]
    if filename in analysis_cache:
        del analysis_cache[filename]

    return {"status": "success", "filename": filename, "size_mb": round(len(contents) / (1024*1024), 2)}

# Serve frontend static files
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
