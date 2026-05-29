"""Thin wrapper around the Instagram Graph API.

Only the pieces we need to forward posts:

- ``fetch_recent_media`` — list recent media for a Business/Creator account.
- ``get_username`` — resolve the account's @handle (used for nicer labels).
- ``refresh_long_lived_token`` — extend a long-lived token's 60-day lifetime.

These map to documented Graph API endpoints:
https://developers.facebook.com/docs/instagram-api/reference/ig-user/media
https://developers.facebook.com/docs/instagram-platform/long-lived-access-tokens
"""

from __future__ import annotations

import logging
from typing import Any

import requests

log = logging.getLogger(__name__)

GRAPH_BASE = "https://graph.facebook.com/v23.0"
GRAPH_INSTAGRAM = "https://graph.instagram.com"

# Fields we ask Instagram for on each media item. caption/permalink/media_url
# are what we render into the Discord message.
MEDIA_FIELDS = (
    "id,caption,media_type,media_url,thumbnail_url,permalink,timestamp,username"
)


class InstagramError(RuntimeError):
    """Raised when the Graph API returns an error or is unreachable."""


def _get(url: str, params: dict[str, Any], timeout: int = 20) -> dict[str, Any]:
    try:
        resp = requests.get(url, params=params, timeout=timeout)
    except requests.RequestException as exc:
        raise InstagramError(f"network error talking to Instagram: {exc}") from exc

    try:
        payload = resp.json()
    except ValueError:
        raise InstagramError(
            f"non-JSON response from Instagram (HTTP {resp.status_code})"
        )

    if resp.status_code >= 400 or "error" in payload:
        err = payload.get("error", {})
        msg = err.get("message", f"HTTP {resp.status_code}")
        raise InstagramError(f"Instagram API error: {msg}")
    return payload


def fetch_recent_media(
    ig_user_id: str, access_token: str, limit: int = 10
) -> list[dict[str, Any]]:
    """Return up to ``limit`` recent media items, newest first.

    Each item is a dict with the keys listed in ``MEDIA_FIELDS``.
    """
    url = f"{GRAPH_BASE}/{ig_user_id}/media"
    params = {
        "fields": MEDIA_FIELDS,
        "limit": limit,
        "access_token": access_token,
    }
    data = _get(url, params)
    return data.get("data", [])


def get_username(ig_user_id: str, access_token: str) -> str:
    """Resolve the @username for an account, or '' if it can't be fetched."""
    url = f"{GRAPH_BASE}/{ig_user_id}"
    try:
        data = _get(url, {"fields": "username", "access_token": access_token})
    except InstagramError as exc:
        log.warning("could not resolve username for %s: %s", ig_user_id, exc)
        return ""
    return data.get("username", "")


def refresh_long_lived_token(access_token: str) -> dict[str, Any]:
    """Refresh a long-lived token, returning the new token + expiry seconds.

    Returns a dict like ``{"access_token": "...", "expires_in": 5183944}``.
    Long-lived tokens must be at least 24 hours old to be refreshable.
    """
    url = f"{GRAPH_INSTAGRAM}/refresh_access_token"
    params = {
        "grant_type": "ig_refresh_token",
        "access_token": access_token,
    }
    return _get(url, params)
