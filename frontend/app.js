// ==========================================================================
// HistoLens AI - Interactive Digital Pathology Client Application
// ==========================================================================

let viewer = null;
let currentSlideId = null;
let currentMetadata = null;
let heatmapItem = null;
let activeTool = 'pan'; // 'pan' | 'roi'
let roiMarkerOverlay = null;

let currentScope = 'roi'; // 'roi' | 'slide'
let slideMetrics = null;
let lastRoiData = null;

document.addEventListener('DOMContentLoaded', () => {
    lucide.createIcons();
    initUI();
    loadSlides();
});

function initUI() {
    // Tool buttons
    const btnPan = document.getElementById('tool-pan');
    const btnRoi = document.getElementById('tool-roi');

    btnPan.addEventListener('click', () => setTool('pan'));
    btnRoi.addEventListener('click', () => setTool('roi'));

    // Scope toggle buttons (Selected ROI vs Whole Slide)
    const btnScopeRoi = document.getElementById('scope-roi');
    const btnScopeSlide = document.getElementById('scope-slide');

    if (btnScopeRoi && btnScopeSlide) {
        btnScopeRoi.addEventListener('click', () => setScope('roi'));
        btnScopeSlide.addEventListener('click', () => setScope('slide'));
    }

    // Heatmap controls
    const toggleHeatmapBtn = document.getElementById('toggle-heatmap');
    const opacitySlider = document.getElementById('heatmap-opacity');
    const opacityVal = document.getElementById('opacity-val');

    toggleHeatmapBtn.addEventListener('click', () => {
        const isActive = toggleHeatmapBtn.classList.toggle('active');
        if (heatmapItem) {
            heatmapItem.setOpacity(isActive ? opacitySlider.value / 100 : 0);
        }
    });

    opacitySlider.addEventListener('input', (e) => {
        const val = e.target.value;
        opacityVal.textContent = `${val}%`;
        if (heatmapItem && toggleHeatmapBtn.classList.contains('active')) {
            heatmapItem.setOpacity(val / 100);
        }
    });

    // Slide dropdown
    const slideSelect = document.getElementById('slide-select');
    slideSelect.addEventListener('change', (e) => {
        if (e.target.value) {
            loadSlide(e.target.value);
        }
    });

    // Upload slide
    const uploadInput = document.getElementById('upload-input');
    uploadInput.addEventListener('change', async (e) => {
        const file = e.target.files[0];
        if (!file) return;

        showLoader(`Uploading ${file.name}...`);
        const formData = new FormData();
        formData.append('file', file);

        try {
            const resp = await fetch('/api/upload', { method: 'POST', body: formData });
            const data = await resp.json();
            await loadSlides();
            loadSlide(data.filename);
        } catch (err) {
            alert('Upload failed: ' + err.message);
            hideLoader();
        }
    });

    // Export PDF
    const btnExportPdf = document.getElementById('btn-export-pdf');
    btnExportPdf.addEventListener('click', () => {
        if (!currentSlideId) return;
        window.open(`/api/slide/${currentSlideId}/report.pdf`, '_blank');
    });

    // Fullscreen toggle
    const btnFullscreen = document.getElementById('btn-fullscreen');
    btnFullscreen.addEventListener('click', () => {
        if (!document.fullscreenElement) {
            document.documentElement.requestFullscreen();
        } else {
            document.exitFullscreen();
        }
    });
}

function setTool(tool) {
    activeTool = tool;
    document.getElementById('tool-pan').classList.toggle('active', tool === 'pan');
    document.getElementById('tool-roi').classList.toggle('active', tool === 'roi');

    const osdCanvas = document.querySelector('.osd-canvas');
    if (tool === 'roi') {
        osdCanvas.style.cursor = 'crosshair';
    } else {
        osdCanvas.style.cursor = 'grab';
    }
}

async function loadSlides() {
    try {
        const resp = await fetch('/api/slides');
        const data = await resp.json();
        const select = document.getElementById('slide-select');
        select.innerHTML = '';

        if (!data.slides || data.slides.length === 0) {
            select.innerHTML = '<option value="">No slides found</option>';
            return;
        }

        data.slides.forEach((s) => {
            const opt = document.createElement('option');
            opt.value = s.id;
            opt.textContent = `${s.filename} (${s.size_mb} MB - ${s.format})`;
            select.appendChild(opt);
        });

        // Load first slide automatically
        if (data.slides.length > 0 && !currentSlideId) {
            loadSlide(data.slides[0].id);
        }
    } catch (err) {
        console.error('Error loading slide list:', err);
    }
}

async function loadSlide(slideId) {
    currentSlideId = slideId;
    showLoader(`Loading ${slideId}...`);

    try {
        // Fetch metadata
        const metaResp = await fetch(`/api/slide/${slideId}/metadata`);
        const dziMeta = await metaResp.json();
        currentMetadata = dziMeta.Image;

        const imgWidth = currentMetadata.Size.Width;
        const imgHeight = currentMetadata.Size.Height;
        document.getElementById('slide-meta-badge').textContent = `${imgWidth} × ${imgHeight} px`;

        // Initialize or update OpenSeadragon
        initOpenSeadragon(slideId, currentMetadata);

        // Fetch quantitative biomarkers and update UI
        fetchMetrics(slideId);

    } catch (err) {
        console.error('Failed to load slide:', err);
        alert('Could not load slide: ' + err.message);
        hideLoader();
    }
}

function initOpenSeadragon(slideId, metadata) {
    const tileSource = {
        width: metadata.Size.Width,
        height: metadata.Size.Height,
        tileSize: metadata.TileSize,
        tileOverlap: metadata.Overlap,
        minLevel: 0,
        maxLevel: Math.ceil(Math.log2(Math.max(metadata.Size.Width, metadata.Size.Height))),
        getTileUrl: function(level, x, y) {
            return `/api/slide/${slideId}/tile/${level}/${x}_${y}.jpg`;
        }
    };

    if (viewer) {
        viewer.destroy();
    }

    viewer = OpenSeadragon({
        id: "openseadragon-viewer",
        prefixUrl: "https://cdnjs.cloudflare.com/ajax/libs/openseadragon/4.1.1/images/",
        tileSources: tileSource,
        showNavigationControl: false,
        showNavigator: true,
        navigatorPosition: "BOTTOM_RIGHT",
        navigatorSizeRatio: 0.18,
        animationTime: 0.35,
        blendTime: 0.1,
        minZoomImageRatio: 0.9,
        maxZoomPixelRatio: 3.0,
        visibilityRatio: 0.8,
        constrainDuringPan: true
    });

    viewer.addHandler('open', () => {
        hideLoader();
        loadHeatmapOverlay(slideId);
        // Automatically inspect center ROI patch on initial load
        const centerX = Math.round(metadata.Size.Width * 0.48);
        const centerY = Math.round(metadata.Size.Height * 0.48);
        triggerRoiInspection(centerX, centerY);
    });

    // Update magnification readout dynamically
    viewer.addHandler('animation', () => {
        if (!viewer || !viewer.viewport) return;
        const zoom = viewer.viewport.getZoom(true);
        const homeZoom = viewer.viewport.getHomeZoom();
        const relativeZoom = zoom / homeZoom;
        
        let magText = '1.0x';
        if (relativeZoom >= 25) {
            magText = '40.0x (High Power)';
        } else if (relativeZoom >= 12) {
            magText = '20.0x (Diagnostic)';
        } else if (relativeZoom >= 6) {
            magText = '10.0x (Survey)';
        } else if (relativeZoom >= 2.5) {
            magText = '4.0x (Low Power)';
        } else {
            magText = `${relativeZoom.toFixed(1)}x (Overview)`;
        }
        document.getElementById('mag-text').textContent = magText;
    });

    // Official OpenSeadragon canvas-click handler (fires on clicks, ignores drag/pan)
    viewer.addHandler('canvas-click', function(event) {
        if (!event.quick) return; // Only process clean clicks, not pan drags
        event.preventGesture = true;

        const viewportPoint = viewer.viewport.pointFromPixel(event.position);
        const imagePoint = viewer.viewport.viewportToImageCoordinates(viewportPoint);
        const imgX = Math.round(imagePoint.x);
        const imgY = Math.round(imagePoint.y);

        if (imgX >= 0 && imgX <= metadata.Size.Width && imgY >= 0 && imgY <= metadata.Size.Height) {
            triggerRoiInspection(imgX, imgY);
            addRoiMarkerOnCanvas(imagePoint);
        }
    });
}

function loadHeatmapOverlay(slideId) {
    if (!viewer) return;

    // Load AI Heatmap as a secondary tiled layer
    viewer.addSimpleImage({
        url: `/api/slide/${slideId}/heatmap`,
        opacity: 0.65,
        success: function(event) {
            heatmapItem = event.item;
        },
        error: function(err) {
            console.warn('Heatmap layer not yet ready:', err);
        }
    });
}

function addRoiMarkerOnCanvas(imagePoint) {
    if (!viewer) return;

    if (roiMarkerOverlay) {
        viewer.removeOverlay(roiMarkerOverlay);
    }

    const marker = document.createElement('div');
    marker.className = 'roi-canvas-marker';
    marker.style.width = '24px';
    marker.style.height = '24px';
    marker.style.border = '2px solid #06B6D4';
    marker.style.borderRadius = '50%';
    marker.style.boxShadow = '0 0 12px #06B6D4, inset 0 0 8px #06B6D4';
    marker.style.transform = 'translate(-50%, -50%)';
    marker.style.pointerEvents = 'none';

    viewer.addOverlay({
        element: marker,
        location: viewer.viewport.imageToViewportCoordinates(imagePoint)
    });
    roiMarkerOverlay = marker;
}

function setScope(scope) {
    currentScope = scope;
    const btnRoi = document.getElementById('scope-roi');
    const btnSlide = document.getElementById('scope-slide');
    if (btnRoi && btnSlide) {
        btnRoi.classList.toggle('active', scope === 'roi');
        btnSlide.classList.toggle('active', scope === 'slide');
    }
    renderDashboard();
}

function renderDashboard() {
    if (currentScope === 'roi' && lastRoiData) {
        document.getElementById('card-tag-label').textContent = 'Selected Patch Assessment';
        document.getElementById('hero-metric-desc').textContent = 'Local Malignancy Risk';

        const probPct = (lastRoiData.tumor_probability * 100).toFixed(1);
        document.getElementById('metric-tumor-burden').textContent = probPct;
        document.getElementById('tumor-burden-progress').style.width = `${Math.min(100, probPct)}%`;

        const riskBadge = document.getElementById('risk-badge');
        riskBadge.textContent = lastRoiData.classification;
        riskBadge.removeAttribute('style');
        if (lastRoiData.tumor_probability > 0.6) {
            riskBadge.className = 'risk-badge risk-high';
        } else if (lastRoiData.tumor_probability > 0.35) {
            riskBadge.className = 'risk-badge risk-moderate';
        } else {
            riskBadge.className = 'risk-badge';
            riskBadge.style.backgroundColor = 'rgba(16, 185, 129, 0.15)';
            riskBadge.style.color = '#10B981';
            riskBadge.style.border = '1px solid rgba(16, 185, 129, 0.3)';
        }

        document.getElementById('box-1-label').textContent = 'Patch Area';
        document.getElementById('metric-tissue-area').textContent = '0.016 mm²';
        document.getElementById('box-1-sub').textContent = 'Local 40x Window';

        document.getElementById('box-2-label').textContent = 'Nuclei Count';
        document.getElementById('metric-tumor-area').textContent = `${lastRoiData.nuclei_count} cells`;
        document.getElementById('box-2-sub').textContent = 'Single-cell Centroids';

        document.getElementById('box-3-label').textContent = 'Stroma Ratio';
        document.getElementById('metric-tsr').textContent = `${(lastRoiData.stroma_ratio * 100).toFixed(1)}%`;
        document.getElementById('box-3-sub').textContent = 'Eosin Stain Share';

        document.getElementById('box-4-label').textContent = 'Nuclear Density';
        document.getElementById('metric-nuclear-density').textContent = `${lastRoiData.nuclei_density_per_mm2} /mm²`;
        document.getElementById('box-4-sub').textContent = 'Local Proliferation';

    } else if (slideMetrics) {
        document.getElementById('card-tag-label').textContent = 'WHO Disease Stratification';
        document.getElementById('hero-metric-desc').textContent = 'Slide Tumor Burden';

        document.getElementById('metric-tumor-burden').textContent = slideMetrics.tumor_burden_pct;
        document.getElementById('tumor-burden-progress').style.width = `${Math.min(100, slideMetrics.tumor_burden_pct)}%`;

        const riskBadge = document.getElementById('risk-badge');
        riskBadge.textContent = slideMetrics.risk_level;
        riskBadge.removeAttribute('style');
        if (slideMetrics.tumor_burden_pct > 35) {
            riskBadge.className = 'risk-badge risk-high';
        } else {
            riskBadge.className = 'risk-badge risk-moderate';
        }

        document.getElementById('box-1-label').textContent = 'Tissue Area';
        document.getElementById('metric-tissue-area').textContent = `${slideMetrics.tissue_area_mm2} mm²`;
        document.getElementById('box-1-sub').textContent = 'Viable Specimen';

        document.getElementById('box-2-label').textContent = 'Tumor Area';
        document.getElementById('metric-tumor-area').textContent = `${slideMetrics.tumor_area_mm2} mm²`;
        document.getElementById('box-2-sub').textContent = 'Infiltrating Mass';

        document.getElementById('box-3-label').textContent = 'TSR Ratio';
        document.getElementById('metric-tsr').textContent = `${slideMetrics.tumor_to_stroma_ratio}`;
        document.getElementById('box-3-sub').textContent = 'Tumor-to-Stroma';

        document.getElementById('box-4-label').textContent = 'Nuclear Density';
        document.getElementById('metric-nuclear-density').textContent = `${slideMetrics.estimated_nuclei_density} /mm²`;
        document.getElementById('box-4-sub').textContent = 'Cell Proliferation';
    }
}

async function triggerRoiInspection(x, y) {
    const placeholder = document.getElementById('roi-placeholder');
    const patchImg = document.getElementById('roi-patch-image');
    const detailsPanel = document.getElementById('roi-results-panel');
    const badge = document.getElementById('roi-status-badge');

    badge.textContent = 'Analyzing...';

    try {
        const resp = await fetch(`/api/slide/${currentSlideId}/analyze_patch`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ x: x, y: y, size: 256 })
        });
        const data = await resp.json();

        lastRoiData = data;

        // Update ROI card
        placeholder.style.display = 'none';
        patchImg.style.display = 'block';
        patchImg.src = data.annotated_image_b64;
        detailsPanel.style.display = 'flex';

        const diagElem = document.getElementById('roi-diagnosis');
        diagElem.textContent = data.classification;
        if (data.tumor_probability > 0.5) {
            diagElem.className = 'detail-val highlight';
        } else {
            diagElem.className = 'detail-val';
            diagElem.style.color = '#10B981';
        }

        document.getElementById('roi-prob').textContent = `${(data.tumor_probability * 100).toFixed(1)}%`;
        document.getElementById('roi-nuclei-count').textContent = `${data.nuclei_count} cells (${data.nuclei_density_per_mm2} /mm²)`;
        document.getElementById('roi-stroma-ratio').textContent = `${(data.stroma_ratio * 100).toFixed(1)}%`;

        badge.textContent = `(${x}, ${y})`;

        // Automatically update the top dashboard metrics to reflect the clicked area
        setScope('roi');

    } catch (err) {
        console.error('ROI analysis error:', err);
        badge.textContent = 'Error';
    }
}

async function fetchMetrics(slideId) {
    try {
        const resp = await fetch(`/api/slide/${slideId}/metrics`);
        const metrics = await resp.json();
        slideMetrics = metrics;

        // Render dashboard with active scope
        renderDashboard();

    } catch (err) {
        console.error('Failed to fetch slide metrics:', err);
    }
}

function showLoader(msg = 'Processing...') {
    const loader = document.getElementById('viewer-loader');
    const status = document.getElementById('loader-status');
    status.textContent = msg;
    loader.classList.remove('hidden');
}

function hideLoader() {
    const loader = document.getElementById('viewer-loader');
    loader.classList.add('hidden');
}
