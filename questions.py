"""
Question printer for info days.
Prints a random line from questions.txt whenever a button wired to a GPIO pin is pressed.
"""

import random
import sys
from pathlib import Path

from gpiozero import Button

from printer import load_logo, open_printer, rule, wrap

# --- Config ---
QUESTIONS_FILE = Path(__file__).with_name("questions.txt")
LOGO_FILE      = Path(__file__).with_name("logo.png")
LOGO_WIDTH     = 256    # px, 8 px = 1 mm on paper (256 px = 32 mm)
BUTTON_PIN     = 17     # BCM numbering; wire button between this pin and GND
BOUNCE_SEC     = 0.05
LINE_SPACING   = 110    # question line pitch in motion units (1/360 in on TM-T88V; text is ~85)
BOTTOM_FEED    = 3      # blank lines (~4.2 mm each) after the text before the cut


def load_questions() -> list[str]:
    lines = QUESTIONS_FILE.read_text(encoding="utf-8").splitlines()
    questions = [l.strip() for l in lines if l.strip()]
    if not questions:
        sys.exit(f"[!] No questions found in {QUESTIONS_FILE}")
    return questions


def print_question(question: str, logo):
    print(f"[+] {question}")
    with open_printer() as p:
        if p is None:
            return

        if logo is not None:
            p.set(align="center")
            p.image(logo, center=True)
            p.text("\n")

        p.set(align="left", bold=False, custom_size=True, height=2, width=2)
        p.line_spacing(LINE_SPACING)
        p.text(rule())
        p.text(wrap(question) + "\n")
        p.text(rule())
        p.line_spacing()  # back to default

        p.set(align="center", bold=False, normal_textsize=True)
        p.text("Vielen Dank!\n")
        if BOTTOM_FEED:
            p.print_and_feed(BOTTOM_FEED)
        p.cut(feed=False)  # feeds just to the cutter, then cuts


def run():
    questions = load_questions()
    logo = load_logo(LOGO_FILE, LOGO_WIDTH)
    button = Button(BUTTON_PIN, pull_up=True, bounce_time=BOUNCE_SEC)
    last = None

    print(f"[*] {len(questions)} questions loaded. Waiting for button on GPIO{BUTTON_PIN}…")
    while True:
        button.wait_for_press()
        # Avoid printing the same question twice in a row
        choices = [q for q in questions if q != last] or questions
        last = random.choice(choices)
        print_question(last, logo)
        button.wait_for_release()
