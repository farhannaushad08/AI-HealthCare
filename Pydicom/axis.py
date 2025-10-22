import pydicom as dicom
import numpy as np
import matplotlib.pyplot as plt
import os

def convert_to_hu(ds):
    """Convert pixel_array to Hounsfield Units using RescaleSlope and RescaleIntercept."""
    try:
        image = ds.pixel_array.astype(np.int16)
        intercept = getattr(ds, 'RescaleIntercept', 0)
        slope = getattr(ds, 'RescaleSlope', 1)
        hu_image = image * slope + intercept
        return hu_image
    except Exception as e:
        print(f"[axis] HU conversion failed for {getattr(ds, 'SOPInstanceUID', '?')}: {e}")
        return ds.pixel_array.astype(np.int16)

def normalize_for_display(array, min_v=None, max_v=None):
    """Normalize HU range to 0-255 grayscale for visualization."""
    array = np.nan_to_num(array)
    if min_v is None:
        min_v = np.min(array)
    if max_v is None:
        max_v = np.max(array)
    diff = max_v - min_v
    if diff == 0:
        return np.uint8(np.full_like(array, 128))
    array = np.clip(array, min_v, max_v)
    norm = (array - min_v) / diff
    return np.uint8(norm * 255)

def show_axis_views(path):
    """Display Axial, Sagittal, and Coronal views for a DICOM series."""
    if not os.path.exists(path):
        print(f"[axis] Path does not exist: {path}")
        return

    ct_images = [f for f in os.listdir(path) if f.lower().endswith('.dcm')]
    if not ct_images:
        print(f"[axis] No DICOM files found in {path}")
        return

    print(f"[axis] Found {len(ct_images)} DICOM slices in {path}")

    # Load all slices safely
    slices = []
    for f in ct_images:
        try:
            ds = dicom.dcmread(os.path.join(path, f), force=True)
            slices.append(ds)
        except Exception as e:
            print(f"[axis] Failed to read {f}: {e}")

    if len(slices) == 0:
        print("[axis] No readable DICOM slices.")
        return

    # Sort slices by z-position
    try:
        slices = sorted(slices, key=lambda x: getattr(x, 'ImagePositionPatient', [0, 0, 0])[2])
    except Exception:
        slices.sort(key=lambda x: getattr(x, 'InstanceNumber', 0))

    pixel_spacing = getattr(slices[0], 'PixelSpacing', [1.0, 1.0])
    slice_thickness = getattr(slices[0], 'SliceThickness', 1.0)

    # Compute aspect ratios
    axial_aspect_ratio = pixel_spacing[1] / pixel_spacing[0]
    sagittal_aspect_ratio = pixel_spacing[1] / slice_thickness
    coronal_aspect_ratio = slice_thickness / pixel_spacing[0]

    # Build 3D volume (in HU)
    img_shape = list(slices[0].pixel_array.shape)
    img_shape.append(len(slices))
    volume3d = np.zeros(img_shape, dtype=np.int16)

    for i, s in enumerate(slices):
        volume3d[:, :, i] = convert_to_hu(s)

    # Normalize volume for display
    vmin = np.percentile(volume3d, 1)
    vmax = np.percentile(volume3d, 99)
    display_vol = normalize_for_display(volume3d, vmin, vmax)

    # Plot 3 anatomical views
    fig = plt.figure(figsize=(10, 10))

    # Axial (Z slice)
    axial = plt.subplot(2, 2, 1)
    plt.title("Axial")
    plt.imshow(display_vol[:, :, display_vol.shape[2] // 2], cmap='gray')
    axial.set_aspect(axial_aspect_ratio)

    # Sagittal (X slice)
    sagittal = plt.subplot(2, 2, 2)
    plt.title("Sagittal")
    plt.imshow(display_vol[:, display_vol.shape[1] // 2, :], cmap='gray')
    sagittal.set_aspect(sagittal_aspect_ratio)

    # Coronal (Y slice)
    coronal = plt.subplot(2, 2, 3)
    plt.title("Coronal")
    plt.imshow(display_vol[display_vol.shape[0] // 2, :, :].T, cmap='gray')
    coronal.set_aspect(coronal_aspect_ratio)

    plt.tight_layout()
    plt.show()
