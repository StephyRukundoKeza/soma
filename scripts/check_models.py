import os
import time

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

MODELS = ["gemini-3.8-flash", "gemini-3.7-flash", "gemini-3.6-flash",
          "gemini-3.5-flash", "gemini-3.5-flash-lite"]

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"],
                      http_options=types.HttpOptions(timeout=20000))

for model in MODELS:
    start = time.time()
    try:
        reply = client.models.generate_content(model=model, contents="Say hello in Kinyarwanda.")
        print(f"{model}: OK in {time.time() - start:.1f} s | {(reply.text or '').strip()[:40]}")
    except Exception as error:
        print(f"{model}: FAILED after {time.time() - start:.1f} s | {str(error)[:70]}")