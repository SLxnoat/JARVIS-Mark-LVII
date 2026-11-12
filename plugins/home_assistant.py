"""
plugins/home_assistant.py - Home Assistant smart home integration.

Adheres to AGENTS.md:
- Thread-safe REST operations with httpx.
- Never raises exceptions, returns concise spoken feedback.
- Reads configuration from config/api_keys.json via memory.config_manager.
"""
import os
import httpx
from memory.config_manager import get_plugin_config

PLUGIN = {
    "name": "home_assistant",
    "description": (
        "Controls smart home devices via Home Assistant. "
        "Allows listing entities, querying entity states, and turning on/off/toggling lights and switches."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "Action: 'get_state', 'turn_on', 'turn_off', 'toggle', 'list_entities'.",
                "enum": ["get_state", "turn_on", "turn_off", "toggle", "list_entities"],
            },
            "entity_id": {
                "type": "STRING",
                "description": "Entity ID (e.g. 'light.living_room', 'switch.desk_lamp'). Required for control.",
            },
            "domain": {
                "type": "STRING",
                "description": "Optional domain filter for listing entities (e.g. 'light', 'switch', 'climate').",
            },
        },
        "required": [],
    },
    "PLUGIN_SETTINGS": {
        "fields": [
            {"key": "url", "label": "Home Assistant URL", "type": "string", "default": "http://homeassistant.local:8123"},
            {"key": "token", "label": "Long-Lived Access Token", "type": "password"},
        ]
    },
}


def _get_connection():
    cfg = get_plugin_config("home_assistant") or {}
    url = cfg.get("url") or os.environ.get("HASS_URL") or "http://homeassistant.local:8123"
    token = cfg.get("token") or os.environ.get("HASS_TOKEN")
    return url.rstrip("/"), token


def run(parameters: dict, player=None, session_memory=None) -> str:
    raw_action = str(parameters.get("action") or parameters.get("mode") or "list_entities").strip().lower()
    if raw_action in ("list", "list_entities", "entities"):
        action = "list_entities"
    elif raw_action in ("state", "get_state", "status", "query"):
        action = "get_state"
    else:
        action = raw_action

    entity_id = str(parameters.get("entity_id") or parameters.get("entity") or "").strip()
    domain = str(parameters.get("domain") or "").strip().lower()

    base_url, token = _get_connection()
    if not token:
        return (
            "Home Assistant is not yet configured. Please set your Long-Lived Access Token "
            "in settings or HASS_TOKEN environment variable."
        )

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    try:
        with httpx.Client(timeout=8.0) as client:
            if action == "list_entities":
                resp = client.get(f"{base_url}/api/states", headers=headers)
                if resp.status_code != 200:
                    return f"Home Assistant returned error {resp.status_code}."
                states = resp.json()
                if domain:
                    states = [s for s in states if s["entity_id"].startswith(f"{domain}.")]

                summary = []
                for s in states[:15]:
                    name = s.get("attributes", {}).get("friendly_name") or s["entity_id"]
                    summary.append(f"- **{name}** (`{s['entity_id']}`): `{s['state']}`")

                if player:
                    try:
                        md = f"### 🏠 Home Assistant Entities ({domain or 'all'})\n\n" + "\n".join(summary)
                        player.show_content("Home Assistant", md)
                    except Exception:
                        pass

                return f"Found {len(states)} device(s) in Home Assistant. Showing states on HUD."

            elif action == "get_state":
                if not entity_id:
                    return "Please provide an entity_id to inspect."
                resp = client.get(f"{base_url}/api/states/{entity_id}", headers=headers)
                if resp.status_code == 404:
                    return f"Device '{entity_id}' not found in Home Assistant."
                elif resp.status_code != 200:
                    return f"Home Assistant error {resp.status_code}."

                state_obj = resp.json()
                curr_state = state_obj.get("state", "unknown")
                friendly = state_obj.get("attributes", {}).get("friendly_name", entity_id)
                return f"{friendly} is currently {curr_state}."

            elif action in ("turn_on", "turn_off", "toggle"):
                if not entity_id:
                    return f"Please provide an entity_id to {action}."

                dev_domain = entity_id.split(".")[0] if "." in entity_id else "homeassistant"
                svc_url = f"{base_url}/api/services/{dev_domain}/{action}"
                payload = {"entity_id": entity_id}

                resp = client.post(svc_url, headers=headers, json=payload)
                if resp.status_code in (200, 201):
                    verb = {"turn_on": "turned on", "turn_off": "turned off", "toggle": "toggled"}.get(action, action)
                    if player:
                        try:
                            player.write_log(f"🏠 [HomeAssistant] {verb.capitalize()} {entity_id}")
                        except Exception:
                            pass
                    return f"Successfully {verb} {entity_id}."
                else:
                    return f"Failed to {action} {entity_id} (HTTP {resp.status_code})."

            else:
                return f"Unknown action '{action}'. Valid actions: list_entities, get_state, turn_on, turn_off, toggle."

    except httpx.ConnectError:
        return f"Could not connect to Home Assistant at {base_url}. Is the server online and reachable?"
    except Exception as e:
        return f"Error communicating with Home Assistant: {e}"
