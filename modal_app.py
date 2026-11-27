"""SOMA on Modal (free Starter plan): the same app as on the laptop, with both models built in.

    pip install modal
    modal setup                  # once: log in with GitHub in the browser
    modal deploy modal_app.py    # prints the live https link

The ready-made index (data/processed) is copied from this computer into the private Modal image.
The two models are public and downloaded while the image is built; no Hugging Face account is needed.
Keys are read from .env at deploy time and stored as a Modal secret (only the ones SOMA needs).
The container sleeps after 2 idle minutes, so free credits are only used while someone is practising.
"""

from pathlib import Path

import modal
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parent
APP_DIR = "/root/soma"
MODELS = ["intfloat/multilingual-e5-base", "DigitalUmuganda/whisper_small_kinyarwanda"]
KEYS = ["GEMINI_API_KEY", "GEMINI_MODELS", "GEMINI_TIMEOUT_MS", "SUPABASE_URL", "SUPABASE_PUBLISHABLE_KEY",
        "SUPABASE_SECRET_KEY", "SOMA_SESSION_MINUTES"]

# Checked only on this computer: inside Modal's containers the files are added by the image
if modal.is_local() and not (ROOT / "data" / "processed" / "chunks.json").exists():
    raise SystemExit("data/processed is missing: build the index first (see README).")


def download_models():
    """Runs once while the image is built, so waking up never re-downloads the models."""
    from huggingface_hub import snapshot_download

    for model in MODELS:
        snapshot_download(model)


# Keys are read from .env on this computer only; inside Modal they come from the stored secret
env = dotenv_values(ROOT / ".env") if modal.is_local() else {}
secret = modal.Secret.from_dict({key: env[key] for key in KEYS if env.get(key)})

image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install("torch", index_url="https://download.pytorch.org/whl/cpu")
    .pip_install_from_requirements(str(ROOT / "requirements-server.txt"))
    .env({"HF_HOME": "/root/hf", "PYTHONUNBUFFERED": "1"})
    .run_function(download_models)
    .env({"HF_HUB_OFFLINE": "1"})                       # everything is already inside the image
    .add_local_file(ROOT / "data" / "processed" / "chunks.json", f"{APP_DIR}/data/processed/chunks.json")
    .add_local_file(ROOT / "data" / "processed" / "embeddings_e5.npy", f"{APP_DIR}/data/processed/embeddings_e5.npy")
    .add_local_file(ROOT / "data" / "processed" / "index_info_e5.json", f"{APP_DIR}/data/processed/index_info_e5.json")
    .add_local_file(ROOT / "app.py", f"{APP_DIR}/app.py")
    .add_local_dir(ROOT / "src", f"{APP_DIR}/src", ignore=["**/__pycache__"])
    .add_local_dir(ROOT / "web", f"{APP_DIR}/web")
)

app = modal.App("soma", image=image)


@app.function(secrets=[secret], cpu=1.0, memory=4096, timeout=600, scaledown_window=120)
@modal.concurrent(max_inputs=20)
@modal.asgi_app()
def web():
    import importlib
    import os
    import sys

    os.chdir(APP_DIR)
    sys.path.insert(0, APP_DIR)
    return importlib.import_module("app").app
