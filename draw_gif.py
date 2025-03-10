import asyncio
import sys
import time
from PIL import Image, ImageSequence
from bleak import BleakScanner, BleakClient

# Service and characteristic UUIDs as discovered
SERVICE_UUID = "0000ffd0-0000-1000-8000-00805f9b34fb"
CHARACTERISTIC_UUID = "0000ffd1-0000-1000-8000-00805f9b34fb"

def load_frames(image_path):
    """
    Load a GIF and ensure it is 16x16 pixels.
    """
    try:
        img = Image.open(image_path)
        if img.size != (16, 16):
            raise ValueError("Image must be exactly 16x16 pixels.")
        if img.format != 'GIF':
            raise ValueError("Image must be in GIF format.")
        
        frames = []
        durations = []
        
        for frame in ImageSequence.Iterator(img):
            frame = frame.convert('RGB')
            picture = [frame.getpixel((x, y)) for y in range(16) for x in range(16)]
            frames.append(picture)
            durations.append(frame.info.get("duration", 100) / 1000.0)  # Convert ms to seconds
        
        return frames, durations if frames else None
    
    except Exception as e:
        print(f"Error loading image: {e}")
        sys.exit(1)

def get_full_picture_command(block_index: int, block_pixels: list) -> bytearray:
    """Constructs a full-picture update command for a block of pixels."""
    header = bytearray([0xBC, 0x0F, (block_index+1) & 0xFF])
    pixel_data = bytearray([value for pixel in block_pixels for value in pixel])
    return header + pixel_data + bytearray([0x55])

async def send_image_blocks(client, picture):
    """Send image data blocks sequentially."""
    for block_index in range(8):
        start, end = block_index * 32, (block_index + 1) * 32
        command = get_full_picture_command(block_index, picture[start:end])
        await client.write_gatt_char(CHARACTERISTIC_UUID, command)
        await asyncio.sleep(0.005)

async def animate_gif(client, frames, durations):
    """Send frames sequentially with file-given delays."""
    try:
        print("Starting GIF animation (press Ctrl+C to stop)...")
        await send_command(client, "bc0ff1080855")  # Start image mode
        while True:
            for frame, delay in zip(frames, durations):
                await send_image_blocks(client, frame)
                await asyncio.sleep(delay)
    except KeyboardInterrupt:
        print("\nAnimation stopped.")
    except Exception as e:
        print(f"Error in animation: {e}")

async def send_command(client, hex_cmd):
    """Send a raw command to the device."""
    data = bytes.fromhex(hex_cmd)
    await client.write_gatt_char(CHARACTERISTIC_UUID, data)
    await asyncio.sleep(0.005)

async def main():
    if len(sys.argv) != 2:
        print("Usage: python image_to_matrix.py <image_file>")
        return
    
    image_path = sys.argv[1]
    frames, durations = load_frames(image_path)
    if not frames:
        print("Failed to process image frames.")
        return
    
    print("Scanning for BLE devices...")
    devices = await BleakScanner.discover()
    target = next((d for d in devices if d.name and "MI Matrix Display" in d.name), None)
    
    if not target:
        print("MI Matrix Display not found.")
        return
    
    print(f"Connecting to {target.name} ({target.address})...")
    try:
        async with BleakClient(target) as client:
            if client.is_connected:
                print("Connected! Starting animation...")
                await animate_gif(client, frames, durations)
            else:
                print("Failed to connect.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
