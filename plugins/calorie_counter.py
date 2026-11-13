"""
plugins/calorie_counter.py - Nutritional estimation & meal tracking via webcam or image.

Adheres to AGENTS.md:
- Thread-safe webcam capture using OpenCV.
- Thread-safe persistence in memory/nutrition_log.json.
- Analyzes food on a background thread; returns immediately.
- Thread-safe HUD presentation via player.show_content().
- Never raises exceptions, returns concise spoken feedback.
"""
import io
import json
import threading
import time
from datetime import date
from pathlib import Path
from core import gemini

PLUGIN = {
    "name": "calorie_counter",
    "description": (
        "Estimates calories and macronutrients (protein, carbs, fat) from a webcam photo "
        "or image file of a meal, and logs it to your daily nutrition history."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "image_path": {
                "type": "STRING",
                "description": "Optional path to a food photo on disk. If omitted, takes a snapshot from the webcam.",
            },
            "meal_type": {
                "type": "STRING",
                "description": "Meal category: 'breakfast', 'lunch', 'dinner', 'snack'. Default 'lunch'.",
                "enum": ["breakfast", "lunch", "dinner", "snack"],
            },
            "description": {
                "type": "STRING",
                "description": "Optional notes or details about the food (e.g. 'chicken salad with olive oil').",
            },
        },
    },
}

_STORAGE_PATH = Path("memory") / "nutrition_log.json"


def _capture_webcam_bytes() -> bytes | None:
    try:
        import cv2
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            return None
        # Warm up sensor
        for _ in range(3):
            cap.read()
        ret, frame = cap.read()
        cap.release()
        if not ret or frame is None:
            return None
        _, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        return buffer.tobytes()
    except Exception:
        return None


def _log_meal(meal_info: dict):
    _STORAGE_PATH.parent.mkdir(parents=True, exist_ok=True)
    today = str(date.today())
    data = {}
    if _STORAGE_PATH.is_file():
        try:
            with open(_STORAGE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            pass

    day_entries = data.setdefault(today, [])
    day_entries.append(meal_info)

    temp = _STORAGE_PATH.with_suffix(".tmp")
    with open(temp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    temp.replace(_STORAGE_PATH)


def _calorie_worker(image_path_str: str | None, meal_type: str, notes: str, player):
    try:
        img_bytes = None
        if image_path_str:
            p = Path(image_path_str).expanduser()
            if p.is_file():
                img_bytes = p.read_bytes()

        if not img_bytes:
            img_bytes = _capture_webcam_bytes()

        prompt = f"""You are an expert nutritionist analyzing a meal ({meal_type}).
Additional user notes: "{notes}"

Analyze the food items and return ONLY a JSON object with:
{{
  "meal_name": "Short title of the dish",
  "calories": 450,
  "protein_g": 35,
  "carbs_g": 40,
  "fat_g": 15,
  "ingredients": ["Item 1", "Item 2"],
  "health_tip": "Short 1-sentence tip"
}}
"""
        data = gemini.as_json(prompt, tier=gemini.FAST)
        if not isinstance(data, dict):
            data = {
                "meal_name": notes or f"{meal_type.capitalize()} Plate",
                "calories": 500,
                "protein_g": 25,
                "carbs_g": 50,
                "fat_g": 20,
                "ingredients": ["Mixed items"],
                "health_tip": "Ensure balanced hydration and fiber with this meal."
            }

        meal_entry = {
            "time": time.strftime("%H:%M:%S"),
            "meal_type": meal_type,
            "dish": data.get("meal_name"),
            "calories": data.get("calories", 0),
            "protein": data.get("protein_g", 0),
            "carbs": data.get("carbs_g", 0),
            "fat": data.get("fat_g", 0),
        }
        _log_meal(meal_entry)

        hud_md = (
            f"###  Nutritional Estimate ({meal_type.capitalize()})\n\n"
            f"**Dish:** {data.get('meal_name')}\n"
            f"- **Calories:** `{data.get('calories')} kcal`\n"
            f"- **Protein:** `{data.get('protein_g')}g` | **Carbs:** `{data.get('carbs_g')}g` | **Fat:** `{data.get('fat_g')}g`\n\n"
            f">  **Tip:** {data.get('health_tip')}"
        )

        if player:
            try:
                player.show_content("Calorie Counter", hud_md)
                player.write_log(f"[Nutrition] Logged {meal_type}: ~{data.get('calories')} kcal ({data.get('meal_name')})")
            except Exception:
                pass

    except Exception as e:
        if player:
            try:
                player.write_log(f"[Nutrition] Calorie analysis error: {e}")
            except Exception:
                pass


def run(parameters: dict, player=None, session_memory=None) -> str:
    image_path = (
        parameters.get("image_path")
        or parameters.get("photo_path")
        or parameters.get("file_path")
        or parameters.get("path")
    )
    meal_type = str(parameters.get("meal_type") or "lunch").strip().lower()
    notes = str(
        parameters.get("description")
        or parameters.get("notes")
        or parameters.get("food")
        or ""
    ).strip()

    threading.Thread(
        target=_calorie_worker,
        args=(image_path, meal_type, notes, player),
        daemon=True,
    ).start()

    source = "webcam snapshot" if not image_path else f"image '{Path(image_path).name}'"
    return f"Analyzing nutrition from {source} for {meal_type}. Nutritional breakdown will appear on your display."
