#!/usr/bin/env python3
"""
CTP500 BLE Thermal Printer CLI (macOS / cross-platform)
-------------------------------------------------------

This is a refactor of Mel's CTP500 GUI logic into a BLE + CLI tool.

It uses:
  - bleak  (Bluetooth LE / GATT)
  - Pillow (text/image -> bitmap for printer)

Usage examples:

  # 1) Find your printer
  python3 ctp500_ble_cli.py scan

  # 2) Inspect services/characteristics for a given address
  python3 ctp500_ble_cli.py inspect --address <BLE_ADDRESS>

  # 3) Print text from a file
  CTP500_WRITE_UUID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx \
    python3 ctp500_ble_cli.py text --address <BLE_ADDRESS> --file note.txt

  # 4) Print an image
  CTP500_WRITE_UUID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx \
    python3 ctp500_ble_cli.py image --address <BLE_ADDRESS> --file picture.png

NOTE: You *must* set the write characteristic UUID correctly, either via:
  - environment variable: CTP500_WRITE_UUID
  - or the --write-uuid CLI flag

"""

import argparse
import asyncio
import os
import sys

from bleak import BleakClient, BleakScanner

from PIL import Image, ImageDraw, ImageFont, ImageChops, ImageOps


# ---------------------------------------------------------------------
# Configuration & Constants
# ---------------------------------------------------------------------

PRINTER_WIDTH = int(os.getenv("CTP500_PRINTER_WIDTH", "384"))

# Image processing constants
TRIM_BOTTOM_MARGIN_PX = 10
TEXT_CANVAS_HEIGHT_PX = 5000
THRESHOLD_VALUE = 128

# BLE communication constants
DEFAULT_CHUNK_SIZE = 180
DEFAULT_WRITE_DELAY_SEC = 0.02
INIT_DELAY_SEC = 0.1
STATUS_READ_DELAY_SEC = 0.2

# You *must* set this to the printer's write characteristic UUID.
# Leave empty here; use env var or CLI flag.
DEFAULT_WRITE_UUID = os.getenv("CTP500_WRITE_UUID", "").strip().lower()

# Optional: status characteristic UUID (if you discover one)
DEFAULT_STATUS_UUID = os.getenv("CTP500_STATUS_UUID", "").strip().lower()

# Default font (Lucon.ttf was used in Mel's app; fall back to a system/default font)
DEFAULT_FONT_PATH = os.getenv("CTP500_FONT", "Lucon.ttf")
DEFAULT_FONT_SIZE = int(os.getenv("CTP500_FONT_SIZE", "28"))

CTP500_BLACK_IS_ONE = os.getenv("CTP500_BLACK_IS_ONE", "0").strip()
DEFAULT_BLACK_IS_ONE = CTP500_BLACK_IS_ONE in ("1", "true", "TRUE", "yes", "on")


# ---------------------------------------------------------------------
# Image helpers (adapted from original script)
# ---------------------------------------------------------------------


def trim_image(im: Image.Image) -> Image.Image:
    """Trim vertical whitespace from an image, leaving a little margin."""
    # Create background matching image mode
    if im.mode in ("L", "LA"):
        bg = Image.new(im.mode, im.size, 255)
    else:
        bg = Image.new(im.mode, im.size, (255, 255, 255))

    diff = ImageChops.difference(im, bg)
    diff = ImageChops.add(diff, diff, 2.0)
    bbox = diff.getbbox()
    if bbox:
        # Add margin at bottom so the last line isn't cut off
        bottom = min(bbox[3] + TRIM_BOTTOM_MARGIN_PX, im.height)
        return im.crop((bbox[0], bbox[1], bbox[2], bottom))
    return im


def get_wrapped_text(text: str, font: ImageFont.FreeTypeFont, line_length: int) -> str:
    """Wrap text so that each line fits within `line_length` pixels."""
    lines = []
    for word in text.split():
        if not lines:
            # First word starts first line
            lines.append(word)
        else:
            candidate = f"{lines[-1]} {word}"
            if font.getlength(candidate) <= line_length:
                lines[-1] = candidate
            else:
                lines.append(word)
    return "\n".join(lines)


def create_text_image(
    text: str,
    printer_width: int = PRINTER_WIDTH,
    font_path: str = DEFAULT_FONT_PATH,
    font_size: int = DEFAULT_FONT_SIZE,
) -> Image.Image:
    """Render text into an image sized for the printer."""
    # Big canvas, will trim later
    img = Image.new("RGB", (printer_width, TEXT_CANVAS_HEIGHT_PX), color=(255, 255, 255))

    # Load font (with graceful fallback)
    try:
        font = ImageFont.truetype(font_path, font_size)
    except (OSError, IOError) as e:
        print(
            f"Warning: could not load font '{font_path}': {e}. Falling back to default.",
            file=sys.stderr,
        )
        font = ImageFont.load_default()

    draw = ImageDraw.Draw(img)

    wrapped_lines = []
    for line in text.splitlines():
        wrapped_lines.append(get_wrapped_text(line, font, printer_width))
    wrapped_text = "\n".join(wrapped_lines)

    draw.text((0, 0), wrapped_text, fill=(0, 0, 0), font=font)
    return trim_image(img)


def floyd_steinberg_dither(im: Image.Image) -> Image.Image:
    """
    Apply Floyd-Steinberg dithering to a grayscale image.
    Converts to 1-bit black/white with error diffusion for better quality.
    Returns 1-bit image where 0 = black, 255 = white.
    """
    # Work on a copy as grayscale
    img = im.convert("L")
    width, height = img.size

    # Convert to numpy-like array for faster processing
    pixels = list(img.getdata())

    for y in range(height):
        for x in range(width):
            idx = y * width + x
            old_pixel = pixels[idx]

            # Threshold: < 128 = black (0), >= 128 = white (255)
            new_pixel = 0 if old_pixel < THRESHOLD_VALUE else 255
            pixels[idx] = new_pixel

            # Calculate error
            error = old_pixel - new_pixel

            # Distribute error to neighboring pixels (Floyd-Steinberg pattern)
            if x + 1 < width:  # Right pixel
                pixels[idx + 1] = max(0, min(255, pixels[idx + 1] + error * 7 // 16))

            if y + 1 < height:
                if x > 0:  # Bottom-left pixel
                    pixels[idx + width - 1] = max(0, min(255, pixels[idx + width - 1] + error * 3 // 16))

                # Bottom pixel
                pixels[idx + width] = max(0, min(255, pixels[idx + width] + error * 5 // 16))

                if x + 1 < width:  # Bottom-right pixel
                    pixels[idx + width + 1] = max(0, min(255, pixels[idx + width + 1] + error * 1 // 16))

    # Create new 1-bit image
    result = Image.new("1", (width, height))
    result.putdata(pixels)
    return result


def prepare_image_for_printer(im: Image.Image, printer_width: int = PRINTER_WIDTH) -> Image.Image:
    """
    Resize, pad, and convert an image for the CTP500 printer.
    We produce a 1-bit image where 0 = black, 255 = white.
    Uses Floyd-Steinberg dithering for better image quality.
    We DO NOT invert here; bit polarity is handled later.
    """
    # Convert to grayscale first
    if im.mode not in ("L", "LA", "RGB", "RGBA", "1"):
        im = im.convert("L")

    # Scale down if wider than printer resolution
    if im.width > printer_width:
        height = int(im.height * (printer_width / im.width))
        im = im.resize((printer_width, height), Image.Resampling.LANCZOS)

    # Pad if narrower than printer width
    if im.width < printer_width:
        padded = Image.new("L", (printer_width, im.height), 255)  # white background
        padded.paste(im, (0, 0))
        im = padded

    # Ensure width multiple of 8
    if im.size[0] % 8:
        new_width = im.size[0] + 8 - (im.size[0] % 8)
        padded = Image.new("L", (new_width, im.size[1]), 255)
        padded.paste(im, (0, 0))
        im = padded

    # Apply Floyd-Steinberg dithering for better image quality
    im = floyd_steinberg_dither(im)

    return im



def image_to_raster_bytes(im: Image.Image, black_is_one: bool = False) -> bytes:
    """
    Convert a prepared 1-bit image into the ESC/POS raster command buffer.

    Pillow '1' mode uses bits where 0 = black, 1 = white.
    If the printer expects 1-bits to be black, set black_is_one=True
    and we will invert bits in the byte stream.
    """
    width = im.size[0]
    height = im.size[1]

    if width % 8 != 0:
        raise ValueError("Image width must be multiple of 8 for raster mode.")

    width_bytes = width // 8

    header = bytearray(b"\x1d\x76\x30\x00")
    header += bytes([width_bytes & 0xFF, (width_bytes >> 8) & 0xFF])
    header += bytes([height & 0xFF, (height >> 8) & 0xFF])

    data = bytearray(im.tobytes())

    if black_is_one:
        # Flip all bits so black pixels become 1-bits in the raster stream
        for i in range(len(data)):
            data[i] ^= 0xFF

    return bytes(header) + bytes(data)


# ---------------------------------------------------------------------
# Printer protocol helpers
# ---------------------------------------------------------------------


INIT_SEQUENCE = b"\x1b\x40"          # ESC @
START_PRINT_SEQUENCE = b"\x1d\x49\xf0\x19"
END_PRINT_SEQUENCE = b"\x0a\x0a\x0a\x9a"
STATUS_REQUEST = b"\x1e\x47\x03"     # from original get_printer_status()


async def write_long(
    client: BleakClient,
    char_uuid: str,
    data: bytes,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    delay: float = DEFAULT_WRITE_DELAY_SEC,
):
    """Write a long buffer to a GATT characteristic in chunks."""
    for i in range(0, len(data), chunk_size):
        chunk = data[i : i + chunk_size]
        await client.write_gatt_char(char_uuid, chunk, response=False)
        if delay:
            await asyncio.sleep(delay)


async def send_init_and_start(client: BleakClient, write_uuid: str):
    await client.write_gatt_char(write_uuid, INIT_SEQUENCE, response=False)
    await asyncio.sleep(INIT_DELAY_SEC)
    await client.write_gatt_char(write_uuid, START_PRINT_SEQUENCE, response=False)
    await asyncio.sleep(INIT_DELAY_SEC)


async def send_end(client: BleakClient, write_uuid: str):
    await client.write_gatt_char(write_uuid, END_PRINT_SEQUENCE, response=False)
    await asyncio.sleep(INIT_DELAY_SEC)


async def send_status_request(client: BleakClient, write_uuid: str, status_uuid: str):
    """
    Best-effort status check: send STATUS_REQUEST to write characteristic
    and read back from a separate status characteristic (if provided).
    """
    await client.write_gatt_char(write_uuid, STATUS_REQUEST, response=False)
    await asyncio.sleep(STATUS_READ_DELAY_SEC)
    data = await client.read_gatt_char(status_uuid)
    return data


# ---------------------------------------------------------------------
# BLE helpers
# ---------------------------------------------------------------------


async def scan_devices(args):
    print("Scanning for BLE devices...")
    devices = await BleakScanner.discover(timeout=args.timeout)
    if not devices:
        print("No BLE devices found.")
        return

    for d in devices:
        # bleak versions differ: rssi may be an attribute or live in metadata
        rssi = getattr(d, "rssi", None)
        if rssi is None and hasattr(d, "metadata"):
            rssi = d.metadata.get("rssi")

        print(f"{d.address}  |  name={d.name!r}  |  rssi={rssi}")


async def inspect_device(args):
    address = args.address
    if not address:
        print("You must provide --address for inspect", file=sys.stderr)
        sys.exit(1)

    print(f"Connecting to {address}...")
    async with BleakClient(address) as client:
        print("Connected.")

        # Support both newer and older bleak APIs
        services_obj = None
        get_services = getattr(client, "get_services", None)

        if callable(get_services):
            # Newer style: async method
            services_obj = await get_services()
        else:
            # Older style: services property (likely your case)
            services_obj = getattr(client, "services", None)

        if services_obj is None:
            print("Could not obtain services from BleakClient.", file=sys.stderr)
            return

        # BleakGATTServiceCollection is iterable in all versions
        for service in services_obj:
            print(f"\nService {service.uuid}  ({service.description})")
            # service.characteristics should be iterable
            for char in service.characteristics:
                props = ",".join(char.properties) if hasattr(char, "properties") else ""
                desc = getattr(char, "description", "")
                print(f"  Char  {char.uuid}  [{props}]  ({desc})")



async def connect_client(address: str) -> BleakClient:
    client = BleakClient(address)
    await client.connect()
    return client


def resolve_write_uuid(args) -> str:
    uuid = (args.write_uuid or DEFAULT_WRITE_UUID).strip().lower()
    if not uuid:
        print(
            "ERROR: No write characteristic UUID specified.\n"
            "Set env CTP500_WRITE_UUID or pass --write-uuid.",
            file=sys.stderr,
        )
        sys.exit(1)
    return uuid


# ---------------------------------------------------------------------
# Commands: status / text / image
# ---------------------------------------------------------------------


async def do_status(args):
    address = args.address
    if not address:
        print("You must provide --address for status", file=sys.stderr)
        sys.exit(1)

    write_uuid = resolve_write_uuid(args)
    status_uuid = (args.status_uuid or DEFAULT_STATUS_UUID).strip().lower()

    async with BleakClient(address) as client:
        print(f"Connected to {address}")
        if status_uuid:
            try:
                data = await send_status_request(client, write_uuid, status_uuid)
                print(f"Raw status ({len(data)} bytes): {data.hex()}")
            except (OSError, TimeoutError, ConnectionError) as e:
                print(f"Status request failed: {e}", file=sys.stderr)
        else:
            print("No status UUID configured; just testing basic connect OK.")
        print("Done.")


async def do_text(args):
    address = args.address
    if not address:
        print("You must provide --address for text printing", file=sys.stderr)
        sys.exit(1)

    write_uuid = resolve_write_uuid(args)

    if args.file:
        try:
            with open(args.file, "r", encoding="utf-8") as f:
                text = f.read()
        except (OSError, IOError) as e:
            print(f"Error reading file '{args.file}': {e}", file=sys.stderr)
            sys.exit(1)
    else:
        text = args.message or ""
    text = text.strip()

    if not text:
        print("No text to print. Provide --file or --message.", file=sys.stderr)
        sys.exit(1)

    print("Rendering text to image...")
    img = create_text_image(
        text,
        printer_width=PRINTER_WIDTH,
        font_path=args.font if args.font is not None else DEFAULT_FONT_PATH,
        font_size=args.font_size if args.font_size is not None else DEFAULT_FONT_SIZE,
    )
    img = prepare_image_for_printer(img, PRINTER_WIDTH)

    black_is_one = args.black_is_one if args.black_is_one is not None else DEFAULT_BLACK_IS_ONE
    raster = image_to_raster_bytes(img, black_is_one=black_is_one)

    print(f"Connecting to printer at {address}...")
    async with BleakClient(address) as client:
        print("Connected. Sending job...")
        await send_init_and_start(client, write_uuid)
        await write_long(client, write_uuid, raster, chunk_size=args.chunk_size)
        await send_end(client, write_uuid)
        print("Text print job sent.")


async def do_image(args):
    address = args.address
    if not address:
        print("You must provide --address for image printing", file=sys.stderr)
        sys.exit(1)

    write_uuid = resolve_write_uuid(args)

    if not args.file:
        print("You must provide --file for image printing.", file=sys.stderr)
        sys.exit(1)

    print(f"Loading image from {args.file}...")
    try:
        img = Image.open(args.file)
    except (OSError, IOError) as e:
        print(f"Error loading image '{args.file}': {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Invalid or unsupported image file '{args.file}': {e}", file=sys.stderr)
        sys.exit(1)

    img = prepare_image_for_printer(img, PRINTER_WIDTH)

    black_is_one = args.black_is_one if args.black_is_one is not None else DEFAULT_BLACK_IS_ONE
    raster = image_to_raster_bytes(img, black_is_one=black_is_one)

    print(f"Connecting to printer at {address}...")
    async with BleakClient(address) as client:
        print("Connected. Sending job...")
        await send_init_and_start(client, write_uuid)
        await write_long(client, write_uuid, raster, chunk_size=args.chunk_size)
        await send_end(client, write_uuid)
        print("Image print job sent.")


# ---------------------------------------------------------------------
# CLI setup
# ---------------------------------------------------------------------


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="CTP500 BLE thermal printer CLI")
    sub = p.add_subparsers(dest="command", required=True)

    # scan
    ps = sub.add_parser("scan", help="Scan for nearby BLE devices")
    ps.add_argument("--timeout", type=float, default=5.0, help="Scan duration in seconds")
    ps.set_defaults(func=scan_devices)

    # inspect
    pi = sub.add_parser("inspect", help="Inspect services/characteristics on a device")
    pi.add_argument("--address", required=True, help="BLE device address")
    pi.set_defaults(func=inspect_device)

    # status
    pst = sub.add_parser("status", help="Test connect and (optionally) read status")
    pst.add_argument("--address", required=True, help="BLE device address")
    pst.add_argument("--write-uuid", help="Write characteristic UUID")
    pst.add_argument("--status-uuid", help="Status characteristic UUID")
    pst.set_defaults(func=do_status)

    # text
    pt = sub.add_parser("text", help="Print text as bitmap")
    pt.add_argument("--address", required=True, help="BLE device address")
    pt.add_argument("--write-uuid", help="Write characteristic UUID")
    group = pt.add_mutually_exclusive_group(required=True)
    group.add_argument("--file", help="Text file to print")
    group.add_argument("--message", help="Inline text to print")
    pt.add_argument("--font", help="Path to TTF font (default: Lucon.ttf or env CTP500_FONT)")
    pt.add_argument("--font-size", type=int, help="Font size (default: env CTP500_FONT_SIZE or 28)")
    pt.add_argument(
        "--chunk-size",
        type=int,
        default=180,
        help="BLE write chunk size (bytes, default 180)",
    )
    pt.add_argument(
        "--black-is-one",
        action="store_true",
        help="Treat 1-bits in raster as black (otherwise 0-bits are black). "
             "Can also set env CTP500_BLACK_IS_ONE=1.",
    )
    pt.set_defaults(func=do_text)

    # image
    pi2 = sub.add_parser("image", help="Print an image file")
    pi2.add_argument("--address", required=True, help="BLE device address")
    pi2.add_argument("--write-uuid", help="Write characteristic UUID")
    pi2.add_argument("--file", required=True, help="Image file to print")
    pi2.add_argument(
        "--chunk-size",
        type=int,
        default=180,
        help="BLE write chunk size (bytes, default 180)",
    )
    pi2.add_argument(
        "--black-is-one",
        action="store_true",
        help="Treat 1-bits in raster as black (otherwise 0-bits are black). "
             "Can also set env CTP500_BLACK_IS_ONE=1.",
    )
    pi2.set_defaults(func=do_image)

    return p


async def main_async():
    parser = build_arg_parser()
    args = parser.parse_args()
    await args.func(args)


def main():
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        print("\nInterrupted, exiting.")


if __name__ == "__main__":
    main()
