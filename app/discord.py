"""Post Instagram media to a Discord channel via an Incoming Webhook.

Incoming Webhooks need no bot or OAuth: you create one in a channel's settings
(Edit Channel -> Integrations -> Webhooks) and paste the URL into the GUI. We
send a rich embed so the caption, author, image, and a link back to the post
all render nicely.
https://discord.com/developers/docs/resources/webhook#execute-webhook
"""

from __future__ import annotations

import logging
from typing import Any

import requests

log = logging.getLogger(__name__)

# Discord caps embed description length; keep well under it to be safe.
_MAX_DESC = 4000


class DiscordError(RuntimeError):
    pass


def _build_embed(media: dict[str, Any]) -> dict[str, Any]:
    caption = (media.get("caption") or "").strip()
    if len(caption) > _MAX_DESC:
        caption = caption[: _MAX_DESC - 1] + "…"

    username = media.get("username") or "Instagram"
    permalink = media.get("permalink", "")

    embed: dict[str, Any] = {
        "title": f"New post from @{username}",
        "url": permalink,
        "description": caption,
        "color": 0xE1306C,  # Instagram brand pink
        "author": {"name": f"@{username}"},
    }

    # Videos expose a thumbnail_url; images expose media_url. Prefer whichever
    # is a still image so the embed always shows a picture.
    image_url = media.get("thumbnail_url") or media.get("media_url")
    if image_url and media.get("media_type") != "VIDEO":
        embed["image"] = {"url": image_url}
    elif media.get("thumbnail_url"):
        embed["image"] = {"url": media["thumbnail_url"]}

    if media.get("timestamp"):
        embed["timestamp"] = media["timestamp"]

    return embed


def send_media(webhook_url: str, media: dict[str, Any], timeout: int = 20) -> None:
    """Send a single media item to Discord. Raises ``DiscordError`` on failure."""
    payload = {"embeds": [_build_embed(media)]}

    # For videos, also drop the permalink as plain content so Discord unfurls a
    # playable preview (embeds can't play IG video directly).
    if media.get("media_type") == "VIDEO" and media.get("permalink"):
        payload["content"] = media["permalink"]

    try:
        resp = requests.post(webhook_url, json=payload, timeout=timeout)
    except requests.RequestException as exc:
        raise DiscordError(f"network error posting to Discord: {exc}") from exc

    if resp.status_code >= 400:
        raise DiscordError(
            f"Discord webhook returned HTTP {resp.status_code}: {resp.text[:200]}"
        )
