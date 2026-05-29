"""Background worker: poll Instagram, forward new posts to Discord.

Runs in a daemon thread started by the web app. On each cycle it walks every
enabled feed, fetches recent media, and forwards any media IDs it hasn't seen
before. It also refreshes long-lived tokens that are nearing expiry.

Design notes:
- "Seen" IDs are tracked per-feed in ``state.json`` so a restart never
  re-posts old content and never floods a channel.
- The very first time a feed is polled we record its current media as "seen"
  WITHOUT forwarding, so wiring up a new feed doesn't dump the back-catalogue
  into the channel. Only posts created after setup get forwarded.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any

from . import discord, instagram, store

log = logging.getLogger(__name__)

# Refresh a token once it's within this many seconds of expiry (~7 days).
_TOKEN_REFRESH_THRESHOLD = 7 * 24 * 3600
# Long-lived tokens last ~60 days; assume that if we don't know the expiry.
_DEFAULT_TOKEN_TTL = 60 * 24 * 3600


class Poller:
    def __init__(self) -> None:
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        # Lets the GUI trigger an immediate poll after a config change.
        self._wake = threading.Event()

    # -- lifecycle ---------------------------------------------------------
    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="poller", daemon=True)
        self._thread.start()
        log.info("poller thread started")

    def stop(self) -> None:
        self._stop.set()
        self._wake.set()

    def trigger(self) -> None:
        """Ask the poller to run a cycle now instead of waiting for the timer."""
        self._wake.set()

    # -- main loop ---------------------------------------------------------
    def _run(self) -> None:
        while not self._stop.is_set():
            interval = 300
            try:
                config = store.load_config()
                interval = max(60, config.poll_interval_seconds)
                self.poll_once(config)
            except Exception:  # never let the loop die on a transient error
                log.exception("unexpected error during poll cycle")

            # Sleep until the interval elapses or someone wakes us.
            self._wake.wait(timeout=interval)
            self._wake.clear()

    # -- one cycle (also callable directly, e.g. from tests/CLI) -----------
    def poll_once(self, config: store.Config | None = None) -> int:
        """Run a single poll over all enabled feeds. Returns # posts forwarded."""
        if config is None:
            config = store.load_config()
        state = store.load_state()
        state.setdefault("seen", {})
        state.setdefault("tokens", {})

        forwarded = 0
        for feed in config.feeds:
            if not feed.enabled:
                continue
            try:
                forwarded += self._process_feed(feed, state)
            except Exception:
                log.exception("error processing feed %s (%s)", feed.id, feed.name)

        store.save_state(state)
        return forwarded

    def _process_feed(self, feed: store.Feed, state: dict[str, Any]) -> int:
        self._maybe_refresh_token(feed, state)

        media_items = instagram.fetch_recent_media(feed.ig_user_id, feed.access_token)
        seen: list[str] = state["seen"].setdefault(feed.id, [])
        seen_set = set(seen)

        # First run for this feed: baseline the current posts, forward nothing.
        if not seen:
            state["seen"][feed.id] = [m["id"] for m in media_items]
            log.info(
                "baselined feed %s with %d existing posts (none forwarded)",
                feed.name,
                len(media_items),
            )
            return 0

        # API returns newest-first; reverse so we post oldest-new first, keeping
        # chronological order in the Discord channel.
        forwarded = 0
        for media in reversed(media_items):
            if media["id"] in seen_set:
                continue
            try:
                discord.send_media(feed.discord_webhook_url, media)
            except discord.DiscordError as exc:
                # Leave it unseen so we retry next cycle rather than losing it.
                log.error("failed to forward %s to Discord: %s", media["id"], exc)
                continue
            seen.append(media["id"])
            seen_set.add(media["id"])
            forwarded += 1
            log.info("forwarded post %s from %s", media["id"], feed.name)

        # Cap the seen-list so it can't grow without bound.
        if len(seen) > 500:
            state["seen"][feed.id] = seen[-500:]
        return forwarded

    def _maybe_refresh_token(self, feed: store.Feed, state: dict[str, Any]) -> None:
        """Refresh the feed's long-lived token if it's close to expiring."""
        info = state["tokens"].get(feed.id, {})
        now = time.time()
        expires_at = info.get("expires_at", now + _DEFAULT_TOKEN_TTL)

        if expires_at - now > _TOKEN_REFRESH_THRESHOLD:
            return

        try:
            result = instagram.refresh_long_lived_token(feed.access_token)
        except instagram.InstagramError as exc:
            log.warning("token refresh failed for %s: %s", feed.name, exc)
            return

        new_token = result.get("access_token")
        if not new_token:
            return

        # Persist the new token back into the config so it survives restarts.
        config = store.load_config()
        for f in config.feeds:
            if f.id == feed.id:
                f.access_token = new_token
                break
        store.save_config(config)
        feed.access_token = new_token

        ttl = int(result.get("expires_in", _DEFAULT_TOKEN_TTL))
        state["tokens"][feed.id] = {"expires_at": now + ttl}
        log.info("refreshed token for %s (valid ~%d days)", feed.name, ttl // 86400)


# Module-level singleton the web app starts and shares.
poller = Poller()
