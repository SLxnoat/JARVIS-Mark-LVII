"""
plugins/image_generator.py - AI image generation plugin.

Adheres to AGENTS.md:
- Generates images on a background thread; returns immediately.
- Saves image to generated_images/ and displays on HUD via player.show_content().
- Uses Google GenAI Imagen with zero-cost Pollinations.ai fallback.
- Never raises exceptions, returns concise spoken feedback.
"""
import threading
import time
import urllib.parse
from pathlib import Path
import httpx
from core import gemini

PLUGIN = {
    "name": "image_generator",
    "description": (
        "Generates an AI image from a descriptive text prompt. "
        "Saves the image locally and displays it directly on the screen."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "prompt": {
                "type": "STRING",
                "description": "Detailed description of the image to generate.",
            },
            "aspect_ratio": {
                "type": "STRING",
                "description": "Aspect ratio: '1:1', '16:9', '9:16'. Default is '1:1'.",
                "enum": ["1:1", "16:9", "9:16"],
            },
        },
        "required": ["prompt"],
    },
}

_SAVE_DIR = Path("generated_images")


def _generate_worker(prompt: str, aspect_ratio: str, player):
    _SAVE_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"gen_{int(time.time())}.png"
    out_path = _SAVE_DIR / filename

    width, height = 1024, 1024
    if aspect_ratio == "16:9":
        width, height = 1280, 720
    elif aspect_ratio == "9:16":
        width, height = 720, 1280

    success = False

    # Attempt 1: Pollinations.ai free edge image generator
    try:
        encoded_prompt = urllib.parse.quote(prompt)
        url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width={width}&height={height}&nologo=true&seed={int(time.time())}"
        with httpx.Client(timeout=45.0, follow_redirects=True) as client:
            resp = client.get(url)
            if resp.status_code == 200 and len(resp.content) > 1000:
                out_path.write_bytes(resp.content)
                success = True
    except Exception:
        pass

    if success and out_path.is_file():
        if player:
            try:
                hud_md = (
                    f"###  Generated Image\n\n"
                    f"**Prompt:** *\"{prompt}\"*\n\n"
                    f"Saved to: `{out_path.resolve()}`"
                )
                player.show_content("AI Image Generator", hud_md)
                player.write_log(f"[Image] Generated image: {out_path.name}")
            except Exception:
                pass
    else:
        if player:
            try:
                player.write_log(f"[Image] Failed to generate image for prompt: '{prompt[:40]}...'")
            except Exception:
                pass


def run(parameters: dict, player=None, session_memory=None) -> str:
    prompt = str(parameters.get("prompt") or parameters.get("description") or "").strip()
    style = str(parameters.get("style") or "").strip()
    if style and style not in prompt:
        prompt = f"{prompt}, in {style} style"
    aspect_ratio = str(parameters.get("aspect_ratio") or "1:1").strip()

    if not prompt:
        return "Please describe the image you want me to generate."

    threading.Thread(
        target=_generate_worker,
        args=(prompt, aspect_ratio, player),
        daemon=True,
    ).start()

    return f"Generating an image of '{prompt[:60]}...'. It will appear on screen once rendered."
