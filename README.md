# insta2discord

Self-hosted service that forwards **new Instagram posts** to a **Discord
channel** — your own DIY version of rss.app. It polls the official Instagram
Graph API on an interval, detects posts it hasn't seen before, and pushes them
into Discord via an Incoming Webhook as a rich embed.

```
Instagram Graph API  ──poll──▶  insta2discord  ──webhook──▶  Discord channel
```

## Features

- **One or many feeds** — map several Instagram accounts to different Discord
  channels.
- **No re-posting / no flooding** — the first poll of a new feed records
  existing posts silently; only posts created *after* setup get forwarded.
  Forwarded IDs are remembered across restarts.
- **Auto token refresh** — long-lived tokens (~60-day life) are refreshed
  automatically before they expire.
- **Small web GUI** — add/remove feeds, paste tokens, send a test post, and
  tune the poll interval.
- **Retry-safe** — if Discord is down, the post stays queued and is retried on
  the next cycle.

## Where to host it

This needs to run somewhere that stays on. Pick a guide:

- **Raspberry Pi (recommended for always-on):** [`HOSTING_RASPBERRY_PI.md`](HOSTING_RASPBERRY_PI.md)
  — runs 24/7 as a proper background service, auto-starts on boot.
- **Shared web hosting (HostGator / cPanel):** [`HOSTING_HOSTGATOR.md`](HOSTING_HOSTGATOR.md)
  — free if you already have it, via a scheduled cron job.
- **Your own desktop:** just run `python run.py` (below) — only works while the
  computer is on.

## Why the Graph API (and not scraping)

Instagram blocks unofficial scraping and there's no public RSS feed. The
supported route is the **Instagram Graph API**, which requires a
**Business or Creator** account linked to a Facebook Page. That's the path this
project uses.

---

## Setup

### 1. Prerequisites

- Python 3.10+
- An Instagram **Business or Creator** account, linked to a Facebook Page
  (do this in the Instagram app: *Settings → Account type and tools*).
- A Discord server where you can create webhooks.

### 2. Install

```bash
git clone <this-repo>
cd insta2discord
pip install -r requirements.txt
```

### 3. Get your Discord webhook URL

In Discord: **Channel → Edit Channel → Integrations → Webhooks → New Webhook**,
choose the target channel, then **Copy Webhook URL**. It looks like
`https://discord.com/api/webhooks/123.../abc...`.

### 4. Get your Instagram credentials

You need two things: your **IG user ID** and a **long-lived access token**.

1. Go to [Meta for Developers](https://developers.facebook.com/) → **My Apps →
   Create App** (type: *Business*).
2. Add the **Instagram Graph API** product and link your Facebook Page /
   Instagram account.
3. Open the **Graph API Explorer**, select your app, and grant these
   permissions: `instagram_basic`, `pages_show_list`,
   `pages_read_engagement` (and `business_management` if prompted).
4. Generate a **User Access Token**, then **extend it to a long-lived token**
   (the Explorer's token debugger has an "Extend Access Token" button, or use
   the [token exchange endpoint](https://developers.facebook.com/docs/instagram-platform/long-lived-access-tokens)).
   Long-lived tokens last ~60 days; insta2discord refreshes them for you after
   that.
5. Find your **IG user ID**: with the token, call
   `GET /me/accounts` to find your Page, then
   `GET /{page-id}?fields=instagram_business_account`. The returned
   `instagram_business_account.id` (a long number starting `1784...`) is what
   you paste into the GUI.

> Tip: the GUI verifies the token when you add a feed by resolving the
> account's `@username`. If that fails, the token or user ID is wrong.

### 5. Run it

```bash
python run.py
```

Open **http://localhost:8080**, click **Add a feed**, paste your IG user ID,
long-lived token, and the Discord webhook URL. Done — new posts will appear in
your channel within one poll interval (default 5 minutes).

Use the **Test** button on a feed to immediately send its latest post to the
channel and confirm the wiring.

---

## Configuration

Settings live in `config.json` (created on first run, git-ignored because it
holds tokens):

| Field | Meaning |
|-------|---------|
| `poll_interval_seconds` | How often to check Instagram (min 60). Default 300. |
| `feeds[]` | Each feed: IG account ID, token, Discord webhook, enabled flag. |

Runtime bookkeeping (which posts were already forwarded, token expiry) lives in
`state.json`. Both files are written atomically.

### Environment variables

| Var | Default | Purpose |
|-----|---------|---------|
| `HOST` | `0.0.0.0` | Web GUI bind address |
| `PORT` | `8080` | Web GUI port |
| `LOG_LEVEL` | `INFO` | Logging verbosity |
| `I2D_CONFIG` / `I2D_STATE` | repo root | Override storage file paths |

---

## Running as a long-lived service

The built-in poller runs in a background thread while `run.py` is alive. To keep
it running on a home server, use **systemd**:

```ini
# /etc/systemd/system/insta2discord.service
[Unit]
Description=insta2discord
After=network-online.target

[Service]
WorkingDirectory=/opt/insta2discord
ExecStart=/usr/bin/python3 run.py
Restart=always
Environment=PORT=8080

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable --now insta2discord
```

### Or: cron-driven one-shot polling

If you'd rather not keep a process running, schedule the one-shot mode:

```cron
*/5 * * * * cd /opt/insta2discord && /usr/bin/python3 run.py --poll-once
```

---

## Security notes

This is a single-user tool with **no built-in authentication**. The GUI exposes
your tokens, so:

- Bind it to `127.0.0.1` (`HOST=127.0.0.1`) or keep it on your LAN.
- If you expose it publicly, put it behind a reverse proxy with auth.
- `config.json` / `state.json` are git-ignored — don't commit your tokens.

---

## Project layout

```
run.py                 entry point (serves GUI + starts poller)
app/
  store.py             config/state persistence (JSON, atomic writes)
  instagram.py         Graph API client (media list, username, token refresh)
  discord.py           webhook sender (builds the embed)
  poller.py            background worker: dedupe + forward + token refresh
  web.py               Flask routes
  templates/index.html the GUI
tests/
  test_poller.py       forwarding/dedupe/baseline logic
```

## How the "only new posts" logic works

1. **First poll of a feed:** all current media IDs are recorded as *seen*, and
   nothing is sent. This avoids dumping your whole back-catalogue into Discord.
2. **Subsequent polls:** any media ID not in *seen* is forwarded (oldest-new
   first, so chronological order is preserved), then added to *seen*.
3. If Discord rejects a send, the ID is left *unseen* and retried next cycle.
4. The seen-list is capped at 500 IDs per feed to bound the state file.

## Running the tests

```bash
python -m unittest discover tests -v
```

## Limitations

- The Graph API's `/media` edge surfaces feed posts (images, videos, carousels,
  Reels). **Stories** require the separate `/stories` edge and the
  `instagram_manage_insights` permission — not wired up here, but easy to add in
  `instagram.py`.
- Carousels are forwarded as a single embed showing the first image plus a link.
- Polling, not webhooks: there's a delay of up to one poll interval. Instagram
  does offer real-time webhooks, but they need a public HTTPS callback; polling
  is simpler for a home server.
