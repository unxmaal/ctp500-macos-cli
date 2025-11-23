"""Unit tests for printer protocol helper functions"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, call, patch
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ctp500_ble_cli import (
    write_long,
    send_init_and_start,
    send_end,
    send_status_request,
    INIT_SEQUENCE,
    START_PRINT_SEQUENCE,
    END_PRINT_SEQUENCE,
    STATUS_REQUEST,
)


class TestWriteLong:
    """Tests for write_long function"""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_writes_single_chunk(self):
        """Test writing data smaller than chunk size"""
        mock_client = MagicMock()
        mock_client.write_gatt_char = AsyncMock()

        data = b"hello"
        char_uuid = "test-uuid"

        await write_long(mock_client, char_uuid, data, chunk_size=100, delay=0)

        # Should write once
        mock_client.write_gatt_char.assert_called_once_with(
            char_uuid, data, response=False
        )

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_writes_multiple_chunks(self):
        """Test writing data larger than chunk size"""
        mock_client = MagicMock()
        mock_client.write_gatt_char = AsyncMock()

        data = b"a" * 250  # 250 bytes
        char_uuid = "test-uuid"
        chunk_size = 100

        await write_long(mock_client, char_uuid, data, chunk_size=chunk_size, delay=0)

        # Should write 3 times (100 + 100 + 50)
        assert mock_client.write_gatt_char.call_count == 3

        # Verify chunks
        calls = mock_client.write_gatt_char.call_args_list
        assert calls[0] == call(char_uuid, b"a" * 100, response=False)
        assert calls[1] == call(char_uuid, b"a" * 100, response=False)
        assert calls[2] == call(char_uuid, b"a" * 50, response=False)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_exact_multiple_of_chunk_size(self):
        """Test writing data that is exactly a multiple of chunk size"""
        mock_client = MagicMock()
        mock_client.write_gatt_char = AsyncMock()

        data = b"x" * 200
        chunk_size = 100

        await write_long(mock_client, char_uuid="uuid", data=data, chunk_size=chunk_size, delay=0)

        # Should write exactly 2 chunks
        assert mock_client.write_gatt_char.call_count == 2

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_empty_data(self):
        """Test writing empty data"""
        mock_client = MagicMock()
        mock_client.write_gatt_char = AsyncMock()

        await write_long(mock_client, "uuid", b"", chunk_size=100, delay=0)

        # Should not write anything
        mock_client.write_gatt_char.assert_not_called()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_delay_between_chunks(self):
        """Test that delay is applied between chunks"""
        mock_client = MagicMock()
        mock_client.write_gatt_char = AsyncMock()

        data = b"x" * 250
        delay = 0.01

        with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
            await write_long(mock_client, "uuid", data, chunk_size=100, delay=delay)

            # Should sleep 3 times (once after each chunk)
            assert mock_sleep.call_count == 3
            mock_sleep.assert_called_with(delay)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_no_delay_when_zero(self):
        """Test that no sleep occurs when delay is 0"""
        mock_client = MagicMock()
        mock_client.write_gatt_char = AsyncMock()

        data = b"x" * 250

        with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
            await write_long(mock_client, "uuid", data, chunk_size=100, delay=0)

            # Should not sleep when delay is 0
            mock_sleep.assert_not_called()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_response_false_parameter(self):
        """Test that write_gatt_char is called with response=False"""
        mock_client = MagicMock()
        mock_client.write_gatt_char = AsyncMock()

        await write_long(mock_client, "uuid", b"test", chunk_size=100, delay=0)

        # Verify response=False
        mock_client.write_gatt_char.assert_called_with("uuid", b"test", response=False)


class TestSendInitAndStart:
    """Tests for send_init_and_start function"""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_sends_init_sequence(self):
        """Test that init sequence is sent"""
        mock_client = MagicMock()
        mock_client.write_gatt_char = AsyncMock()

        with patch('asyncio.sleep', new_callable=AsyncMock):
            await send_init_and_start(mock_client, "test-uuid")

        # First call should be init sequence
        first_call = mock_client.write_gatt_char.call_args_list[0]
        assert first_call[0][0] == "test-uuid"
        assert first_call[0][1] == INIT_SEQUENCE
        assert first_call[1]["response"] is False

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_sends_start_sequence(self):
        """Test that start print sequence is sent"""
        mock_client = MagicMock()
        mock_client.write_gatt_char = AsyncMock()

        with patch('asyncio.sleep', new_callable=AsyncMock):
            await send_init_and_start(mock_client, "test-uuid")

        # Second call should be start sequence
        second_call = mock_client.write_gatt_char.call_args_list[1]
        assert second_call[0][0] == "test-uuid"
        assert second_call[0][1] == START_PRINT_SEQUENCE
        assert second_call[1]["response"] is False

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_delays_between_commands(self):
        """Test that delays are added between commands"""
        mock_client = MagicMock()
        mock_client.write_gatt_char = AsyncMock()

        with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
            await send_init_and_start(mock_client, "test-uuid")

            # Should sleep twice (after each write)
            assert mock_sleep.call_count == 2
            mock_sleep.assert_called_with(0.1)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_correct_sequence_order(self):
        """Test that init is sent before start"""
        mock_client = MagicMock()
        mock_client.write_gatt_char = AsyncMock()

        with patch('asyncio.sleep', new_callable=AsyncMock):
            await send_init_and_start(mock_client, "test-uuid")

        calls = mock_client.write_gatt_char.call_args_list
        assert len(calls) == 2
        assert calls[0][0][1] == INIT_SEQUENCE
        assert calls[1][0][1] == START_PRINT_SEQUENCE


class TestSendEnd:
    """Tests for send_end function"""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_sends_end_sequence(self):
        """Test that end sequence is sent"""
        mock_client = MagicMock()
        mock_client.write_gatt_char = AsyncMock()

        with patch('asyncio.sleep', new_callable=AsyncMock):
            await send_end(mock_client, "test-uuid")

        mock_client.write_gatt_char.assert_called_once_with(
            "test-uuid", END_PRINT_SEQUENCE, response=False
        )

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_delays_after_send(self):
        """Test that delay is added after sending"""
        mock_client = MagicMock()
        mock_client.write_gatt_char = AsyncMock()

        with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
            await send_end(mock_client, "test-uuid")

            mock_sleep.assert_called_once_with(0.1)


class TestSendStatusRequest:
    """Tests for send_status_request function"""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_sends_status_request(self):
        """Test that status request is sent to write characteristic"""
        mock_client = MagicMock()
        mock_client.write_gatt_char = AsyncMock()
        mock_client.read_gatt_char = AsyncMock(return_value=b"\x00\x01")

        with patch('asyncio.sleep', new_callable=AsyncMock):
            await send_status_request(mock_client, "write-uuid", "status-uuid")

        mock_client.write_gatt_char.assert_called_once_with(
            "write-uuid", STATUS_REQUEST, response=False
        )

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_reads_from_status_characteristic(self):
        """Test that status is read from status characteristic"""
        mock_client = MagicMock()
        mock_client.write_gatt_char = AsyncMock()
        mock_client.read_gatt_char = AsyncMock(return_value=b"\x00\x01")

        with patch('asyncio.sleep', new_callable=AsyncMock):
            await send_status_request(mock_client, "write-uuid", "status-uuid")

        mock_client.read_gatt_char.assert_called_once_with("status-uuid")

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_returns_status_data(self):
        """Test that function returns the status data"""
        mock_client = MagicMock()
        mock_client.write_gatt_char = AsyncMock()
        expected_data = b"\xAA\xBB\xCC"
        mock_client.read_gatt_char = AsyncMock(return_value=expected_data)

        with patch('asyncio.sleep', new_callable=AsyncMock):
            result = await send_status_request(mock_client, "write-uuid", "status-uuid")

        assert result == expected_data

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_delays_before_read(self):
        """Test that delay is added before reading status"""
        mock_client = MagicMock()
        mock_client.write_gatt_char = AsyncMock()
        mock_client.read_gatt_char = AsyncMock(return_value=b"\x00")

        with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
            await send_status_request(mock_client, "write-uuid", "status-uuid")

            mock_sleep.assert_called_once_with(0.2)


class TestProtocolConstants:
    """Tests for protocol constant definitions"""

    @pytest.mark.unit
    def test_init_sequence_value(self):
        """Test that INIT_SEQUENCE has correct ESC/POS value"""
        assert INIT_SEQUENCE == b"\x1b\x40"

    @pytest.mark.unit
    def test_start_print_sequence_value(self):
        """Test that START_PRINT_SEQUENCE has expected value"""
        assert START_PRINT_SEQUENCE == b"\x1d\x49\xf0\x19"

    @pytest.mark.unit
    def test_end_print_sequence_value(self):
        """Test that END_PRINT_SEQUENCE has expected value"""
        assert END_PRINT_SEQUENCE == b"\x0a\x0a\x0a\x9a"

    @pytest.mark.unit
    def test_status_request_value(self):
        """Test that STATUS_REQUEST has expected value"""
        assert STATUS_REQUEST == b"\x1e\x47\x03"
