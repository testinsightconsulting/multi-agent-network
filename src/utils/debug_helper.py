"""Debug helper for Concierge→Specialist flow. Set TOPOLOGY_DEBUG=1 to enable."""
import os


def is_debug() -> bool:
    """True when TOPOLOGY_DEBUG is set to 1, true, or yes."""
    return os.environ.get("TOPOLOGY_DEBUG", "").strip().lower() in ("1", "true", "yes")


def debug(msg: str, **kwargs) -> None:
    """Print when TOPOLOGY_DEBUG=1. Use for stepping through Concierge→Specialist calls."""
    if is_debug():
        extra = " ".join(f"{k}={v!r}" for k, v in kwargs.items()) if kwargs else ""
        print(f"[Concierge→Specialist] {msg}" + (f" {extra}" if extra else ""))
