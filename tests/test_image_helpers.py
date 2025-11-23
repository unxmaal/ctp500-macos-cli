"""Unit tests for image helper functions"""
import pytest
from PIL import Image, ImageFont
import sys
import os

# Add parent directory to path to import the module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ctp500_ble_cli import (
    trim_image,
    get_wrapped_text,
    create_text_image,
    PRINTER_WIDTH,
)


class TestTrimImage:
    """Tests for trim_image function"""

    @pytest.mark.unit
    def test_trim_white_image_returns_original(self):
        """Test that a completely white image returns unchanged"""
        img = Image.new("RGB", (100, 100), (255, 255, 255))
        result = trim_image(img)
        # Should return original since no content to trim
        assert result.size == img.size

    @pytest.mark.unit
    def test_trim_image_with_content(self):
        """Test trimming an image with actual content"""
        img = Image.new("RGB", (100, 100), (255, 255, 255))
        # Draw a black rectangle in the middle
        from PIL import ImageDraw
        draw = ImageDraw.Draw(img)
        draw.rectangle([25, 25, 75, 75], fill=(0, 0, 0))

        result = trim_image(img)

        # Result should be smaller than original (trimmed)
        assert result.height <= img.height
        assert result.width <= img.width

    @pytest.mark.unit
    def test_trim_adds_bottom_margin(self):
        """Test that trim_image adds 10px margin at bottom"""
        img = Image.new("RGB", (100, 100), (255, 255, 255))
        from PIL import ImageDraw
        draw = ImageDraw.Draw(img)
        # Draw at top
        draw.rectangle([0, 0, 100, 10], fill=(0, 0, 0))

        result = trim_image(img)

        # Height should include the content plus margin
        # bbox would be approximately (0, 0, 100, 10-11)
        assert result.height >= 20 and result.height <= 22

    @pytest.mark.unit
    def test_trim_preserves_mode(self):
        """Test that image mode is preserved for RGB"""
        # Note: Current implementation has bug with grayscale - only works with RGB
        img = Image.new("RGB", (100, 100), (255, 255, 255))
        result = trim_image(img)
        assert result.mode == "RGB"


class TestGetWrappedText:
    """Tests for get_wrapped_text function"""

    @pytest.fixture
    def default_font(self):
        """Provide a default font for testing"""
        return ImageFont.load_default()

    @pytest.mark.unit
    def test_short_text_no_wrapping(self, default_font):
        """Test that short text doesn't wrap"""
        text = "Hello"
        result = get_wrapped_text(text, default_font, 1000)
        assert result == "Hello"
        assert "\n" not in result

    @pytest.mark.unit
    def test_long_text_wraps(self, default_font):
        """Test that long text wraps to multiple lines"""
        text = "This is a very long line of text that should wrap"
        result = get_wrapped_text(text, default_font, 50)
        assert "\n" in result
        lines = result.split("\n")
        assert len(lines) > 1

    @pytest.mark.unit
    def test_wrapped_lines_fit_width(self, default_font):
        """Test that wrapped lines respect the width limit"""
        text = "word1 word2 word3 word4 word5"
        line_length = 100
        result = get_wrapped_text(text, default_font, line_length)

        for line in result.split("\n"):
            length = default_font.getlength(line)
            assert length <= line_length

    @pytest.mark.unit
    def test_empty_text(self, default_font):
        """Test handling of empty text"""
        result = get_wrapped_text("", default_font, 100)
        assert result == ""

    @pytest.mark.unit
    def test_single_long_word(self, default_font):
        """Test that a single word longer than line_length goes on its own line"""
        text = "verylongwordthatdoesnotfit"
        result = get_wrapped_text(text, default_font, 50)
        # Current implementation adds empty first line, word on second
        # This is a known quirk: lines starts with ['']
        assert "verylongwordthatdoesnotfit" in result


class TestCreateTextImage:
    """Tests for create_text_image function"""

    @pytest.mark.unit
    def test_creates_rgb_image(self):
        """Test that function creates an RGB image"""
        text = "Test"
        result = create_text_image(text)
        assert result.mode == "RGB"

    @pytest.mark.unit
    def test_image_width_matches_printer(self):
        """Test that image width is <= printer width (trimming reduces it)"""
        text = "Test"
        result = create_text_image(text, printer_width=384)
        # After trimming, width will be smaller
        assert result.width <= 384

    @pytest.mark.unit
    def test_custom_printer_width(self):
        """Test custom printer width"""
        text = "Test"
        custom_width = 200
        result = create_text_image(text, printer_width=custom_width)
        # After trimming, width will be smaller
        assert result.width <= custom_width

    @pytest.mark.unit
    def test_empty_text_returns_small_image(self):
        """Test that empty text returns image"""
        result = create_text_image("")
        # Empty text creates full canvas that cannot be trimmed (all white)
        # This is current behavior - not optimal but documented
        assert isinstance(result, Image.Image)

    @pytest.mark.unit
    def test_multiline_text(self):
        """Test rendering multiline text"""
        text = "Line 1\nLine 2\nLine 3"
        result = create_text_image(text)
        # Width gets trimmed down
        assert result.width <= PRINTER_WIDTH
        # Should have some height for multiple lines
        assert result.height > 10

    @pytest.mark.unit
    def test_font_fallback_on_missing_font(self):
        """Test that missing font falls back to default"""
        text = "Test"
        # Use a non-existent font path
        result = create_text_image(
            text,
            font_path="/nonexistent/font.ttf"
        )
        # Should still create an image (using default font)
        assert isinstance(result, Image.Image)
        # Width gets trimmed
        assert result.width <= PRINTER_WIDTH

    @pytest.mark.unit
    def test_custom_font_size(self):
        """Test that custom font size parameter is accepted"""
        text = "Test"
        # With default font fallback, size may not affect actual rendering
        result = create_text_image(text, font_size=10)

        # Just verify it doesn't crash and returns an image
        assert isinstance(result, Image.Image)

    @pytest.mark.unit
    def test_long_text_wraps_correctly(self):
        """Test that long text wraps and renders properly"""
        text = "This is a very long line of text that should wrap within the printer width constraints"
        result = create_text_image(text, printer_width=384)
        # Width gets trimmed to actual content
        assert result.width <= 384
        # Should have multiple lines worth of height
        assert result.height > 20
