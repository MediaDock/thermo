#!/usr/bin/env python3
"""
Thermal printer kiosk for an Epson printer on /dev/usb/lp0.

Modes:
  questions  print a random question from questions.txt on a GPIO button press (default)
  sms        print every SMS received by the SIM7672E modem
"""

import argparse
import signal
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("mode", nargs="?", default="questions", choices=["questions", "sms"])
    args = parser.parse_args()

    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))

    # Import lazily so each mode only needs its own hardware libraries
    if args.mode == "sms":
        import sms as mode
    else:
        import questions as mode

    try:
        mode.run()
    except KeyboardInterrupt:
        print("\n[*] Exiting.")


if __name__ == "__main__":
    main()
