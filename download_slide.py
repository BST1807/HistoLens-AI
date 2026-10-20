import os
import sys
import requests

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
os.makedirs(DATA_DIR, exist_ok=True)

SLIDE_PATH = os.path.join(DATA_DIR, "CMU-1-Small-Region.svs")

URLS = [
    "https://raw.githubusercontent.com/libvips/libvips/master/test/test-suite/images/CMU-1-Small-Region.svs",
    "https://huggingface.co/datasets/TIACentre/TIAToolBox_Remote_Samples/resolve/main/sample_wsis/CMU-1-Small-Region.svs"
]

def download_slide():
    if os.path.exists(SLIDE_PATH) and os.path.getsize(SLIDE_PATH) > 1_000_000:
        print(f"Slide already exists at {SLIDE_PATH} ({os.path.getsize(SLIDE_PATH) / 1024 / 1024:.2f} MB)")
        return SLIDE_PATH

    print("Downloading authentic sample Whole Slide Image (CMU-1-Small-Region.svs)...")
    for url in URLS:
        try:
            print(f"Fetching from {url}...")
            response = requests.get(url, stream=True, timeout=30)
            if response.status_code == 200:
                with open(SLIDE_PATH, "wb") as f:
                    for chunk in response.iter_content(chunk_size=65536):
                        if chunk:
                            f.write(chunk)
                size_mb = os.path.getsize(SLIDE_PATH) / (1024 * 1024)
                print(f"Successfully downloaded to {SLIDE_PATH} ({size_mb:.2f} MB)")
                return SLIDE_PATH
            else:
                print(f"Status code {response.status_code}, trying next source...")
        except Exception as e:
            print(f"Failed with {url}: {e}, trying next...")

    print("Could not download external SVS. Will generate high-resolution histology sample...")
    return None

if __name__ == "__main__":
    download_slide()
