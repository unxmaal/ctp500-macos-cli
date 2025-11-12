# CTP500 BLE CLI (macOS)

Command-line BLE driver for the Walmart CTP500 / “Teal Printer” thermal printer.

This tool:

- Uses **bleak** to talk BLE GATT on macOS
- Renders text/images to bitmaps with **Pillow**/
- Sends ESC/POS-style raster commands over a UART-over-BLE characteristic


## 1. Prerequisites

- macOS with Bluetooth enabled
- Python 3.13+
- Printer powered on and nearby

Install Python dependencies:

    pip install bleak pillow

## 2. Pair the printer (macOS UI)

5. Open System Settings → Bluetooth
2. Put the printer into pairing mode
3. Pair it (it will appear as something like ‘Teal Printer’)

## 3. Find the BLE address

    ./ctp500_ble_cli.py scan

Look for a line like:

    D210000E-A47D-2971-6819-A5F4389E7B86  |  name='Teal Printer'

Copy that address.

## 4. Discover services & characteristics

    ./ctp500_ble_cli.py inspect --address D210000E-A47D-2971-6819-A5F4189E7B86

You should see a vendor service like:

    Service 49535343-fe7d-4ae5-8fa9-9fafd205e455
      Char 49535343-8841-43f4-a8d4-ecbe34729bb3  [write-without-response,write]

The write characteristic UUID is 

    49535343-8841-43f4-a8d4-ecbe34729bb3

## 5. Configure environment

    export CTP500_WRITE_UUID=49535343-8841-43f4-a8d4-ecbe34729bb3
    export CTP500_FONT=/System/Library/Fonts/Menlo.ttc
    export CTP500_FONT_SIZE=40
    export CSP500_BLACK_IS_ONE=1

## 6. Print text

Inline:

    ./ctp500_ble_cli.py text  \
      --address D210000E-A47D-2971-6819-A5F4389E7B86 \
      --message "Hello from macOS" \
      --black-is-one \
      --chunk-size 20

From file:

    ./ctp500_ble_cli.py text \
      --address D210000E-A47D-2971-6819-A5F4189E7B86 \
      --file note.txt \
      --black-is-one \
      --chunk-size 20

## 7. Print image

    ./ctp500_ble_cli.py image \
      --address D210000E-A47D-2971-6819-A5F4389E7B86 \
      --file picture.png \
      --black-is-one \
      --chunk-size 20

## 8. Tuning

- Increase or decrease CTP500_FONT_SIZE do change text size
- Try larger --chunk-size for faster transfer; if prints become unreliable, drop back to 20
