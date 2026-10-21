# /// script
# requires-python = ">=3.13"
# dependencies = ["pillow==13.0.0"]
# ///
"""Compress PNG and JPEG images and strip their metadata.

The default step for images under ``docs/`` and ``examples/``. It runs from
pre-commit on staged images, and by hand::

    uv run python tools/compress_images.py docs examples
    uv run python tools/compress_images.py --check docs examples

(Pillow is a dev dependency of the project and pinned by ``uv.lock``. Outside
a project, ``uv run tools/compress_images.py`` reads the dependency from the
header above instead.)

What it does to each image:

* strips all metadata: EXIF, GPS, XMP, text chunks, comments, DPI, thumbnails;
* applies the EXIF orientation first, so the picture stays upright;
* converts a non-sRGB colour profile (macOS screenshots are Display P3) to
    sRGB before dropping it, so colours do not shift;
* PNG: lossless re-encode, and a lossy 256-colour palette version when it
    stays close to the original (PSNR of ``MIN_PSNR_DB`` or better); keeps the
    smaller;
* animated PNG: every frame is re-encoded losslessly and the animation
    (frame timing, loop count) is kept; there is no palette step;
* JPEG: re-encode at quality ``JPEG_QUALITY``, optimised and progressive.

A file is rewritten only when it carried metadata or the result is at least
``MIN_SAVING`` smaller, so running the tool again changes nothing. Any file that
cannot be read is left untouched. ``--check`` writes nothing and exits with 1
when a file would change.
"""

import argparse
import io
import math
import sys
from collections.abc import Iterator, Sequence
from pathlib import Path

from PIL import (
    Image,
    ImageChops,
    ImageCms,
    ImageOps,
    ImageStat,
    features,
)

MAX_COLORS = 256
MIN_PSNR_DB = 40.0
PEAK = 255.0
JPEG_QUALITY = 85
MIN_SAVING = 0.05
SUFFIXES = {".png", ".jpg", ".jpeg"}
JPEG_METADATA_KEYS = {
    "exif",
    "icc_profile",
    "comment",
    "xmp",
    "photoshop",
    "dpi",
}
RGB_MODES = {"RGB", "RGBA"}
ANIMATION_KEYS = {
    "duration",
    "loop",
    "default_image",
    "disposal",
    "blend",
    "bbox",
}


def _iter_images(paths: Sequence[Path]) -> Iterator[Path]:
    """Yield every PNG and JPEG file in ``paths``, recursing into folders.

    Parameters
    ----------
    paths
        Files and folders given on the command line.

    Yields
    ------
    Path
        An image file, in sorted order within each folder.
    """
    for path in paths:
        found = sorted(path.rglob("*")) if path.is_dir() else [path]
        for candidate in found:
            if candidate.is_file() and candidate.suffix.lower() in SUFFIXES:
                yield candidate


def _has_metadata(image: Image.Image) -> bool:
    """Tell whether ``image`` carries metadata that should be stripped.

    Parameters
    ----------
    image
        An opened image.

    Returns
    -------
    bool
        True for any PNG chunk beyond transparency, and for JPEG EXIF, colour
        profile, comment, XMP, Photoshop or DPI data.
    """
    if len(image.getexif()) > 0:
        return True
    keys = set(image.info) - {"transparency"} - ANIMATION_KEYS
    if image.format == "JPEG":
        return bool(keys & JPEG_METADATA_KEYS)
    return bool(keys)


def _to_srgb(image: Image.Image) -> Image.Image:
    """Convert ``image`` to sRGB when it carries another colour profile.

    Parameters
    ----------
    image
        An opened image with its metadata still attached.

    Returns
    -------
    Image.Image
        The same pixels in sRGB, or ``image`` itself when it has no profile,
        is already sRGB, or is not an RGB image.
    """
    profile = image.info.get("icc_profile")
    if not isinstance(profile, bytes):
        return image
    if image.mode == "P":
        image = image.convert("RGBA")
    if image.mode not in RGB_MODES:
        return image
    source = ImageCms.ImageCmsProfile(io.BytesIO(profile))
    if "srgb" in ImageCms.getProfileDescription(source).lower():
        return image
    converted = ImageCms.profileToProfile(
        image,
        source,
        ImageCms.createProfile("sRGB"),
        outputMode=image.mode,
    )
    return image if converted is None else converted


def _clean(image: Image.Image) -> Image.Image:
    """Return the pixels of ``image`` upright, in sRGB, with no metadata.

    Parameters
    ----------
    image
        An opened image.

    Returns
    -------
    Image.Image
        A copy whose ``info`` dictionary is empty.
    """
    result = _to_srgb(ImageOps.exif_transpose(image))
    if "transparency" in result.info:
        result = result.convert("RGBA")
    pixels = result.copy()
    pixels.info.clear()
    return pixels


def _psnr(first: Image.Image, second: Image.Image) -> float:
    """Measure how close two images of the same mode are.

    Parameters
    ----------
    first
        The reference image.
    second
        The image to compare.

    Returns
    -------
    float
        Peak signal-to-noise ratio in dB; ``inf`` for identical images.
    """
    sums = ImageStat.Stat(ImageChops.difference(first, second)).sum2
    mse = sum(sums) / (len(sums) * first.width * first.height)
    return math.inf if mse == 0 else 10 * math.log10(PEAK**2 / mse)


def _quantize(image: Image.Image) -> Image.Image | None:
    """Reduce ``image`` to a palette of at most 256 colours, if that is safe.

    Parameters
    ----------
    image
        A clean image.

    Returns
    -------
    Image.Image | None
        The palette image, or None when the image is not RGB or RGBA, is
        already a palette image, or the palette version differs too much.
    """
    if image.mode not in RGB_MODES:
        return None
    if features.check("libimagequant"):
        method = Image.Quantize.LIBIMAGEQUANT
    elif image.mode == "RGBA":
        method = Image.Quantize.FASTOCTREE
    else:
        method = Image.Quantize.MEDIANCUT
    palette = image.quantize(colors=MAX_COLORS, method=method)
    if _psnr(image, palette.convert(image.mode)) < MIN_PSNR_DB:
        return None
    return palette


def _encode_png(image: Image.Image) -> bytes:
    """Encode ``image`` as an optimised PNG.

    Parameters
    ----------
    image
        The image to encode.

    Returns
    -------
    bytes
        The PNG file contents.
    """
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def _as_int(value: object) -> int:
    """Read a number from an image ``info`` entry.

    Parameters
    ----------
    value
        An entry of ``Image.info``.

    Returns
    -------
    int
        The value as an integer, or 0 when it is not a number.
    """
    return int(value) if isinstance(value, int | float) else 0


def _frame_count(image: Image.Image) -> int:
    """Count the frames of ``image``.

    Parameters
    ----------
    image
        An opened image.

    Returns
    -------
    int
        The number of frames; 1 for a still image.
    """
    return _as_int(getattr(image, "n_frames", 1))


def _animated_png_bytes(image: Image.Image) -> bytes:
    """Return an animated PNG with every frame of ``image``, without metadata.

    Frames are composed to full canvas size by Pillow, so each one is stored as
    a plain RGBA frame. Frame timing, the loop count and the default-image flag
    are kept. Pillow merges consecutive identical frames and adds their
    durations, so the picture and its timing stay the same.

    Parameters
    ----------
    image
        An opened animated PNG.

    Returns
    -------
    bytes
        The new PNG file contents.
    """
    loop = _as_int(image.info.get("loop", 0))
    default_image = bool(image.info.get("default_image", False))
    frames: list[Image.Image] = []
    durations: list[int] = []
    for index in range(_frame_count(image)):
        image.seek(index)
        durations.append(_as_int(image.info.get("duration", 0)))
        frames.append(_clean(image).convert("RGBA"))
    buffer = io.BytesIO()
    frames[0].save(
        buffer,
        format="PNG",
        save_all=True,
        append_images=frames[1:],
        duration=durations,
        loop=loop,
        default_image=default_image,
        optimize=True,
    )
    return buffer.getvalue()


def _png_bytes(image: Image.Image) -> bytes:
    """Return the smallest PNG for ``image`` without metadata.

    Parameters
    ----------
    image
        An opened PNG.

    Returns
    -------
    bytes
        For an animated PNG, every frame re-encoded losslessly. Otherwise
        whichever is smaller: the lossless or the palette encoding.
    """
    if _frame_count(image) > 1:
        return _animated_png_bytes(image)
    clean = _clean(image)
    candidates = [_encode_png(clean)]
    if clean.mode != "P":
        palette = _quantize(clean)
        if palette is not None:
            candidates.append(_encode_png(palette))
    return min(candidates, key=len)


def _jpeg_bytes(image: Image.Image) -> bytes:
    """Return ``image`` as an optimised JPEG without metadata.

    Parameters
    ----------
    image
        An opened JPEG.

    Returns
    -------
    bytes
        The JPEG file contents.
    """
    clean = _clean(image)
    if clean.mode not in {"RGB", "L"}:
        clean = clean.convert("RGB")
    buffer = io.BytesIO()
    clean.save(
        buffer,
        format="JPEG",
        quality=JPEG_QUALITY,
        optimize=True,
        progressive=True,
    )
    return buffer.getvalue()


def _recompress(original: bytes) -> bytes | None:
    """Encode the image in ``original`` again, smaller and without metadata.

    Parameters
    ----------
    original
        The contents of a PNG or JPEG file.

    Returns
    -------
    bytes | None
        The new file contents, or None for any other format.
    """
    with Image.open(io.BytesIO(original)) as image:
        image.load()
        if image.format == "PNG":
            return _png_bytes(image)
        if image.format == "JPEG":
            return _jpeg_bytes(image)
    return None


def _carries_metadata(original: bytes) -> bool:
    """Tell whether the image in ``original`` has metadata to strip.

    Parameters
    ----------
    original
        The contents of a PNG or JPEG file.

    Returns
    -------
    bool
        True when there is metadata.
    """
    with Image.open(io.BytesIO(original)) as image:
        return _has_metadata(image)


def compress_file(path: Path, *, write: bool = True) -> int | None:
    """Compress one image and strip its metadata.

    Parameters
    ----------
    path
        A PNG or JPEG file.
    write
        When False, only report what would change.

    Returns
    -------
    int | None
        None when the file is left as it is; otherwise the bytes saved, which
        is zero or negative when only the metadata was removed.
    """
    original = path.read_bytes()
    try:
        candidate = _recompress(original)
        dirty = _carries_metadata(original)
    except (OSError, ValueError, ImageCms.PyCMSError) as error:
        sys.stderr.write(f"skipped {path}: {error}\n")
        return None
    if candidate is None:
        return None
    saving = len(original) - len(candidate)
    if not dirty and saving < len(original) * MIN_SAVING:
        return None
    if write:
        path.write_bytes(candidate)
    return saving


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command line tool.

    Parameters
    ----------
    argv
        Arguments; ``sys.argv[1:]`` when None.

    Returns
    -------
    int
        0 normally; with ``--check``, 1 when any file would change.
    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    check: bool = args.check
    paths: list[Path] = args.paths
    changed = 0
    saved = 0
    for path in _iter_images(paths):
        result = compress_file(path, write=not check)
        if result is None:
            continue
        changed += 1
        saved += result
        verb = "would change" if check else "compressed"
        sys.stdout.write(f"{verb} {path} ({result:+,} bytes saved)\n")
    if changed:
        sys.stdout.write(f"{changed} file(s), {saved:,} bytes saved\n")
    return 1 if check and changed else 0


if __name__ == "__main__":
    raise SystemExit(main())
