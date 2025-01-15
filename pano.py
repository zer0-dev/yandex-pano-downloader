import requests
import platform
import asyncio
import aiohttp
from PIL import Image
from io import BytesIO
import sys
import progressbar
import math
from typing import Dict, Optional

def fetch_and_process_json(url: str) -> Optional[Dict]:
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Accept": "*/*",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive"
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"Error retrieving data: {e}")
        return None

async def fetch_tile(session: aiohttp.ClientSession, url: str) -> Optional[Image.Image]:
    try:
        async with session.get(url) as response:
            response.raise_for_status()
            content = await response.read()
            return Image.open(BytesIO(content))
    except (aiohttp.ClientError, IOError) as e:
        print(f"Failed to fetch tile: {e}")
        return None

async def make_pano(image_id: str, pano_width: int, pano_height: int, tile_width: int, tile_height: int, auto_height: bool, zoom: int, filename: str = "pano.jpg") -> None:
    x_range = math.ceil(pano_width / tile_width)
    y_range = math.ceil(pano_height / tile_height)
    total_tiles = x_range * y_range
    
    if auto_height and pano_height != int(pano_width / 2):
        pano_height = int(pano_width / 2)

    pano = Image.new("RGB", (pano_width, pano_height))
    print(f"Total tiles to process: {total_tiles}")

    bar = progressbar.ProgressBar(max_value=total_tiles)

    async with aiohttp.ClientSession() as session:
        tasks = []
        for x in range(x_range):
            for y in range(y_range):
                tile_url = f"https://pano.maps.yandex.net/{image_id}/{zoom}.{x}.{y}"
                tasks.append(fetch_tile(session, tile_url))

        results = await asyncio.gather(*tasks)

        tile_index = 0
        for x in range(x_range):
            for y in range(y_range):
                tile = results[tile_index]
                tile_index += 1
                if tile:
                    pano.paste(tile, (x * tile_width, y * tile_height))
                    bar.update(bar.value + 1)

    pano.save(filename)
    print(f"Panorama saved as {filename}")

def parse_args():
    from argparse import ArgumentParser

    parser = ArgumentParser(description="Download and assemble a Yandex panorama.")
    parser.add_argument("-c", "--coordinates", required=True, help="Coordinates in the format 'latitude,longitude'")
    parser.add_argument("-z", "--zoom", type=int, default=0, help="Zoom level (default: 0)")
    parser.add_argument("-o", "--output", default="pano.jpg", help="Output file name (default: pano.jpg)")
    parser.add_argument("-a", "--auto-height", action="store_true", help="Automatically adjust panorama height")

    return parser.parse_args()

def main() -> None:
    args = parse_args()

    try:
        lat, lon = map(float, args.coordinates.split(","))
    except ValueError:
        print("Invalid coordinates. Please provide in the format 'latitude,longitude'")
        sys.exit(1)

    api_url = (
        f"https://api-maps.yandex.ru/services/panoramas/1.x/?l=stv&lang=ru_RU&ll="
        f"{lon},{lat}&origin=userAction&provider=streetview"
    )

    data = fetch_and_process_json(api_url)
    if not data:
        sys.exit(1)

    try:
        images = data["data"]["Data"]["Images"]
        image_id = images["imageId"]
        tile_width = images["Tiles"]["width"]
        tile_height = images["Tiles"]["height"]
        zoom_data = images["Zooms"][args.zoom]
        pano_width = zoom_data["width"]
        pano_height = zoom_data["height"]
    except (KeyError, IndexError, TypeError):
        print("Invalid panorama data or zoom level not available.")
        sys.exit(1)

    if platform.system() == "Windows":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy()) # to work properly on windows

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(
            make_pano(image_id, pano_width, pano_height, tile_width, tile_height, args.auto_height, args.zoom, args.output)
        )
    finally:
        loop.close()

if __name__ == "__main__":
    main()
