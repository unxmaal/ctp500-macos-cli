"""Unit tests for image processing functions"""

import pytest
from PIL import Image
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ctp500_ble_cli import (
    prepare_image_for_printer,
    image_to_raster_bytes,
    floyd_steinberg_dither,
    PRINTER_WIDTH,
)


class TestFloydSteinbergDither:
    """Tests for floyd_steinberg_dither function"""

    @pytest.mark.unit
    def test_returns_1bit_image(self):
        """Test that dithering returns 1-bit image"""
        img = Image.new("L", (100, 100), 128)
        result = floyd_steinberg_dither(img)
        assert result.mode == "1"

    @pytest.mark.unit
    def test_preserves_dimensions(self):
        """Test that dithering preserves image dimensions"""
        width, height = 200, 150
        img = Image.new("L", (width, height), 128)
        result = floyd_steinberg_dither(img)
        assert result.size == (width, height)

    @pytest.mark.unit
    def test_pure_white_stays_white(self):
        """Test that pure white pixels stay white"""
        img = Image.new("L", (10, 10), 255)
        result = floyd_steinberg_dither(img)
        # All pixels should be white (255 in mode '1')
        pixels = list(result.getdata())
        assert all(p == 255 for p in pixels)

    @pytest.mark.unit
    def test_pure_black_stays_black(self):
        """Test that pure black pixels stay black"""
        img = Image.new("L", (10, 10), 0)
        result = floyd_steinberg_dither(img)
        # All pixels should be black (0 in mode '1')
        pixels = list(result.getdata())
        assert all(p == 0 for p in pixels)

    @pytest.mark.unit
    def test_mid_gray_produces_pattern(self):
        """Test that mid-gray produces dithered pattern (mix of black and white)"""
        img = Image.new("L", (100, 100), 128)
        result = floyd_steinberg_dither(img)
        pixels = list(result.getdata())

        # Should have both black and white pixels (dithered)
        unique_values = set(pixels)
        assert 0 in unique_values or 255 in unique_values
        # For mid-gray, should have roughly 50% black pixels
        black_count = sum(1 for p in pixels if p == 0)
        black_ratio = black_count / len(pixels)
        # Allow 30-70% range (dithering creates patterns)
        assert 0.3 <= black_ratio <= 0.7

    @pytest.mark.unit
    def test_gradient_produces_varying_density(self):
        """Test that gradient produces varying dot density"""
        # Create gradient from black to white
        img = Image.new("L", (256, 100))
        for x in range(256):
            for y in range(100):
                img.putpixel((x, y), x)  # Gradient 0-255

        result = floyd_steinberg_dither(img)

        # Left side (dark) should have more black pixels than right (light)
        left_pixels = [result.getpixel((x, 50)) for x in range(50)]
        right_pixels = [result.getpixel((x, 50)) for x in range(206, 256)]

        left_black = sum(1 for p in left_pixels if p == 0)
        right_black = sum(1 for p in right_pixels if p == 0)

        # Left should have significantly more black pixels
        assert left_black > right_black


class TestPrepareImageForPrinter:
    """Tests for prepare_image_for_printer function"""

    @pytest.mark.unit
    def test_converts_to_1bit_mode(self):
        """Test that output is 1-bit image"""
        img = Image.new("RGB", (100, 100), (128, 128, 128))
        result = prepare_image_for_printer(img)
        assert result.mode == "1"

    @pytest.mark.unit
    def test_width_matches_printer_width(self):
        """Test that output width matches printer width"""
        img = Image.new("RGB", (100, 100))
        result = prepare_image_for_printer(img, printer_width=384)
        assert result.width == 384

    @pytest.mark.unit
    def test_pads_narrow_image(self):
        """Test that images narrower than printer width are padded"""
        img = Image.new("L", (100, 100), 128)
        result = prepare_image_for_printer(img, printer_width=384)
        assert result.width == 384

    @pytest.mark.unit
    def test_scales_down_wide_image(self):
        """Test that images wider than printer are scaled down"""
        img = Image.new("L", (800, 400), 128)
        result = prepare_image_for_printer(img, printer_width=384)
        assert result.width == 384
        # Aspect ratio should be preserved (approximately)
        expected_height = int(400 * (384 / 800))
        assert abs(result.height - expected_height) <= 1

    @pytest.mark.unit
    def test_width_multiple_of_8(self):
        """Test that output width is always a multiple of 8"""
        # Test with various widths
        for width in [100, 381, 390]:
            img = Image.new("L", (width, 100), 128)
            result = prepare_image_for_printer(img, printer_width=width)
            assert result.width % 8 == 0

    @pytest.mark.unit
    def test_threshold_creates_pure_bw(self):
        """Test that thresholding creates pure black and white"""
        img = Image.new("L", (100, 100), 128)
        result = prepare_image_for_printer(img)

        # Get pixel values - in mode '1', should be 0 or 255
        pixels = list(result.getdata())
        unique_values = set(pixels)
        # In PIL mode '1', pixels are 0 (black) or 255 (white)
        assert unique_values.issubset({0, 255})

    @pytest.mark.unit
    def test_threshold_at_128(self):
        """Test that threshold is at value 128"""
        # Create image with gradient
        img = Image.new("L", (PRINTER_WIDTH, 2))
        # Top row: values below threshold (should become black = 0)
        for x in range(PRINTER_WIDTH):
            img.putpixel((x, 0), 127)
        # Bottom row: values at/above threshold (should become white = 255)
        for x in range(PRINTER_WIDTH):
            img.putpixel((x, 1), 128)

        result = prepare_image_for_printer(img)

        # Check first row is black
        assert result.getpixel((0, 0)) == 0
        # Check second row is white
        assert result.getpixel((0, 1)) == 255

    @pytest.mark.unit
    def test_handles_rgba_mode(self):
        """Test handling of RGBA images"""
        img = Image.new("RGBA", (100, 100), (128, 128, 128, 255))
        result = prepare_image_for_printer(img)
        assert result.mode == "1"
        assert result.width % 8 == 0

    @pytest.mark.unit
    def test_handles_1bit_mode(self):
        """Test handling of already 1-bit images"""
        img = Image.new("1", (100, 100), 1)
        result = prepare_image_for_printer(img)
        assert result.mode == "1"

    @pytest.mark.unit
    def test_preserves_height_for_correct_width(self):
        """Test that height is preserved when width matches"""
        height = 200
        img = Image.new("L", (PRINTER_WIDTH, height), 128)
        result = prepare_image_for_printer(img, printer_width=PRINTER_WIDTH)
        assert result.height == height


class TestImageToRasterBytes:
    """Tests for image_to_raster_bytes function"""

    @pytest.mark.unit
    def test_header_format(self):
        """Test that raster header is correct format"""
        img = Image.new("1", (384, 100), 255)
        result = image_to_raster_bytes(img)

        # Header should be: 1D 76 30 00 (4 bytes)
        assert result[0:4] == b"\x1d\x76\x30\x00"

    @pytest.mark.unit
    def test_width_encoding_in_header(self):
        """Test that width is correctly encoded in header (little-endian)"""
        width = 384
        img = Image.new("1", (width, 100), 255)
        result = image_to_raster_bytes(img)

        width_bytes = width // 8
        # Bytes 4-5 are width in bytes (little-endian)
        assert result[4] == width_bytes & 0xFF
        assert result[5] == (width_bytes >> 8) & 0xFF

    @pytest.mark.unit
    def test_height_encoding_in_header(self):
        """Test that height is correctly encoded in header (little-endian)"""
        height = 250
        img = Image.new("1", (384, height), 255)
        result = image_to_raster_bytes(img)

        # Bytes 6-7 are height (little-endian)
        assert result[6] == height & 0xFF
        assert result[7] == (height >> 8) & 0xFF

    @pytest.mark.unit
    def test_data_length(self):
        """Test that total data length is correct"""
        width = 384
        height = 100
        img = Image.new("1", (width, height), 255)
        result = image_to_raster_bytes(img)

        # Total should be: 8 byte header + (width/8 * height) data bytes
        expected_length = 8 + (width // 8) * height
        assert len(result) == expected_length

    @pytest.mark.unit
    def test_black_is_one_false(self):
        """Test bit polarity when black_is_one=False"""
        # Create 8px wide, 1px tall image, all black
        img = Image.new("1", (8, 1), 0)  # 0 = black in PIL mode '1'
        result = image_to_raster_bytes(img, black_is_one=False)

        # With black_is_one=False, black pixels (0) stay as 0 bits
        # 8 black pixels = 0b00000000 = 0x00
        data_byte = result[8]  # First data byte after header
        assert data_byte == 0x00

    @pytest.mark.unit
    def test_black_is_one_true(self):
        """Test bit polarity when black_is_one=True"""
        # Create 8px wide, 1px tall image, all black
        img = Image.new("1", (8, 1), 0)  # 0 = black in PIL mode '1'
        result = image_to_raster_bytes(img, black_is_one=True)

        # With black_is_one=True, black pixels (0) are inverted to 1 bits
        # 8 black pixels = 0b11111111 = 0xFF
        data_byte = result[8]  # First data byte after header
        assert data_byte == 0xFF

    @pytest.mark.unit
    def test_mixed_pixels_bit_packing(self):
        """Test that pixels are correctly packed into bytes"""
        # Create 8px wide, 1px tall image with alternating pattern
        img = Image.new("1", (8, 1))
        # Pattern: black, white, black, white, black, white, black, white
        for x in range(8):
            img.putpixel((x, 0), 0 if x % 2 == 0 else 255)

        result = image_to_raster_bytes(img, black_is_one=False)

        # Black=0, White=1 in output (since black_is_one=False)
        # Pattern: 0,1,0,1,0,1,0,1 = 0b01010101 = 0x55
        data_byte = result[8]
        assert data_byte == 0x55

    @pytest.mark.unit
    def test_raises_on_non_multiple_of_8_width(self):
        """Test that function raises error for width not multiple of 8"""
        img = Image.new("1", (100, 100), 255)  # 100 is not multiple of 8

        with pytest.raises(ValueError, match="multiple of 8"):
            image_to_raster_bytes(img)

    @pytest.mark.unit
    def test_large_image(self):
        """Test handling of larger images"""
        width = 384
        height = 1000
        img = Image.new("1", (width, height), 255)
        result = image_to_raster_bytes(img)

        expected_length = 8 + (width // 8) * height
        assert len(result) == expected_length

    @pytest.mark.unit
    def test_all_white_image(self):
        """Test all-white image produces expected output"""
        img = Image.new("1", (384, 100), 255)  # All white
        result = image_to_raster_bytes(img, black_is_one=False)

        # All white pixels = all 1 bits = all 0xFF bytes
        data_section = result[8:]
        assert all(byte == 0xFF for byte in data_section)

    @pytest.mark.unit
    def test_all_black_image(self):
        """Test all-black image produces expected output"""
        img = Image.new("1", (384, 100), 0)  # All black
        result = image_to_raster_bytes(img, black_is_one=False)

        # All black pixels = all 0 bits = all 0x00 bytes
        data_section = result[8:]
        assert all(byte == 0x00 for byte in data_section)
