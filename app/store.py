"""Persistent JSON storage for configuration and runtime state.

Two files live next to the project root:

- ``config.json`` holds user-editable settings: the poll interval and the list
  of "feeds" (an Instagram account + access token mapped to a Discord webhook).
- ``state.json`` holds runtime bookkeeping: which media IDs we have already
  forwarded, and when each token was last refreshed.

Both are plain JSON so they are easy to inspect and back up. Access is guarded
by a re-entrant lock because the web GUI and the poller thread touch them
concurrently.
"""

from __future__ import annotations

import json
import os
import threading
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any

# Files are resolved relative to the repo root (the parent of this package),
# unless overridden via env vars — handy for tests and alternate deployments.
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.environ.get("I2D_CONFIG", os.path.join(_ROOT, "config.json"))
STATE_PATH = os.environ.get("I2D_STATE", os.path.join(_ROOT, "state.json"))

_lock = threading.RLock()


@dataclass
class Feed:
    """A single Instagram-account -> Discord-channel forwarding rule."""

    id: str
    name: str  # human label shown in the GUI, e.g. "@mybrand -> #announcements"
    ig_user_id: str  # Instagram Business/Creator account ID (numeric string)
    access_token: str  # long-lived user access token
    discord_webhook_url: str
    enabled: bool = True
    # Mirror the @username so the GUI can show it without an API round-trip.
    ig_username: str = ""

    @staticmethod
    def new(**kwargs: Any) -> "Feed":
        return Feed(id=uuid.uuid4().hex[:12], **kwargs)


@dataclass
class Config:
    poll_interval_seconds: int = 300  # 5 minutes; Graph API rate limits are generous
    feeds: list[Feed] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "poll_interval_seconds": self.poll_interval_seconds,
            "feeds": [asdict(f) for f in self.feeds],
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "Config":
        return Config(
            poll_interval_seconds=int(data.get("poll_interval_seconds", 300)),
            feeds=[Feed(**f) for f in data.get("feeds", [])],
        )


def _read_json(path: str, default: Any) -> Any:
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _write_json(path: str, data: Any) -> None:
    # Write to a temp file then rename so a crash mid-write can't corrupt the
    # real file (rename is atomic on POSIX).
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
    os.replace(tmp, path)


def load_config() -> Config:
    with _lock:
        return Config.from_dict(_read_json(CONFIG_PATH, {}))


def save_config(config: Config) -> None:
    with _lock:
        _write_json(CONFIG_PATH, config.to_dict())


def load_state() -> dict[str, Any]:
    with _lock:
        return _read_json(STATE_PATH, {"seen": {}, "tokens": {}})


def save_state(state: dict[str, Any]) -> None:
    with _lock:
        _write_json(STATE_PATH, state)
