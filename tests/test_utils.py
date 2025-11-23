"""Unit tests for utility functions"""

import pytest
import sys
import os
from unittest.mock import patch, MagicMock
from argparse import Namespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ctp500_ble_cli import resolve_write_uuid


class TestResolveWriteUuid:
    """Tests for resolve_write_uuid function"""

    @pytest.mark.unit
    def test_uses_args_write_uuid_when_provided(self):
        """Test that args.write_uuid takes precedence"""
        args = Namespace(write_uuid="12345678-1234-1234-1234-123456789abc")

        with patch.dict(os.environ, {"CTP500_WRITE_UUID": "different-uuid"}):
            result = resolve_write_uuid(args)

        assert result == "12345678-1234-1234-1234-123456789abc"

    @pytest.mark.unit
    def test_uses_env_var_when_args_empty(self):
        """Test that environment variable is used when args is None"""
        # Note: DEFAULT_WRITE_UUID is set at module import, so patching
        # os.environ after import doesn't affect it. This test verifies
        # the function uses the pre-loaded DEFAULT_WRITE_UUID
        args = Namespace(write_uuid=None)

        # Import and reload module with patched environment
        with patch.dict(os.environ, {"CTP500_WRITE_UUID": "test-uuid-123"}, clear=True):
            import importlib
            import ctp500_ble_cli

            importlib.reload(ctp500_ble_cli)
            result = ctp500_ble_cli.resolve_write_uuid(args)

        assert result == "test-uuid-123"

    @pytest.mark.unit
    def test_strips_whitespace(self):
        """Test that UUIDs are stripped of whitespace"""
        args = Namespace(write_uuid="  uuid-with-spaces  ")

        result = resolve_write_uuid(args)

        assert result == "uuid-with-spaces"

    @pytest.mark.unit
    def test_converts_to_lowercase(self):
        """Test that UUIDs are converted to lowercase"""
        args = Namespace(write_uuid="ABCD-1234-EFGH")

        result = resolve_write_uuid(args)

        assert result == "abcd-1234-efgh"

    @pytest.mark.unit
    def test_exits_when_no_uuid_provided(self):
        """Test that function exits when no UUID is available"""
        args = Namespace(write_uuid=None)

        with patch.dict(os.environ, {}, clear=True):
            import importlib
            import ctp500_ble_cli

            importlib.reload(ctp500_ble_cli)
            with pytest.raises(SystemExit) as exc_info:
                ctp500_ble_cli.resolve_write_uuid(args)

            assert exc_info.value.code == 1

    @pytest.mark.unit
    def test_exits_when_uuid_is_empty_string(self):
        """Test that function exits when UUID is empty after stripping"""
        args = Namespace(write_uuid="   ")

        with pytest.raises(SystemExit) as exc_info:
            resolve_write_uuid(args)

        assert exc_info.value.code == 1

    @pytest.mark.unit
    def test_empty_env_var_causes_exit(self):
        """Test that empty environment variable causes exit"""
        args = Namespace(write_uuid=None)

        with patch.dict(os.environ, {"CTP500_WRITE_UUID": ""}):
            import importlib
            import ctp500_ble_cli

            importlib.reload(ctp500_ble_cli)
            with pytest.raises(SystemExit) as exc_info:
                ctp500_ble_cli.resolve_write_uuid(args)

            assert exc_info.value.code == 1

    @pytest.mark.unit
    def test_args_empty_string_falls_back_to_env(self):
        """Test that empty string in args falls back to environment"""
        args = Namespace(write_uuid="")

        # Import and reload module with patched environment
        with patch.dict(
            os.environ, {"CTP500_WRITE_UUID": "fallback-uuid-456"}, clear=True
        ):
            import importlib
            import ctp500_ble_cli

            importlib.reload(ctp500_ble_cli)
            result = ctp500_ble_cli.resolve_write_uuid(args)

        assert result == "fallback-uuid-456"


class TestConfigParsing:
    """Tests for configuration parsing from environment variables"""

    @pytest.mark.unit
    def test_printer_width_default(self):
        """Test PRINTER_WIDTH default value"""
        with patch.dict(os.environ, {}, clear=True):
            # Re-import to get fresh environment
            import importlib
            import ctp500_ble_cli

            importlib.reload(ctp500_ble_cli)

            # Should default to 384
            assert ctp500_ble_cli.PRINTER_WIDTH == 384

    @pytest.mark.unit
    def test_printer_width_from_env(self):
        """Test PRINTER_WIDTH can be set from environment"""
        with patch.dict(os.environ, {"CTP500_PRINTER_WIDTH": "500"}):
            import importlib
            import ctp500_ble_cli

            importlib.reload(ctp500_ble_cli)

            assert ctp500_ble_cli.PRINTER_WIDTH == 500

    @pytest.mark.unit
    def test_default_font_size(self):
        """Test DEFAULT_FONT_SIZE default value"""
        with patch.dict(os.environ, {}, clear=True):
            import importlib
            import ctp500_ble_cli

            importlib.reload(ctp500_ble_cli)

            assert ctp500_ble_cli.DEFAULT_FONT_SIZE == 28

    @pytest.mark.unit
    def test_font_size_from_env(self):
        """Test font size can be set from environment"""
        with patch.dict(os.environ, {"CTP500_FONT_SIZE": "40"}):
            import importlib
            import ctp500_ble_cli

            importlib.reload(ctp500_ble_cli)

            assert ctp500_ble_cli.DEFAULT_FONT_SIZE == 40

    @pytest.mark.unit
    def test_black_is_one_false_by_default(self):
        """Test DEFAULT_BLACK_IS_ONE is False by default"""
        with patch.dict(os.environ, {}, clear=True):
            import importlib
            import ctp500_ble_cli

            importlib.reload(ctp500_ble_cli)

            assert ctp500_ble_cli.DEFAULT_BLACK_IS_ONE is False

    @pytest.mark.unit
    @pytest.mark.parametrize("value", ["1", "true", "TRUE", "yes", "on"])
    def test_black_is_one_truthy_values(self, value):
        """Test that various truthy strings set BLACK_IS_ONE to True"""
        with patch.dict(os.environ, {"CTP500_BLACK_IS_ONE": value}):
            import importlib
            import ctp500_ble_cli

            importlib.reload(ctp500_ble_cli)

            assert ctp500_ble_cli.DEFAULT_BLACK_IS_ONE is True

    @pytest.mark.unit
    @pytest.mark.parametrize("value", ["0", "false", "FALSE", "no", "off", ""])
    def test_black_is_one_falsy_values(self, value):
        """Test that various falsy strings set BLACK_IS_ONE to False"""
        with patch.dict(os.environ, {"CTP500_BLACK_IS_ONE": value}):
            import importlib
            import ctp500_ble_cli

            importlib.reload(ctp500_ble_cli)

            assert ctp500_ble_cli.DEFAULT_BLACK_IS_ONE is False

    @pytest.mark.unit
    def test_default_font_path(self):
        """Test DEFAULT_FONT_PATH default value"""
        with patch.dict(os.environ, {}, clear=True):
            import importlib
            import ctp500_ble_cli

            importlib.reload(ctp500_ble_cli)

            assert ctp500_ble_cli.DEFAULT_FONT_PATH == "Lucon.ttf"

    @pytest.mark.unit
    def test_font_path_from_env(self):
        """Test font path can be set from environment"""
        custom_path = "/System/Library/Fonts/Menlo.ttc"
        with patch.dict(os.environ, {"CTP500_FONT": custom_path}):
            import importlib
            import ctp500_ble_cli

            importlib.reload(ctp500_ble_cli)

            assert ctp500_ble_cli.DEFAULT_FONT_PATH == custom_path
