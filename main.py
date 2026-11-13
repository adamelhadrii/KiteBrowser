#!/usr/bin/python3
"""KiteBrowser entry point: `./main.py [url ...]`. A second launch opens its URLs as tabs in the running window."""
import os
import sys

from app import APP_ID, Kite

if __name__ == "__main__":
    # KITE_APP_ID lets tests run beside the user's own Kite without being handed over to it.
    sys.exit(Kite(app_id=os.environ.get("KITE_APP_ID", APP_ID)).run(sys.argv))
