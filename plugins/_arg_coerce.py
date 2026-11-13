"""Shared arg-coercion helper — import in any plugin's run() or loader for safe type normalisation.

Usage:
    from plugins._arg_coerce import coerce_params
    parameters = coerce_params(parameters)
"""

def _coerce(value):
    """Coerce a single value: strings that look like bools/ints/floats/None become the right type."""
    if not isinstance(value, str):
        return value
    v = value.strip()
    if v.lower() == "true":
        return True
    if v.lower() == "false":
        return False
    if v.lower() in ("null", "none"):
        return None
    try:
        return int(v)
    except ValueError:
        pass
    try:
        return float(v)
    except ValueError:
        pass
    return value

def coerce_params(parameters: dict) -> dict:
    """Return a new dict with all string values coerced to their natural types."""
    return {k: _coerce(v) for k, v in (parameters or {}).items()}
