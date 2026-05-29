"""Flask web GUI for managing feeds and triggering polls.

Routes:
- ``GET  /``               dashboard: list feeds, settings, status
- ``POST /feeds``          add a feed (resolves @username, tests the token)
- ``POST /feeds/<id>/toggle``  enable/disable a feed
- ``POST /feeds/<id>/test``    send the latest post to its channel now
- ``POST /feeds/<id>/delete``  remove a feed
- ``POST /settings``       update the poll interval
- ``POST /poll``           run a poll cycle immediately

This is a single-user, LAN/home-server tool: there's no auth layer, so run it
behind your own network or a reverse proxy with auth if you expose it.
"""

from __future__ import annotations

import logging

from flask import (
    Flask,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)

from . import discord, instagram, store
from .poller import poller

log = logging.getLogger(__name__)


def create_app() -> Flask:
    app = Flask(__name__)
    # Secret key only protects flash-message cookies on this local tool.
    app.secret_key = "insta2discord-local"

    @app.route("/")
    def index():
        config = store.load_config()
        state = store.load_state()
        # Surface how many posts we've forwarded per feed for the dashboard.
        seen_counts = {fid: len(ids) for fid, ids in state.get("seen", {}).items()}
        return render_template(
            "index.html",
            config=config,
            seen_counts=seen_counts,
            poller_alive=poller._thread.is_alive() if poller._thread else False,
        )

    @app.route("/feeds", methods=["POST"])
    def add_feed():
        ig_user_id = request.form.get("ig_user_id", "").strip()
        access_token = request.form.get("access_token", "").strip()
        webhook = request.form.get("discord_webhook_url", "").strip()
        name = request.form.get("name", "").strip()

        if not (ig_user_id and access_token and webhook):
            flash("Instagram user ID, access token, and webhook URL are all required.", "error")
            return redirect(url_for("index"))

        # Validate the token by resolving the @username before saving.
        username = instagram.get_username(ig_user_id, access_token)
        if not username:
            flash(
                "Couldn't verify that Instagram account/token. "
                "Check the user ID and that the token has instagram_basic permission.",
                "error",
            )
            return redirect(url_for("index"))

        config = store.load_config()
        feed = store.Feed.new(
            name=name or f"@{username}",
            ig_user_id=ig_user_id,
            access_token=access_token,
            discord_webhook_url=webhook,
            ig_username=username,
        )
        config.feeds.append(feed)
        store.save_config(config)
        flash(f"Added feed for @{username}. New posts will start forwarding shortly.", "success")
        poller.trigger()  # baseline the feed right away
        return redirect(url_for("index"))

    @app.route("/feeds/<feed_id>/toggle", methods=["POST"])
    def toggle_feed(feed_id: str):
        config = store.load_config()
        for f in config.feeds:
            if f.id == feed_id:
                f.enabled = not f.enabled
                store.save_config(config)
                flash(f"{'Enabled' if f.enabled else 'Disabled'} feed {f.name}.", "success")
                break
        return redirect(url_for("index"))

    @app.route("/feeds/<feed_id>/test", methods=["POST"])
    def test_feed(feed_id: str):
        config = store.load_config()
        feed = next((f for f in config.feeds if f.id == feed_id), None)
        if not feed:
            flash("Feed not found.", "error")
            return redirect(url_for("index"))
        try:
            media = instagram.fetch_recent_media(feed.ig_user_id, feed.access_token, limit=1)
            if not media:
                flash("No media found on that account to test with.", "error")
            else:
                discord.send_media(feed.discord_webhook_url, media[0])
                flash("Sent the latest post to Discord as a test.", "success")
        except (instagram.InstagramError, discord.DiscordError) as exc:
            flash(f"Test failed: {exc}", "error")
        return redirect(url_for("index"))

    @app.route("/feeds/<feed_id>/delete", methods=["POST"])
    def delete_feed(feed_id: str):
        config = store.load_config()
        config.feeds = [f for f in config.feeds if f.id != feed_id]
        store.save_config(config)
        # Drop its seen-history too.
        state = store.load_state()
        state.get("seen", {}).pop(feed_id, None)
        state.get("tokens", {}).pop(feed_id, None)
        store.save_state(state)
        flash("Feed deleted.", "success")
        return redirect(url_for("index"))

    @app.route("/settings", methods=["POST"])
    def update_settings():
        config = store.load_config()
        try:
            config.poll_interval_seconds = max(60, int(request.form.get("poll_interval_seconds", 300)))
            store.save_config(config)
            flash("Settings saved.", "success")
        except ValueError:
            flash("Poll interval must be a number of seconds.", "error")
        return redirect(url_for("index"))

    @app.route("/poll", methods=["POST"])
    def poll_now():
        count = poller.poll_once()
        flash(f"Poll complete — forwarded {count} new post(s).", "success")
        return redirect(url_for("index"))

    return app
