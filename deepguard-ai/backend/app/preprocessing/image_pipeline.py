"""Image preprocessing pipeline — pure computer vision operations.

Pipeline: resize → normalize → RGB convert → face crop → CLAHE →
          denoise → ELA → FFT → DCT → wavelet → edge maps →
          metadata extraction → hashing
"""

import base64
import io
import math
import struct
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image

from app.config import settings


# ── Resize ──────────────────────────────────────────────────────────────

def resize_image(image: np.ndarray, target_size: int = 384) -> np.ndarray:
    h, w = image.shape[:2]
    if max(h, w) <= target_size:
        return image
    scale = target_size / max(h, w)
    new_w, new_h = int(w * scale), int(h * scale)
    return cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_AREA)


# ── Normalize ───────────────────────────────────────────────────────────

def normalize_image(image: np.ndarray) -> np.ndarray:
    return image.astype(np.float32) / 255.0


# ── RGB Conversion ──────────────────────────────────────────────────────

def ensure_rgb(image: np.ndarray) -> np.ndarray:
    if len(image.shape) == 2:
        return cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
    if image.shape[2] == 4:
        return cv2.cvtColor(image, cv2.COLOR_RGBA2RGB)
    if image.shape[2] == 3:
        return image
    return image


# ── Face Crop ───────────────────────────────────────────────────────────

def crop_largest_face(image: np.ndarray) -> np.ndarray | None:
    gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    face_cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )
    faces = face_cascade.detectMultiScale(gray, 1.1, 5)
    if len(faces) == 0:
        return None
    x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
    return image[y:y + h, x:x + w]


# ── CLAHE (Contrast Enhancement) ───────────────────────────────────────

def apply_clahe(image: np.ndarray) -> np.ndarray:
    lab = cv2.cvtColor(image, cv2.COLOR_RGB2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=settings.clahe_clip_limit, tileGridSize=(8, 8))
    l = clahe.apply(l)
    enhanced = cv2.merge([l, a, b])
    return cv2.cvtColor(enhanced, cv2.COLOR_LAB2RGB)


# ── Denoising ──────────────────────────────────────────────────────────

def denoise_image(image: np.ndarray, strength: int | None = None) -> np.ndarray:
    if strength is None:
        strength = settings.denoise_strength
    return cv2.fastNlMeansDenoisingColored(image, None, strength, strength, 7, 21)


# ── Error Level Analysis ───────────────────────────────────────────────

def generate_ela(image: np.ndarray, quality: int | None = None) -> np.ndarray:
    if quality is None:
        quality = settings.ela_quality
    ret, buf = cv2.imencode(".jpg", cv2.cvtColor(image, cv2.COLOR_RGB2BGR),
                            [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ret:
        return np.zeros_like(image)
    recompressed = cv2.imdecode(buf, cv2.IMREAD_COLOR)
    recompressed = cv2.cvtColor(recompressed, cv2.COLOR_BGR2RGB)
    diff = cv2.absdiff(image.astype(np.float32), recompressed.astype(np.float32))
    diff = (diff / diff.max() * 255).astype(np.uint8) if diff.max() > 0 else diff.astype(np.uint8)
    return diff


# ── FFT (Frequency Spectrum) ──────────────────────────────────────────

def generate_fft(image: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY).astype(np.float32)
    f = np.fft.fft2(gray)
    fshift = np.fft.fftshift(f)
    magnitude = 20 * np.log(np.abs(fshift) + 1)
    magnitude = ((magnitude - magnitude.min()) / (magnitude.max() - magnitude.min() + 1e-8) * 255).astype(np.uint8)
    return magnitude


# ── DCT Compression Features ───────────────────────────────────────────

def generate_dct(image: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY).astype(np.float32)
    dct_coeffs = cv2.dct(gray)
    dct_vis = np.log(np.abs(dct_coeffs) + 1)
    dct_vis = ((dct_vis - dct_vis.min()) / (dct_vis.max() - dct_vis.min() + 1e-8) * 255).astype(np.uint8)
    return dct_vis


# ── Wavelet (Haar) ────────────────────────────────────────────────────

def generate_wavelet(image: np.ndarray) -> dict[str, np.ndarray]:
    gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY).astype(np.float32)
    h, w = gray.shape
    h = h - (h % 2)
    w = w - (w % 2)
    gray = gray[:h, :w]
    LL = (gray[0::2, 0::2] + gray[0::2, 1::2] + gray[1::2, 0::2] + gray[1::2, 1::2]) / 4
    LH = (gray[0::2, 0::2] - gray[0::2, 1::2] + gray[1::2, 0::2] - gray[1::2, 1::2]) / 4
    HL = (gray[0::2, 0::2] + gray[0::2, 1::2] - gray[1::2, 0::2] - gray[1::2, 1::2]) / 4
    HH = (gray[0::2, 0::2] - gray[0::2, 1::2] - gray[1::2, 0::2] + gray[1::2, 1::2]) / 4
    return {"LL": LL, "LH": LH, "HL": HL, "HH": HH}


# ── Edge Maps ─────────────────────────────────────────────────────────

def generate_edge_maps(image: np.ndarray) -> dict[str, np.ndarray]:
    gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    canny = cv2.Canny(gray, 100, 200)
    sobel_x = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    sobel_y = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    sobel = cv2.magnitude(sobel_x, sobel_y)
    sobel = ((sobel / sobel.max()) * 255).astype(np.uint8) if sobel.max() > 0 else sobel.astype(np.uint8)
    laplacian = cv2.Laplacian(gray, cv2.CV_32F)
    laplacian = ((laplacian - laplacian.min()) / (laplacian.max() - laplacian.min() + 1e-8) * 255).astype(np.uint8)
    return {"canny": canny, "sobel": sobel, "laplacian": laplacian}


# ── Metadata ──────────────────────────────────────────────────────────

def extract_image_metadata(file_path: str) -> dict[str, Any]:
    meta: dict[str, Any] = {}
    try:
        import exifread
        with open(file_path, "rb") as f:
            tags = exifread.process_file(f, details=False)
        meta["tag_count"] = len(tags)
        camera = tags.get("Image Make", "")
        model = tags.get("Image Model", "")
        if camera or model:
            meta["camera"] = f"{camera} {model}".strip()
        software = tags.get("Image Software", "")
        if software:
            meta["software"] = str(software)
        gps_lat = tags.get("GPS GPSLatitude")
        gps_lon = tags.get("GPS GPSLongitude")
        if gps_lat and gps_lon:
            meta["gps_present"] = True
        create_time = tags.get("EXIF DateTimeOriginal") or tags.get("Image DateTime")
        if create_time:
            meta["creation_time"] = str(create_time)
    except Exception:
        pass
    return meta


# ── Hashing ───────────────────────────────────────────────────────────

def compute_hashes(file_path: str) -> dict[str, str]:
    import hashlib
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            sha256.update(chunk)
    phash = ""
    try:
        from PIL import Image
        import imagehash
        phash = str(imagehash.phash(Image.open(file_path)))
    except Exception:
        pass
    return {"sha256": sha256.hexdigest(), "phash": phash}


# ── Diagnostic image encoding ─────────────────────────────────────────

def _array_to_base64(arr: np.ndarray, quality: int = 85) -> str:
    """Convert a numpy array (uint8, HxW or HxWxC) to a base64 JPEG string."""
    if arr.dtype != np.uint8:
        arr = np.clip(arr, 0, 255).astype(np.uint8)
    if len(arr.shape) == 2:
        arr = cv2.cvtColor(arr, cv2.COLOR_GRAY2RGB)
    elif arr.shape[2] == 4:
        arr = cv2.cvtColor(arr, cv2.COLOR_RGBA2RGB)
    success, buf = cv2.imencode(".jpg", cv2.cvtColor(arr, cv2.COLOR_RGB2BGR),
                                [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not success:
        return ""
    return base64.b64encode(buf).decode("utf-8")


def _generate_diagnostic_images(
    rgb: np.ndarray,
    file_path: str,
    ela_img: np.ndarray | None = None,
    fft_img: np.ndarray | None = None,
    dct_img: np.ndarray | None = None,
    wavelet_hh: np.ndarray | None = None,
    edge_canny: np.ndarray | None = None,
    edge_sobel: np.ndarray | None = None,
    edge_laplacian: np.ndarray | None = None,
) -> dict[str, str]:
    """Generate base64-encoded diagnostic visualization images."""
    diag: dict[str, str] = {}
    if ela_img is not None:
        diag["ela"] = _array_to_base64(ela_img)
    if fft_img is not None:
        diag["fft"] = _array_to_base64(fft_img)
    if dct_img is not None:
        diag["dct"] = _array_to_base64(dct_img)
    if wavelet_hh is not None:
        diag["wavelet_hh"] = _array_to_base64(wavelet_hh)
    if edge_canny is not None:
        diag["edges_canny"] = _array_to_base64(edge_canny)
    if edge_sobel is not None:
        diag["edges_sobel"] = _array_to_base64(edge_sobel)
    if edge_laplacian is not None:
        diag["edges_laplacian"] = _array_to_base64(edge_laplacian)
    return diag


# ── Anomaly region generation ──────────────────────────────────────────

def _generate_anomaly_regions(
    ela_img: np.ndarray | None,
    fft_img: np.ndarray | None,
    noise_map: np.ndarray | None,
    wavelet_hh: np.ndarray | None,
    edge_canny: np.ndarray | None,
    image_shape: tuple[int, int],
) -> list[dict[str, Any]]:
    """Generate dynamic anomaly bounding boxes from forensic evidence.

    Returns a list of {x, y, w, h, label, source} dicts with coordinates
    normalized to [0, 100] range for frontend overlay rendering.
    """
    h, w = image_shape[:2]
    regions: list[dict[str, Any]] = []

    # ELA-based anomalies: find bright (high-difference) regions
    if ela_img is not None and ela_img.size > 0:
        gray_ela = np.mean(ela_img, axis=2) if ela_img.ndim == 3 else ela_img
        threshold = float(np.percentile(gray_ela, 95))
        bright_mask = gray_ela > threshold
        if bright_mask.any():
            ys, xs = np.where(bright_mask)
            x_min, x_max = int(xs.min()), int(xs.max())
            y_min, y_max = int(ys.min()), int(ys.max())
            # Normalize to [0, 100] range
            regions.append({
                "x": round(x_min / w * 100, 1),
                "y": round(y_min / h * 100, 1),
                "w": round((x_max - x_min) / w * 100, 1),
                "h": round((y_max - y_min) / h * 100, 1),
                "label": "ELA Anomaly",
                "source": "ela",
                "intensity": float(round(float(gray_ela[bright_mask].mean()), 4)),
            })

    # Wavelet HH-based anomalies: high-frequency noise regions
    if wavelet_hh is not None and wavelet_hh.size > 0:
        hh = np.abs(wavelet_hh)
        threshold = float(np.percentile(hh, 95))
        hh_mask = hh > threshold
        if hh_mask.any():
            ys, xs = np.where(hh_mask)
            x_min, x_max = int(xs.min()), int(xs.max())
            y_min, y_max = int(ys.min()), int(ys.max())
            regions.append({
                "x": round(x_min / w * 100, 1),
                "y": round(y_min / h * 100, 1),
                "w": round((x_max - x_min) / w * 100, 1),
                "h": round((y_max - y_min) / h * 100, 1),
                "label": "High-Frequency Noise",
                "source": "wavelet_hh",
                "intensity": float(round(float(hh[hh_mask].mean()), 4)),
            })

    # Edge-based anomalies: unnaturally sharp regions
    if edge_canny is not None and edge_canny.size > 0:
        edge_density = cv2.blur(edge_canny.astype(np.float32), (15, 15))
        threshold = float(np.percentile(edge_density, 97))
        edge_mask = edge_density > threshold
        if edge_mask.any():
            ys, xs = np.where(edge_mask)
            x_min, x_max = int(xs.min()), int(xs.max())
            y_min, y_max = int(ys.min()), int(ys.max())
            regions.append({
                "x": round(x_min / w * 100, 1),
                "y": round(y_min / h * 100, 1),
                "w": round((x_max - x_min) / w * 100, 1),
                "h": round((y_max - y_min) / h * 100, 1),
                "label": "Abnormal Edge Density",
                "source": "edges",
                "intensity": float(round(float(edge_density[edge_mask].mean()), 4)),
            })

    # FFT-based anomalies: frequency domain irregularities
    if fft_img is not None and fft_img.size > 0:
        fft_norm = fft_img.astype(np.float32) / 255.0
        threshold = float(np.percentile(fft_norm, 98))
        fft_mask = fft_norm > threshold
        if fft_mask.any():
            ys, xs = np.where(fft_mask)
            x_min, x_max = int(xs.min()), int(xs.max())
            y_min, y_max = int(ys.min()), int(ys.max())
            regions.append({
                "x": round(x_min / w * 100, 1),
                "y": round(y_min / h * 100, 1),
                "w": round((x_max - x_min) / w * 100, 1),
                "h": round((y_max - y_min) / h * 100, 1),
                "label": "Frequency Anomaly",
                "source": "fft",
                "intensity": float(round(float(fft_norm[fft_mask].mean()), 4)),
            })

    return regions


# ── Main Pipeline ────────────────────────────────────────────────────

def run_image_pipeline(file_path: str) -> dict[str, Any]:
    image = cv2.imread(file_path)
    if image is None:
        return {"status": "error", "error": "Could not read image"}
    image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    original = image.copy()

    result: dict[str, Any] = {"status": "ok"}

    # Resize
    resized = resize_image(image, target_size=384)
    result["original_size"] = f"{original.shape[1]}x{original.shape[0]}"
    result["resized_size"] = f"{resized.shape[1]}x{resized.shape[0]}"

    # Normalize
    normalized = normalize_image(resized)

    # RGB ensure
    rgb = ensure_rgb(resized)

    # Face crop
    face_crop = crop_largest_face(rgb)
    result["face_cropped"] = face_crop is not None
    result["face_crop_size"] = f"{face_crop.shape[1]}x{face_crop.shape[0]}" if face_crop is not None else None

    # CLAHE
    enhanced = apply_clahe(rgb)

    # Denoise (uses settings.denoise_strength)
    denoised = denoise_image(enhanced)

    # ELA (uses settings.ela_quality)
    ela = generate_ela(rgb)
    ela_score = float(ela.mean())
    result["ela_score"] = round(ela_score, 4)

    # FFT
    fft = generate_fft(rgb)
    fft_score = float(fft.mean())
    result["fft_mean"] = round(fft_score, 4)

    # DCT
    dct = generate_dct(rgb)
    dct_score = float(dct.mean())
    result["dct_mean"] = round(dct_score, 4)

    # Wavelet
    wavelet = generate_wavelet(rgb)
    result["wavelet"] = {k: float(v.mean()) for k, v in wavelet.items()}

    # Edge maps
    edges = generate_edge_maps(rgb)
    result["edge_intensity"] = {
        k: float(v.mean()) for k, v in edges.items()
    }

    # Metadata
    result["metadata"] = extract_image_metadata(file_path)

    # Hashes
    result["hashes"] = compute_hashes(file_path)

    # Diagnostic images (base64-encoded visualizations)
    wavelet_hh = wavelet.get("HH")
    result["diagnostic_images"] = _generate_diagnostic_images(
        rgb=rgb,
        file_path=file_path,
        ela_img=ela,
        fft_img=fft,
        dct_img=dct,
        wavelet_hh=wavelet_hh,
        edge_canny=edges.get("canny"),
        edge_sobel=edges.get("sobel"),
        edge_laplacian=edges.get("laplacian"),
    )

    # Anomaly regions (dynamic, evidence-based bounding boxes)
    result["anomaly_regions"] = _generate_anomaly_regions(
        ela_img=ela,
        fft_img=fft,
        noise_map=None,
        wavelet_hh=wavelet_hh,
        edge_canny=edges.get("canny"),
        image_shape=(rgb.shape[0], rgb.shape[1]),
    )

    return result
