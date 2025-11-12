#!/usr/bin/env python3
import serial, time

port = "/dev/cu.TealPrinter"  # adjust if needed
baud = 9600

ser = serial.Serial(
    port=port,
    baudrate=baud,
    timeout=2,
    write_timeout=5,
)

print("Opening", port)
time.sleep(0.5)

# Initialize printer
ser.write(b"\x1b\x40")
ser.flush()
time.sleep(0.5)

# Try a very dumb text print (many ESC/POS printers accept this)
ser.write(b"Hello from macOS\n\n\n\n")
ser.flush()
time.sleep(1.0)

ser.close()
print("Done.")

