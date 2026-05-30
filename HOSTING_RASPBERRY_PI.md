# Hosting on a Raspberry Pi 5 — step by step

This guide gets insta2discord running 24/7 on a **Raspberry Pi 5**. Unlike
shared web hosting, the Pi runs the tool the "proper" way: a continuous
background service that auto-starts on boot and restarts itself if anything
goes wrong. Set it up once and forget it.

Written for a first-timer. Total time: a relaxed evening, including the
inevitable WiFi hiccup.

You have: **Raspberry Pi 5 8GB starter kit** (Pi, 27W power supply, case with
fan, heatsink, 128GB microSD card, micro-HDMI cable). That's everything you
need — nothing else to buy.

---

## Part A — Assemble and prepare the Pi (on your normal computer)

### Step 1 — Put it in the case with the fan

Follow the little leaflet in your kit to seat the Pi in the case, stick on the
heatsink, and plug the fan's small connector onto the board. (Don't power
anything on yet.) The fan keeps the Pi 5 cool and quiet — worth doing properly.

### Step 2 — Flash the microSD card

The microSD card is the Pi's "hard drive." We write the operating system onto
it from your normal computer.

1. On your normal computer, download **Raspberry Pi Imager** (free, official):
   https://www.raspberrypi.com/software/
2. Plug the microSD card into your computer (your kit may include a USB adapter
   for this).
3. Open Imager and choose:
   - **Device:** Raspberry Pi 5
   - **Operating System:** *Raspberry Pi OS (64-bit)* — the recommended one.
   - **Storage:** your microSD card.
4. Click **Next**, then **EDIT SETTINGS** (this is the magic part — it sets the
   Pi up before first boot so you don't even need a monitor):
   - **Set hostname:** `raspberrypi` (or whatever you like).
   - **Set username and password:** pick a username (the rest of this guide
     assumes `pi`) and a password you'll remember. **Write these down.**
   - **Configure wireless LAN:** enter your home WiFi name and password.
   - **Set locale:** your timezone/keyboard.
   - Go to the **Services** tab and **tick "Enable SSH"** → "Use password
     authentication." This lets you control the Pi from your laptop.
5. Save, then **Write**. It takes a few minutes. When done, eject the card.

> If your version of Imager doesn't show "EDIT SETTINGS," write the card anyway,
> then you'll do first-time setup with a monitor + keyboard plugged into the Pi.

### Step 3 — Boot the Pi

1. Put the microSD card into the Pi (slot on the underside).
2. Plug in the power supply. (You can skip the monitor — we'll connect remotely.)
3. Wait ~1–2 minutes for it to boot and join your WiFi.

---

## Part B — Connect to the Pi from your computer

We'll use **SSH** — a text-based remote connection. It sounds technical but
it's just typing into a terminal window.

1. Open a terminal on your normal computer:
   - **Mac:** open the **Terminal** app.
   - **Windows:** open **PowerShell** (or Windows Terminal).
2. Connect (use the username and hostname you set in Step 2):

   ```bash
   ssh pi@raspberrypi.local
   ```

   - First time, it asks "are you sure?" — type `yes`.
   - Enter the password you set. (You won't see characters as you type — that's
     normal.)
   - If `raspberrypi.local` doesn't work, find the Pi's IP address from your
     router's device list and use `ssh pi@192.168.x.x` instead.

You're now "inside" the Pi. Commands you type go to the Pi, not your computer.

### Update it first (good habit)

```bash
sudo apt update && sudo apt full-upgrade -y
```

This may take a few minutes. `sudo` means "run as administrator"; it may ask
for your password.

---

## Part C — Install insta2discord

### Step 4 — Get the project onto the Pi

Make sure git is available, then clone the project:

```bash
sudo apt install -y git python3-venv
cd ~
git clone <YOUR-REPO-URL> insta2discord
cd insta2discord
```

> Replace `<YOUR-REPO-URL>` with this repository's URL. If you'd rather not use
> git, you can copy the files over with `scp` or a tool like FileZilla — but
> git makes future updates a one-line `git pull`.

### Step 5 — Set up a Python environment and install dependencies

A "virtual environment" (`.venv`) is just a private folder of Python packages
for this project, so it doesn't interfere with the rest of the Pi.

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

### Step 6 — Quick test

```bash
.venv/bin/python run.py
```

You should see log lines and "Running on http://0.0.0.0:8080". On your normal
computer's web browser, visit **http://raspberrypi.local:8080** (or
`http://<pi-ip>:8080`). You'll see the insta2discord settings page.

Because the Pi sits on your **private home network**, it's fine to use this web
page here (unlike a public web host). Add your feed: Instagram user ID,
long-lived token, and Discord webhook URL. Use the **Test** button to confirm a
post lands in Discord.

When you're happy, stop the test with **Ctrl+C** — next we make it run forever.

---

## Part D — Make it run 24/7 (auto-start on boot)

We'll register it as a **systemd service** so it starts automatically when the
Pi powers on and restarts itself if it ever crashes.

### Step 7 — Install the service

A ready-made service file is included at `deploy/insta2discord.service`.

1. If your username is **not** `pi`, or you cloned the project somewhere other
   than `/home/pi/insta2discord`, open `deploy/insta2discord.service` and edit
   the `User=` and the two paths to match. (Edit on the Pi with
   `nano deploy/insta2discord.service`; save with Ctrl+O, Enter, then Ctrl+X.)

2. Install and start it:

   ```bash
   sudo cp deploy/insta2discord.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable --now insta2discord
   ```

   - `enable` = start automatically on every boot.
   - `--now` = also start it right now.

### Step 8 — Confirm it's running

```bash
systemctl status insta2discord
```

Look for **active (running)** in green. Press `q` to exit.

To watch the live logs (handy to see posts being forwarded):

```bash
journalctl -u insta2discord -f
```

Press Ctrl+C to stop watching (the service keeps running).

**That's it.** The Pi will now forward new Instagram posts to Discord around the
clock, survive reboots and power cuts, and refresh your tokens automatically.
You can unplug your laptop and walk away — the Pi does the rest.

---

## Everyday operations (cheat sheet)

| I want to... | Command (over SSH) |
|---|---|
| Check it's running | `systemctl status insta2discord` |
| Watch live logs | `journalctl -u insta2discord -f` |
| Restart it | `sudo systemctl restart insta2discord` |
| Stop it | `sudo systemctl stop insta2discord` |
| Change settings | Visit `http://raspberrypi.local:8080` in a browser |
| Update to a newer version | `cd ~/insta2discord && git pull && sudo systemctl restart insta2discord` |

> After `git pull`, if dependencies changed, also run
> `.venv/bin/pip install -r requirements.txt` before restarting.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `ssh: could not resolve hostname` | Use the Pi's IP address instead of `raspberrypi.local` (find it in your router's device list). |
| Service shows **failed** | `journalctl -u insta2discord -e` to see the error. Usually a wrong path/username in the service file, or dependencies not installed. |
| Web page won't load | Make sure the service is running, and that you're on the same WiFi network as the Pi. |
| "No module named flask" | The venv path in the service file is wrong, or `pip install` was skipped. Redo Step 5. |
| Nothing posts to Discord | The first poll only baselines existing posts (sends nothing). Post something new and wait one poll interval (default 5 min). |

---

## A note on security

The settings page has no password and exposes your tokens, so keep it on your
**home network only** — don't forward port 8080 through your router to the
internet. If you ever need to reach it from outside, use a VPN into your home
network (a great future Pi project in itself) rather than exposing the page.

---

## What else this Pi can do later

You bought an 8GB Pi 5 — it can run insta2discord and several other things at
once without breaking a sweat. Popular next projects:

- **Pi-hole** — network-wide ad/tracker blocking for every device in your home.
- **Home Assistant** — smart-home hub for lights, sensors, thermostats.
- **Jellyfin / Plex** — stream your own movie and music library to your TV/phone.
- **More bots like this** — mirror YouTube, RSS, or Twitch alerts into Discord.
- **A home VPN** — securely reach your home network (and this Pi) from anywhere.

Each is its own evening project, and they happily coexist on the same Pi.
