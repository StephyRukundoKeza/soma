"""Download Digital Umuganda's Kinyarwanda speech model once (about 1 GB), then test it.

    python scripts/download_speech_model.py
"""

import os
import sys
from pathlib import Path

os.environ["HF_HUB_OFFLINE"] = "0"          # allow the download just for this script
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src" / "soma"))

import numpy as np  # noqa: E402

import speech  # noqa: E402


def main():
    print(f"Downloading {speech.KINYARWANDA_MODEL} (about 1 GB, only the first time)...")
    pipe = speech.kinyarwanda_pipeline()
    silence = np.zeros(16000, dtype=np.float32)
    pipe({"raw": silence, "sampling_rate": 16000})
    print("Ready: Kinyarwanda recordings will now be transcribed on this computer.")


if __name__ == "__main__":
    main()
