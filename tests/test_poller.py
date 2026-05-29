"""Tests for the poller's core forwarding logic.

We stub out the network-touching modules (instagram, discord) so the tests run
offline and assert the dedupe/baseline behaviour that keeps us from flooding a
channel or re-posting old content.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from unittest import mock

# Point storage at temp files BEFORE importing the package modules.
_tmp = tempfile.mkdtemp()
os.environ["I2D_CONFIG"] = os.path.join(_tmp, "config.json")
os.environ["I2D_STATE"] = os.path.join(_tmp, "state.json")

from app import store  # noqa: E402
from app.poller import Poller  # noqa: E402


def _media(mid: str) -> dict:
    return {
        "id": mid,
        "caption": f"caption {mid}",
        "media_type": "IMAGE",
        "media_url": f"https://example.com/{mid}.jpg",
        "permalink": f"https://instagram.com/p/{mid}",
        "username": "tester",
        "timestamp": "2026-05-29T00:00:00+0000",
    }


class PollerTests(unittest.TestCase):
    def setUp(self):
        # Fresh config/state per test.
        feed = store.Feed.new(
            name="test",
            ig_user_id="123",
            access_token="tok",
            discord_webhook_url="https://discord/webhook",
            ig_username="tester",
        )
        self.feed = feed
        store.save_config(store.Config(poll_interval_seconds=300, feeds=[feed]))
        store.save_state({"seen": {}, "tokens": {}})
        self.poller = Poller()

    def test_first_run_baselines_without_forwarding(self):
        with mock.patch("app.poller.instagram.fetch_recent_media",
                        return_value=[_media("a"), _media("b")]), \
             mock.patch("app.poller.discord.send_media") as send:
            forwarded = self.poller.poll_once()
        self.assertEqual(forwarded, 0)
        send.assert_not_called()
        state = store.load_state()
        self.assertEqual(set(state["seen"][self.feed.id]), {"a", "b"})

    def test_new_post_is_forwarded_once(self):
        # Baseline with one post.
        with mock.patch("app.poller.instagram.fetch_recent_media",
                        return_value=[_media("a")]), \
             mock.patch("app.poller.discord.send_media"):
            self.poller.poll_once()

        # A new post "b" appears (newest-first ordering).
        with mock.patch("app.poller.instagram.fetch_recent_media",
                        return_value=[_media("b"), _media("a")]), \
             mock.patch("app.poller.discord.send_media") as send:
            forwarded = self.poller.poll_once()
        self.assertEqual(forwarded, 1)
        send.assert_called_once()
        # Forwarded media id should be "b".
        self.assertEqual(send.call_args.args[1]["id"], "b")

        # Polling again with no change forwards nothing.
        with mock.patch("app.poller.instagram.fetch_recent_media",
                        return_value=[_media("b"), _media("a")]), \
             mock.patch("app.poller.discord.send_media") as send2:
            forwarded = self.poller.poll_once()
        self.assertEqual(forwarded, 0)
        send2.assert_not_called()

    def test_discord_failure_leaves_post_unseen_for_retry(self):
        from app.poller import discord as d
        with mock.patch("app.poller.instagram.fetch_recent_media",
                        return_value=[_media("a")]), \
             mock.patch("app.poller.discord.send_media"):
            self.poller.poll_once()

        # New post, but Discord rejects it -> should NOT be marked seen.
        with mock.patch("app.poller.instagram.fetch_recent_media",
                        return_value=[_media("b"), _media("a")]), \
             mock.patch("app.poller.discord.send_media",
                        side_effect=d.DiscordError("boom")):
            forwarded = self.poller.poll_once()
        self.assertEqual(forwarded, 0)
        state = store.load_state()
        self.assertNotIn("b", state["seen"][self.feed.id])

    def test_disabled_feed_is_skipped(self):
        config = store.load_config()
        config.feeds[0].enabled = False
        store.save_config(config)
        with mock.patch("app.poller.instagram.fetch_recent_media") as fetch:
            self.poller.poll_once()
        fetch.assert_not_called()


if __name__ == "__main__":
    unittest.main()
