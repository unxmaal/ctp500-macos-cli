"""Integration tests for command functions with BLE mocking"""
import pytest
import sys
import os
from unittest.mock import AsyncMock, MagicMock, patch, mock_open
from argparse import Namespace
from PIL import Image
import io

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ctp500_ble_cli import (
    scan_devices,
    inspect_device,
    do_status,
    do_text,
    do_image,
    connect_client,
)


class TestScanDevices:
    """Tests for scan_devices command"""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_scan_finds_devices(self, capsys):
        """Test that scan discovers and displays BLE devices"""
        # Mock device
        mock_device = MagicMock()
        mock_device.address = "AA:BB:CC:DD:EE:FF"
        mock_device.name = "Test Printer"
        mock_device.rssi = -50

        args = Namespace(timeout=5.0)

        with patch('ctp500_ble_cli.BleakScanner.discover', new_callable=AsyncMock) as mock_discover:
            mock_discover.return_value = [mock_device]
            await scan_devices(args)

        captured = capsys.readouterr()
        assert "AA:BB:CC:DD:EE:FF" in captured.out
        assert "Test Printer" in captured.out

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_scan_no_devices(self, capsys):
        """Test scan when no devices are found"""
        args = Namespace(timeout=5.0)

        with patch('ctp500_ble_cli.BleakScanner.discover', new_callable=AsyncMock) as mock_discover:
            mock_discover.return_value = []
            await scan_devices(args)

        captured = capsys.readouterr()
        assert "No BLE devices found" in captured.out

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_scan_uses_timeout(self):
        """Test that scan uses the specified timeout"""
        args = Namespace(timeout=10.0)

        with patch('ctp500_ble_cli.BleakScanner.discover', new_callable=AsyncMock) as mock_discover:
            mock_discover.return_value = []
            await scan_devices(args)

            mock_discover.assert_called_once_with(timeout=10.0)


class TestInspectDevice:
    """Tests for inspect_device command"""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_inspect_without_address_exits(self):
        """Test that inspect exits when no address provided"""
        args = Namespace(address=None)

        with pytest.raises(SystemExit):
            await inspect_device(args)

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_inspect_displays_services(self, capsys):
        """Test that inspect connects to device"""
        args = Namespace(address="AA:BB:CC:DD:EE:FF")

        # Mock service and characteristic
        mock_char = MagicMock()
        mock_char.uuid = "char-uuid-1234"
        mock_char.properties = ["read", "write"]
        mock_char.description = "Test Char"

        mock_service = MagicMock()
        mock_service.uuid = "service-uuid-5678"
        mock_service.description = "Test Service"
        mock_service.characteristics = [mock_char]

        mock_services = [mock_service]

        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()
        mock_client.services = mock_services

        with patch('ctp500_ble_cli.BleakClient', return_value=mock_client):
            await inspect_device(args)

        captured = capsys.readouterr()
        # Verify it at least connects
        assert "Connecting" in captured.out or "Connected" in captured.out


class TestDoStatus:
    """Tests for do_status command"""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_status_without_address_exits(self):
        """Test that status exits when no address provided"""
        args = Namespace(address=None, write_uuid="uuid", status_uuid=None)

        with pytest.raises(SystemExit):
            await do_status(args)

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_status_without_write_uuid_exits(self):
        """Test that status exits when no write UUID available"""
        args = Namespace(address="AA:BB:CC:DD:EE:FF", write_uuid=None, status_uuid=None)

        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(SystemExit):
                await do_status(args)

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_status_with_status_uuid(self, capsys):
        """Test status command with status UUID"""
        args = Namespace(
            address="AA:BB:CC:DD:EE:FF",
            write_uuid="write-uuid",
            status_uuid="status-uuid"
        )

        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()
        mock_client.write_gatt_char = AsyncMock()
        mock_client.read_gatt_char = AsyncMock(return_value=b"\xAA\xBB")

        with patch('ctp500_ble_cli.BleakClient', return_value=mock_client):
            with patch('asyncio.sleep', new_callable=AsyncMock):
                await do_status(args)

        captured = capsys.readouterr()
        assert "aabb" in captured.out.lower()

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_status_without_status_uuid(self, capsys):
        """Test status command without status UUID (basic connect test)"""
        args = Namespace(
            address="AA:BB:CC:DD:EE:FF",
            write_uuid="write-uuid",
            status_uuid=None
        )

        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()

        with patch('ctp500_ble_cli.BleakClient', return_value=mock_client):
            await do_status(args)

        captured = capsys.readouterr()
        assert "No status UUID configured" in captured.out


class TestDoText:
    """Tests for do_text command"""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_text_without_address_exits(self):
        """Test that text command exits when no address provided"""
        args = Namespace(
            address=None,
            write_uuid="uuid",
            file=None,
            message="test",
            font=None,
            font_size=None,
            chunk_size=180,
            black_is_one=False
        )

        with pytest.raises(SystemExit):
            await do_text(args)

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_text_without_content_exits(self):
        """Test that text command exits when no text provided"""
        args = Namespace(
            address="AA:BB:CC:DD:EE:FF",
            write_uuid="uuid",
            file=None,
            message=None,
            font=None,
            font_size=None,
            chunk_size=180,
            black_is_one=False
        )

        with pytest.raises(SystemExit):
            await do_text(args)

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_text_with_inline_message(self):
        """Test text command with inline message"""
        args = Namespace(
            address="AA:BB:CC:DD:EE:FF",
            write_uuid="write-uuid",
            file=None,
            message="Hello World",
            font=None,
            font_size=None,
            chunk_size=180,
            black_is_one=False
        )

        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()
        mock_client.write_gatt_char = AsyncMock()

        with patch('ctp500_ble_cli.BleakClient', return_value=mock_client):
            with patch('asyncio.sleep', new_callable=AsyncMock):
                await do_text(args)

        # Verify write was called (connection is automatic via context manager)
        assert mock_client.write_gatt_char.call_count > 0

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_text_with_file(self):
        """Test text command with file input"""
        args = Namespace(
            address="AA:BB:CC:DD:EE:FF",
            write_uuid="write-uuid",
            file="test.txt",
            message=None,
            font=None,
            font_size=None,
            chunk_size=180,
            black_is_one=False
        )

        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()
        mock_client.write_gatt_char = AsyncMock()

        file_content = "Content from file"

        with patch('ctp500_ble_cli.BleakClient', return_value=mock_client):
            with patch('asyncio.sleep', new_callable=AsyncMock):
                with patch('builtins.open', mock_open(read_data=file_content)):
                    await do_text(args)

        # Verify write was called (connection is automatic via context manager)
        assert mock_client.write_gatt_char.call_count > 0


class TestDoImage:
    """Tests for do_image command"""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_image_without_address_exits(self):
        """Test that image command exits when no address provided"""
        args = Namespace(
            address=None,
            write_uuid="uuid",
            file="test.png",
            chunk_size=180,
            black_is_one=False
        )

        with pytest.raises(SystemExit):
            await do_image(args)

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_image_without_file_exits(self):
        """Test that image command exits when no file provided"""
        args = Namespace(
            address="AA:BB:CC:DD:EE:FF",
            write_uuid="uuid",
            file=None,
            chunk_size=180,
            black_is_one=False
        )

        with pytest.raises(SystemExit):
            await do_image(args)

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_image_prints_successfully(self):
        """Test image command with valid image file"""
        args = Namespace(
            address="AA:BB:CC:DD:EE:FF",
            write_uuid="write-uuid",
            file="test.png",
            chunk_size=180,
            black_is_one=False
        )

        # Create a test image in memory
        test_image = Image.new("RGB", (100, 100), (255, 255, 255))

        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()
        mock_client.write_gatt_char = AsyncMock()

        with patch('ctp500_ble_cli.BleakClient', return_value=mock_client):
            with patch('asyncio.sleep', new_callable=AsyncMock):
                with patch('ctp500_ble_cli.Image.open', return_value=test_image):
                    await do_image(args)

        # Verify write was called (connection is automatic via context manager)
        assert mock_client.write_gatt_char.call_count > 0


class TestConnectClient:
    """Tests for connect_client utility"""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_connect_client_returns_connected_client(self):
        """Test that connect_client returns a connected BleakClient"""
        address = "AA:BB:CC:DD:EE:FF"

        mock_client = MagicMock()
        mock_client.connect = AsyncMock()

        with patch('ctp500_ble_cli.BleakClient', return_value=mock_client):
            result = await connect_client(address)

        assert result == mock_client
        mock_client.connect.assert_called_once()
