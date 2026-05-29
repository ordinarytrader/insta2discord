#!/usr/bin/env python3
"""Entry point: start the background poller and serve the web GUI.

Usage:
    python run.py                # serve on http://0.0.0.0:8080
    HOST=127.0.0.1 PORT=5000 python run.py
    python run.py --poll-once    # run a single poll cycle and exit (for cron)
"""

from __future__ import annotations

import logging
import os
import sys

from app.poller import poller
from app.web import create_app


def _configure_logging() -> None:
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def main() -> None:
    _configure_logging()

    if "--poll-once" in sys.argv:
        # One-shot mode: handy if you'd rather drive polling from cron/systemd
        # timers than keep the in-process scheduler running.
        count = poller.poll_once()
        logging.info("poll-once complete: forwarded %d post(s)", count)
        return

    poller.start()
    app = create_app()
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8080"))
    # use_reloader=False so we don't spawn a second poller thread.
    app.run(host=host, port=port, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
