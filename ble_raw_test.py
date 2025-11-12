#!/usr/bin/env python3
import asyncio
from bleak import BleakClient

ADDRESS = "D210000E-A47D-2971-6819-A5F4189E7B86"
WRITE_UUID = "49535343-8841-43f4-a8d4-ecbe34729bb3"


async def main():
    async with BleakClient(ADDRESS) as client:
        print("Connected, sending raw text...")
        # Try extremely simple text with newlines
        await client.write_gatt_char(WRITE_UUID, b"Hello from BLE\r\n\r\n\r\n", response=False)
        # Give it a moment to chew
        await asyncio.sleep(1.0)
    print("Done.")

if __name__ == "__main__":
    asyncio.run(main())

