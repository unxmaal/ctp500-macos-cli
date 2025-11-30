#!/opt/homebrew/bin/python3.11
"""
CUPS Backend for CTP500 Thermal Receipt Printer (BLE)

This backend interfaces between CUPS and the CTP500 printer via Bluetooth LE.
It handles file format detection, conversion, and BLE communication.

CUPS calls this backend with:
  backend job-id user title copies options [file]

Device URI format:
  ctp500://BLE-ADDRESS
  Example: ctp500://D210000E-A47D-2971-6819-A5F4189E7B86

Exit codes (CUPS standard):
  0 = Success
  1 = Failed (CUPS will retry)
  2 = Failed (CUPS will stop queue)
  3 = Failed (CUPS will cancel job)
  4 = Failed (CUPS will hold job)
"""

import sys
import os
import re
import tempfile
import subprocess
import asyncio
from pathlib import Path

# Add Homebrew's virtualenv site-packages to path
HOMEBREW_PREFIX = os.getenv("HOMEBREW_PREFIX", "/opt/homebrew")
sys.path.insert(0, f"{HOMEBREW_PREFIX}/opt/ctp500-printer/lib/python3.11/site-packages")

try:
    from bleak import BleakClient
    from PIL import Image, ImageDraw, ImageFont, ImageChops, ImageOps
except ImportError as e:
    print(f"ERROR: Failed to import required module: {e}", file=sys.stderr)
    print(f"ERROR: sys.path = {sys.path}", file=sys.stderr)
    sys.exit(2)

# Configuration
HOMEBREW_PREFIX = os.getenv("HOMEBREW_PREFIX", "/opt/homebrew")
CONFIG_FILE = os.getenv("CONFIG_FILE", f"{HOMEBREW_PREFIX}/etc/ctp500/ctp500.conf")

# Printer constants
PRINTER_WIDTH = 384
TRIM_BOTTOM_MARGIN_PX = 10
TEXT_CANVAS_HEIGHT_PX = 5000
THRESHOLD_VALUE = 128
DEFAULT_CHUNK_SIZE = 180
DEFAULT_WRITE_DELAY_SEC = 0.02
INIT_DELAY_SEC = 0.1

# Defaults
DEFAULT_WRITE_UUID = "49535343-8841-43f4-a8d4-ecbe34729bb3"
DEFAULT_FONT_SIZE = 28

# ESC/POS command sequences
INIT_SEQUENCE = b"\x1b\x40"  # ESC @
START_PRINT_SEQUENCE = b"\x1d\x49\xf0\x19"
END_PRINT_SEQUENCE = b"\x0a\x0a\x0a\x9a"

def log_info(msg):
    """Log info message to stderr (CUPS reads stderr for logging)"""
    print(f"INFO: {msg}", file=sys.stderr)

def log_error(msg):
    """Log error message to stderr"""
    print(f"ERROR: {msg}", file=sys.stderr)

def validate_uri(uri):
    """Validate CUPS device URI format"""
    if not uri:
        return False
    return uri.startswith("ctp500://")

def extract_ble_address(uri):
    """Extract BLE address from device URI"""
    if not uri:
        return None
    # Strip ctp500:// prefix and query parameters
    addr = uri.replace("ctp500://", "").split("?")[0]
    return addr if addr else None

def validate_ble_address(addr):
    """Validate BLE address format (MAC or UUID)"""
    if not addr:
        return False
    # MAC format: AA:BB:CC:DD:EE:FF
    mac_pattern = r'^[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}$'
    # UUID format: XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX
    uuid_pattern = r'^[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}$'
    return bool(re.match(mac_pattern, addr) or re.match(uuid_pattern, addr))

def read_config():
    """Read configuration from file"""
    config = {
        'write_uuid': DEFAULT_WRITE_UUID,
        'chunk_size': DEFAULT_CHUNK_SIZE
    }

    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                for line in f:
                    line = line.strip()
                    if '=' in line and not line.startswith('#'):
                        key, value = line.split('=', 1)
                        key = key.strip().lower()
                        value = value.strip().strip('"').strip("'")
                        if key == 'write_uuid':
                            config['write_uuid'] = value
                        elif key == 'chunk_size':
                            config['chunk_size'] = int(value)
        except Exception as e:
            log_error(f"Failed to read config file: {e}")

    return config

def detect_format(filepath):
    """Detect file format using file command"""
    try:
        result = subprocess.run(
            ['file', '-b', '--mime-type', filepath],
            capture_output=True,
            text=True,
            check=True
        )
        mime = result.stdout.strip()

        if mime == 'application/postscript':
            return 'postscript'
        elif mime == 'application/pdf':
            return 'pdf'
        elif mime.startswith('image/'):
            return 'image'
        elif mime == 'text/plain':
            return 'text'
        else:
            return 'unknown'
    except Exception as e:
        log_error(f"Format detection failed: {e}")
        return 'unknown'

# Image processing functions (from ctp500_ble_cli.py)

def trim_image(im):
    """Trim vertical whitespace from an image"""
    if im.mode in ("L", "LA"):
        bg = Image.new(im.mode, im.size, 255)
    else:
        bg = Image.new(im.mode, im.size, (255, 255, 255))

    diff = ImageChops.difference(im, bg)
    diff = ImageChops.add(diff, diff, 2.0)
    bbox = diff.getbbox()
    if bbox:
        bottom = min(bbox[3] + TRIM_BOTTOM_MARGIN_PX, im.height)
        return im.crop((bbox[0], bbox[1], bbox[2], bottom))
    return im

def text_to_image(text, font_size=DEFAULT_FONT_SIZE):
    """Convert text to image"""
    try:
        font = ImageFont.truetype("Lucon.ttf", font_size)
    except:
        font = ImageFont.load_default()

    img = Image.new("L", (PRINTER_WIDTH, TEXT_CANVAS_HEIGHT_PX), 255)
    draw = ImageDraw.Draw(img)

    y = 0
    for line in text.split('\n'):
        draw.text((0, y), line, font=font, fill=0)
        y += font_size + 5

    return trim_image(img)

def image_to_bitmap(img, black_is_one=True):
    """Convert image to 1-bit bitmap for printer"""
    # Resize to printer width if needed
    if img.width != PRINTER_WIDTH:
        aspect = img.height / img.width
        new_height = int(PRINTER_WIDTH * aspect)
        img = img.resize((PRINTER_WIDTH, new_height), Image.Resampling.LANCZOS)

    # Convert to grayscale and then to 1-bit
    if img.mode != 'L':
        img = img.convert('L')

    # Threshold
    img = img.point(lambda x: 255 if x > THRESHOLD_VALUE else 0, mode='1')

    # Invert if needed
    if not black_is_one:
        img = ImageOps.invert(img.convert('L')).convert('1')

    return img

def image_to_raster_bytes(img, black_is_one=True):
    """Convert image to ESC/POS raster format with command header"""
    # Ensure image is 1-bit
    if img.mode != '1':
        img = image_to_bitmap(img, black_is_one=False)  # Don't invert yet

    width = img.width
    height = img.height

    if width % 8 != 0:
        # Pad width to multiple of 8
        new_width = ((width + 7) // 8) * 8
        padded = Image.new('1', (new_width, height), 1)  # 1 = white
        padded.paste(img, (0, 0))
        img = padded
        width = new_width

    width_bytes = width // 8

    # ESC/POS raster header: GS v 0 mode xL xH yL yH
    header = bytearray(b"\x1d\x76\x30\x00")
    header += bytes([width_bytes & 0xFF, (width_bytes >> 8) & 0xFF])
    header += bytes([height & 0xFF, (height >> 8) & 0xFF])

    # Get bitmap data
    data = bytearray(img.tobytes())

    # Invert bits if black_is_one (Pillow uses 0=black, 1=white)
    if black_is_one:
        for i in range(len(data)):
            data[i] ^= 0xFF

    return bytes(header) + bytes(data)

async def print_to_ble(ble_address, write_uuid, raster_data, chunk_size=DEFAULT_CHUNK_SIZE):
    """Send raster data to printer via BLE with proper ESC/POS sequences"""
    try:
        async with BleakClient(ble_address) as client:
            log_info(f"Connected to {ble_address}")

            # Send initialization sequence
            await client.write_gatt_char(write_uuid, INIT_SEQUENCE, response=False)
            await asyncio.sleep(INIT_DELAY_SEC)

            # Send start print sequence
            await client.write_gatt_char(write_uuid, START_PRINT_SEQUENCE, response=False)
            await asyncio.sleep(INIT_DELAY_SEC)

            # Send raster data in chunks
            total_chunks = (len(raster_data) + chunk_size - 1) // chunk_size
            for i in range(0, len(raster_data), chunk_size):
                chunk = raster_data[i:i+chunk_size]
                await client.write_gatt_char(write_uuid, chunk, response=False)
                await asyncio.sleep(DEFAULT_WRITE_DELAY_SEC)

                chunk_num = i // chunk_size + 1
                if chunk_num % 10 == 0:
                    log_info(f"Sent chunk {chunk_num}/{total_chunks}")

            # Send end print sequence (feeds paper!)
            await client.write_gatt_char(write_uuid, END_PRINT_SEQUENCE, response=False)
            await asyncio.sleep(INIT_DELAY_SEC)

            log_info("Print job completed successfully")
            return True
    except Exception as e:
        log_error(f"BLE communication failed: {e}")
        return False

def print_text(ble_address, write_uuid, text_file, chunk_size):
    """Print text file"""
    try:
        with open(text_file, 'r') as f:
            text = f.read()

        log_info("Converting text to image...")
        img = text_to_image(text)

        log_info("Converting image to raster format...")
        raster = image_to_raster_bytes(img, black_is_one=True)

        log_info(f"Printing to {ble_address}...")
        return asyncio.run(print_to_ble(ble_address, write_uuid, raster, chunk_size))
    except Exception as e:
        log_error(f"Text printing failed: {e}")
        return False

def print_image(ble_address, write_uuid, image_file, chunk_size):
    """Print image file"""
    try:
        log_info(f"Loading image: {image_file}")
        img = Image.open(image_file)

        log_info("Converting image to raster format...")
        raster = image_to_raster_bytes(img, black_is_one=True)

        log_info(f"Printing to {ble_address}...")
        return asyncio.run(print_to_ble(ble_address, write_uuid, raster, chunk_size))
    except Exception as e:
        log_error(f"Image printing failed: {e}")
        return False

def convert_with_sips(input_file, output_file):
    """Convert PostScript/PDF to PNG using macOS sips"""
    try:
        subprocess.run(
            ['sips', '-s', 'format', 'png', input_file, '--out', output_file],
            capture_output=True,
            check=True
        )
        return True
    except subprocess.CalledProcessError:
        return False

def main():
    """Main CUPS backend entry point"""
    # Discovery mode (no arguments)
    if len(sys.argv) == 1:
        print('direct ctp500 "CTP500 Thermal Printer" "CTP500 BLE Thermal Receipt Printer"')
        return 0

    # Job mode (6 or 7 arguments)
    if len(sys.argv) not in (6, 7):
        log_error(f"Usage: {sys.argv[0]} job-id user title copies options [file]")
        return 1

    job_id = sys.argv[1]
    user = sys.argv[2]
    title = sys.argv[3]
    copies = sys.argv[4]
    options = sys.argv[5]
    input_file = sys.argv[6] if len(sys.argv) == 7 else None

    log_info(f"Job {job_id}: User={user}, Title={title}, Copies={copies}")

    # Get device URI from environment
    device_uri = os.getenv('DEVICE_URI')
    if not device_uri:
        log_error("DEVICE_URI environment variable not set")
        return 2

    if not validate_uri(device_uri):
        log_error(f"Invalid device URI: {device_uri}")
        log_error("Expected format: ctp500://BLE-ADDRESS")
        return 2

    # Extract and validate BLE address
    ble_address = extract_ble_address(device_uri)
    if not ble_address or not validate_ble_address(ble_address):
        log_error(f"Invalid BLE address: {ble_address}")
        return 2

    log_info(f"BLE Address: {ble_address}")

    # Load configuration
    config = read_config()
    write_uuid = config['write_uuid']
    chunk_size = config['chunk_size']

    log_info(f"Write UUID: {write_uuid}")
    log_info(f"Chunk Size: {chunk_size}")

    # Handle input source
    cleanup_temp = False
    if not input_file or input_file == '-':
        # Read from stdin
        temp_fd, input_file = tempfile.mkstemp(prefix='ctp500-job-')
        os.close(temp_fd)
        with open(input_file, 'wb') as f:
            f.write(sys.stdin.buffer.read())
        cleanup_temp = True
        log_info(f"Reading from stdin to temp file: {input_file}")
    else:
        log_info(f"Input file: {input_file}")

    try:
        # Detect file format
        file_format = detect_format(input_file)
        log_info(f"Detected format: {file_format}")

        # Process based on format
        success = False

        if file_format == 'text':
            success = print_text(ble_address, write_uuid, input_file, chunk_size)

        elif file_format == 'image':
            success = print_image(ble_address, write_uuid, input_file, chunk_size)

        elif file_format in ('postscript', 'pdf'):
            # Convert to PNG
            temp_fd, temp_png = tempfile.mkstemp(suffix='.png', prefix='ctp500-image-')
            os.close(temp_fd)

            log_info(f"Converting {file_format} to PNG...")
            if convert_with_sips(input_file, temp_png):
                log_info("Conversion successful")
                success = print_image(ble_address, write_uuid, temp_png, chunk_size)
                os.unlink(temp_png)
            else:
                log_error(f"Failed to convert {file_format} to image")
                os.unlink(temp_png)
                return 3

        else:
            log_error(f"Unsupported file format: {file_format}")
            return 3

        return 0 if success else 1

    finally:
        if cleanup_temp and os.path.exists(input_file):
            os.unlink(input_file)

if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        log_error("Interrupted by user")
        sys.exit(1)
    except Exception as e:
        log_error(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(2)
