# Hosting on HostGator (shared cPanel) — step by step

This guide runs insta2discord on a **HostGator shared hosting** account, so it
works 24/7 without needing your desktop on. It uses a **cron job** (a scheduled
task) instead of a long-running program, which is what shared hosting allows.

On a public web host you should **not** run the web settings page (it would
expose your tokens). Instead you fill in your settings in a file once. These
steps use that file-based approach.

---

## Before you start, gather these 3 values

1. **Instagram user ID** — the long number for your Business/Creator account.
2. **Long-lived access token** — from the Meta developer console.
3. **Discord webhook URL** — from your Discord channel settings.

(See the main `README.md`, section "Get your Instagram credentials" and
"Get your Discord webhook URL", for exactly how to obtain each one.)

---

## Step 1 — Put your settings in a file

1. Make a copy of `config.example.json` and name it **`config.json`**.
2. Open `config.json` in a text editor and replace the three
   `PASTE_..._HERE` placeholders with your real values.
3. To add more accounts, copy the block inside `"feeds": [ ... ]` and give each
   one a different `"id"`.

> Keep this file private — it contains your tokens.

---

## Step 2 — Upload the project to HostGator

1. Log into your HostGator **cPanel**.
2. Open **Files → File Manager**.
3. Create a folder **outside** your public website folder — e.g. a folder named
   `insta2discord` in your home directory (NOT inside `public_html`). Keeping it
   out of `public_html` means no one can reach your files/tokens from a browser.
4. Upload all the project files into that folder (drag-and-drop, or use the
   **Upload** button). Make sure `config.json` (the one you just filled in) is
   included.

---

## Step 3 — Set up Python

1. In cPanel, open **Software → Setup Python App** (sometimes "Setup Python
   App" under Software).
2. Click **Create Application**.
   - **Python version:** pick the newest available (3.8+ is fine).
   - **Application root:** the `insta2discord` folder you created.
   - **Application URL:** you can leave default; we won't use the web part.
3. Click **Create**. cPanel shows a command near the top that starts with
   `source ...activate` — **copy that whole line**, you'll need it once.
4. Still on that page, find the **"Run pip install"** box (or use the terminal
   in the next step) and install the requirements: enter `requirements.txt`
   in the install box if offered, OR use Step 4 below.

---

## Step 4 — Install the dependencies (one time)

If cPanel gave you a terminal, or you can use SSH:

```bash
# 1. paste the "source ...activate" line cPanel showed you, then:
cd ~/insta2discord
pip install -r requirements.txt
```

If you don't have terminal access, HostGator's "Setup Python App" page has a
field to add packages — add `Flask` and `requests` there and click the install
button.

---

## Step 5 — Test it once by hand

Run a single check to confirm everything's wired up:

```bash
cd ~/insta2discord
python run.py --poll-once
```

The first run records your existing posts silently (so it doesn't dump your
whole history into Discord). Post something new on Instagram, run it again, and
it should appear in your Discord channel.

> Note: the very first time, it learns your current posts and sends nothing.
> Only posts made *after* that first run get forwarded.

---

## Step 6 — Schedule it with a cron job (the always-on part)

This is what makes it run automatically forever.

1. In cPanel, open **Advanced → Cron Jobs**.
2. Under "Add New Cron Job", set **Common Settings** to *Once every 5 minutes*
   (or pick your own interval).
3. In the **Command** box, paste this (adjust the path if your Python lives
   elsewhere — the "Setup Python App" page shows the exact python path):

   ```
   cd ~/insta2discord && ~/virtualenv/insta2discord/3.8/bin/python run.py --poll-once >> ~/insta2discord/cron.log 2>&1
   ```

   - `~/virtualenv/insta2discord/3.8/bin/python` is the Python that cPanel
     created for your app — copy the real path from the Setup Python App page.
   - The `>> ...cron.log` part saves output to a log file so you can check it if
     something looks off.
4. Click **Add New Cron Job**.

That's it. Every 5 minutes HostGator will wake the tool, check Instagram, post
anything new to Discord, and quit. Your tokens auto-refresh, so you shouldn't
need to touch it again.

---

## Checking on it

- Look at `~/insta2discord/cron.log` (in File Manager) to see recent activity.
- `state.json` (created automatically) is the tool's memory of what it already
  posted — don't delete it, or it'll re-baseline.

## If something doesn't work

| Symptom | Likely cause / fix |
|---|---|
| Cron log shows "No module named flask/requests" | Dependencies didn't install — redo Step 4 with the correct Python path. |
| "Couldn't verify Instagram account" / API errors | Token or user ID is wrong, or token expired before first run. Regenerate the long-lived token. |
| Nothing posts but no errors | First run only baselines — post something new, wait one interval. |
| HostGator emails you about a killed process | You're trying to run the always-on version; make sure you're using `--poll-once` via cron, not leaving `run.py` running. |
