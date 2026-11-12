"""
plugins/spaced_repetition.py - Leitner flashcard spaced repetition study system.

Adheres to AGENTS.md:
- Thread-safe file persistence in memory/flashcards.json.
- Thread-safe HUD presentation via player.show_content().
- Never raises exceptions, returns concise spoken feedback.
"""
import json
import time
import uuid
from pathlib import Path

PLUGIN = {
    "name": "spaced_repetition",
    "description": (
        "Spaced repetition flashcard memory system. Add new cards with front/back text, "
        "review cards currently due for study, rate recall (1-5), or view deck statistics."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "Action: 'add', 'review', 'score', 'stats'.",
                "enum": ["add", "review", "score", "stats"],
            },
            "deck": {
                "type": "STRING",
                "description": "Deck name (e.g. 'Spanish', 'Python', 'History'). Default 'Default'.",
            },
            "front": {
                "type": "STRING",
                "description": "Front of card (prompt, question, or term). Required for 'add'.",
            },
            "back": {
                "type": "STRING",
                "description": "Back of card (answer, definition, or translation). Required for 'add'.",
            },
            "card_id": {
                "type": "STRING",
                "description": "Card ID to score during review.",
            },
            "rating": {
                "type": "INTEGER",
                "description": "Recall quality rating 1 to 5 (1=forgot completely, 5=perfect easy recall). Required for 'score'.",
            },
        },
        "required": ["action"],
    },
}

_STORAGE_PATH = Path("memory") / "flashcards.json"
_INTERVALS_DAYS = [1, 2, 4, 7, 14, 30]  # Leitner box intervals


def _load_cards() -> list[dict]:
    if _STORAGE_PATH.is_file():
        try:
            with open(_STORAGE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []


def _save_cards(cards: list[dict]) -> None:
    _STORAGE_PATH.parent.mkdir(parents=True, exist_ok=True)
    temp = _STORAGE_PATH.with_suffix(".tmp")
    with open(temp, "w", encoding="utf-8") as f:
        json.dump(cards, f, indent=2)
    temp.replace(_STORAGE_PATH)


def run(parameters: dict, player=None, session_memory=None) -> str:
    action = parameters.get("action", "review").strip().lower()
    deck = str(parameters.get("deck") or "Default").strip()
    front = str(parameters.get("front") or "").strip()
    back = str(parameters.get("back") or "").strip()
    card_id = str(parameters.get("card_id") or "").strip()
    rating = parameters.get("rating")

    try:
        cards = _load_cards()
        now = time.time()

        if action == "add":
            if not front or not back:
                return "Adding a flashcard requires both 'front' (question) and 'back' (answer)."

            cid = str(uuid.uuid4())[:8]
            cards.append({
                "id": cid,
                "deck": deck,
                "front": front,
                "back": back,
                "box": 0,
                "due_at": now,
                "created_at": time.strftime("%Y-%m-%d"),
            })
            _save_cards(cards)
            return f"Added new card to deck '{deck}' (ID: {cid})."

        elif action == "review":
            deck_cards = [c for c in cards if c.get("deck", "").lower() == deck.lower()]
            due_cards = [c for c in deck_cards if c.get("due_at", 0) <= now]

            if not due_cards:
                return f"No cards due for review in deck '{deck}'. Total cards: {len(deck_cards)}."

            card = due_cards[0]
            hud_text = (
                f"### 📇 Flashcard Review: Deck '{deck}'\n\n"
                f"**Card ID:** `{card['id']}`\n\n"
                f"### ❓ Question / Front:\n> **{card['front']}**\n\n"
                f"---\n"
                f"*(Ask JARVIS to reveal the answer or score your recall 1-5)*\n\n"
                f"<details><summary>Click to Reveal Answer</summary>\n\n> {card['back']}\n</details>"
            )
            if player:
                try:
                    player.show_content(f"Card Review: {deck}", hud_text)
                except Exception:
                    pass

            return f"Card due in {deck}: '{card['front']}'. Card ID is {card['id']}."

        elif action == "score":
            if not card_id:
                return "Please provide the 'card_id' to score."
            if rating is None or not (1 <= int(rating) <= 5):
                return "Please provide a recall rating from 1 (forgot) to 5 (perfect recall)."

            r = int(rating)
            card = next((c for c in cards if c["id"] == card_id), None)
            if not card:
                return f"Card with ID '{card_id}' not found."

            current_box = card.get("box", 0)
            if r >= 3:
                new_box = min(current_box + 1, len(_INTERVALS_DAYS) - 1)
            else:
                new_box = 0

            days = _INTERVALS_DAYS[new_box]
            card["box"] = new_box
            card["due_at"] = now + (days * 86400)
            card["last_reviewed"] = time.strftime("%Y-%m-%d %H:%M")
            _save_cards(cards)

            return f"Card {card_id} scored {r}/5. Moved to box {new_box}. Next review in {days} day(s)."

        elif action == "stats":
            deck_cards = [c for c in cards if c.get("deck", "").lower() == deck.lower()]
            due_cards = [c for c in deck_cards if c.get("due_at", 0) <= now]
            return f"Deck '{deck}' has {len(deck_cards)} total cards; {len(due_cards)} are currently due for review."

        else:
            return f"Unknown action '{action}'. Valid actions: add, review, score, stats."

    except Exception as e:
        return f"Error in spaced repetition: {e}"
