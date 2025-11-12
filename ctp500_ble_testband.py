#!/usr/bin/env python3
import asyncio
from bleak import BleakClient

ADDRESS = "D210000E-A47D-2971-6819-A5F4189E7B86"
WRITE_UUID = "49535343-8841-43f4-a8d4-ecbe34729bb3"

INIT_SEQUENCE = b"\x1b\x40"          # ESC @
START_PRINT_SEQUENCE = b"\x1d\x49\xf0\x19"
END_PRINT_SEQUENCE = b"\x0a\x0a\x0a\x9a"

# Printer width from Mel's code
PRINTER_WIDTH = 384
BYTES_PER_ROW = PRINTER_WIDTH // 8
HEIGHT = 40  # 40 rows just as a test

def make_raster_block(fill_byte: int) -> bytes:
    """
    Build a raster block using ESC *raster* command:
      1d 76 30 00 | width_bytes_lo width_bytes_hi | height_lo height_hi | data...
    """
    header = bytearray(b"\x1d\x76\x30\x00")
    header += bytes([BYTES_PER_ROW & 0xFF, (BYTES_PER_ROW >> 8) & 0xFF])
    header += bytes([HEIGHT & 0xFF, (HEIGHT >> 8) & 0xFF])

    # Each row is BYTES_PER_ROW bytes, repeated HEIGHT times
    row = bytes([fill_byte]) * BYTES_PER_ROW
    data = row * HEIGHT

    return bytes(header) + data


async def main():
    async with BleakClient(ADDRESS) as client:
        print("Connected, sending init + start...")
        await client.write_gatt_char(WRITE_UUID, INIT_SEQUENCE, response=False)
        await asyncio.sleep(0.1)
        await client.write_gatt_char(WRITE_UUID, START_PRINT_SEQUENCE, response=False)
        await asyncio.sleep(0.1)

        # First try all 0xFF (all bits 1)
        print("Sending all-0xFF raster block...")
        raster_ff = make_raster_block(0xFF)
        # Chunk to 20B to be super-safe with BLE
        for i in range(0, len(raster_ff), 20):
            await client.write_gatt_char(WRITE_UUID, raster_ff[i:i+20], response=False)
            await asyncio.sleep(0.01)

        await asyncio.sleep(0.2)

        # Then try all 0x00 (all bits 0)
        print("Sending all-0x00 raster block...")
        raster_00 = make_raster_block(0x00)
        for i in range(0, len(raster_00), 20):
            await client.write_gatt_char(WRITE_UUID, raster_00[i:i+20], response=False)
            await asyncio.sleep(0.01)

        await asyncio.sleep(0.2)

        print("Sending end sequence...")
        await client.write_gatt_char(WRITE_UUID, END_PRINT_SEQUENCE, response=False)
        await asyncio.sleep(0.5)

    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())

