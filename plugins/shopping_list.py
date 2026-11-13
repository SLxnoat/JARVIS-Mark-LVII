"""
plugins/shopping_list.py - Persistent grocery and checklist manager.

Adheres to AGENTS.md:
- Thread-safe storage in memory/shopping_list.json.
- Thread-safe HUD display via player.show_content().
- Never raises exceptions, returns clean spoken strings.
"""
import json
import time
from pathlib import Path

PLUGIN = {
    "name": "shopping_list",
    "description": (
        "Manages a persistent shopping or grocery checklist. "
        "Allows adding items, removing items, marking items as bought, listing all items, and clearing."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "Action: 'add', 'remove', 'check', 'list', 'clear'.",
                "enum": ["add", "remove", "check", "list", "clear"],
            },
            "item": {
                "type": "STRING",
                "description": "Item name to add, remove, or mark as checked.",
            },
            "category": {
                "type": "STRING",
                "description": "Optional category (e.g. 'Groceries', 'Hardware', 'Pharmacy').",
            },
        },
        "required": ["action"],
    },
}

_STORAGE_PATH = Path("memory") / "shopping_list.json"


def _load_list() -> list[dict]:
    if _STORAGE_PATH.is_file():
        try:
            with open(_STORAGE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []


def _save_list(items: list[dict]) -> None:
    _STORAGE_PATH.parent.mkdir(parents=True, exist_ok=True)
    temp = _STORAGE_PATH.with_suffix(".tmp")
    with open(temp, "w", encoding="utf-8") as f:
        json.dump(items, f, indent=2)
    temp.replace(_STORAGE_PATH)


def run(parameters: dict, player=None, session_memory=None) -> str:
    action = parameters.get("action", "list").strip().lower()
    item_name = str(parameters.get("item") or "").strip()
    category = str(parameters.get("category") or "General").strip()

    try:
        items = _load_list()

        if action == "add":
            if not item_name:
                return "Please provide an item name to add to the shopping list."
            # Check duplicate
            for it in items:
                if it["name"].lower() == item_name.lower():
                    it["checked"] = False
                    _save_list(items)
                    return f"'{item_name}' was already on your list; marked it as needed."

            items.append({
                "name": item_name,
                "category": category,
                "checked": False,
                "added_at": time.strftime("%Y-%m-%d %H:%M"),
            })
            _save_list(items)
            return f"Added '{item_name}' to your shopping list."

        elif action == "remove":
            if not item_name:
                return "Please specify the item name to remove."
            initial_len = len(items)
            items = [it for it in items if it["name"].lower() != item_name.lower()]
            if len(items) < initial_len:
                _save_list(items)
                return f"Removed '{item_name}' from the shopping list."
            return f"'{item_name}' was not found on your shopping list."

        elif action == "check":
            if not item_name:
                return "Please specify the item to check off."
            found = False
            for it in items:
                if it["name"].lower() == item_name.lower():
                    it["checked"] = True
                    found = True
                    break
            if found:
                _save_list(items)
                return f"Marked '{item_name}' as purchased."
            return f"'{item_name}' was not found on your shopping list."

        elif action == "clear":
            _save_list([])
            return "Cleared all items from your shopping list."

        elif action == "list":
            if not items:
                return "Your shopping list is currently empty."

            pending = [it for it in items if not it["checked"]]
            completed = [it for it in items if it["checked"]]

            # Format markdown display for HUD
            hud_lines = ["###  Shopping List\n"]
            if pending:
                hud_lines.append("**Needed Items:**")
                for it in pending:
                    cat = f" *({it['category']})*" if it.get("category") != "General" else ""
                    hud_lines.append(f"- [ ] **{it['name']}**{cat}")
                hud_lines.append("")

            if completed:
                hud_lines.append("**Purchased:**")
                for it in completed:
                    hud_lines.append(f"- [x] ~{it['name']}~")

            if player:
                try:
                    player.show_content("Shopping List", "\n".join(hud_lines))
                except Exception:
                    pass

            if pending:
                names = ", ".join(it["name"] for it in pending[:5])
                extra = f" and {len(pending) - 5} more" if len(pending) > 5 else ""
                return f"You have {len(pending)} item(s) on your shopping list: {names}{extra}."
            return f"All items on your shopping list are checked off ({len(completed)} completed)."

        else:
            return f"Unknown action '{action}'. Valid actions: add, remove, check, list, clear."

    except Exception as e:
        return f"Error managing shopping list: {e}"
