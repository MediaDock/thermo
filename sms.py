"""
SMS printer.
Receives SMS via a SIMCom SIM7672E modem on a serial port and prints each one.
"""

import re
import sys
import time

import serial

from printer import open_printer, rule, wrap

# --- Modem config ---
PORT     = "/dev/ttyS0"
BAUD     = 115200
TIMEOUT  = 1
POLL_SEC = 5

HEADER = "Fettes Statement"

# Indices notified via +CMTI that arrived mid-AT-command and need processing
_pending: set[int] = set()
_CMTI_RE = re.compile(r'\+CMTI:\s*"[^"]*",\s*(\d+)')


def mask_sender(sender: str) -> str:
    """Return sender with middle digits masked: +CC******last3"""
    if not sender.startswith('+') or len(sender) < 7:
        return sender
    num = sender[1:]  # digits after +
    # Single-digit country codes: +1 (US/Canada), +7 (Russia/Kazakhstan)
    cc_len = 1 if num[0] in ('1', '7') else 2
    prefix = '+' + num[:cc_len]
    last3 = num[-3:]
    middle_len = len(num) - cc_len - 3
    if middle_len <= 0:
        return sender
    return prefix + '*' * middle_len + last3


def print_sms(msg: dict, index: int):
    """Print the SMS on the thermal printer; always log it to stdout too."""
    print("=" * 50)
    print(f"  Index    : {index}")
    print(f"  From     : {mask_sender(msg['sender'])}")
    print(f"  Time     : {msg['timestamp']}")
    print(f"  Status   : {msg['status']}")
    print(f"  Message  :\n{msg['text']}")
    print("=" * 50 + "\n")

    with open_printer() as p:
        if p is None:
            return

        p.set(align="center", bold=True, custom_size=True, height=2, width=2)
        p.text(f"{HEADER}\n")
        p.text(rule())

        p.set(align="left", bold=True, custom_size=True, height=1, width=1)
        p.text("From:\n")
        p.set(align="left", bold=False, custom_size=True, height=1, width=1)
        p.text(f"  {mask_sender(msg['sender'])}\n")

        p.set(align="left", bold=True, custom_size=True, height=1, width=1)
        p.text("Received:\n")
        p.set(align="left", bold=False, custom_size=True, height=1, width=1)
        p.text(f"  {msg['timestamp']}\n")

        p.set(align="left", bold=False, custom_size=True, height=2, width=2)
        p.text(rule())
        p.text(f"{wrap(msg['text'])}\n")
        p.text(rule())
        p.cut()


# ---------------------------------------------------------------------------
# Modem helpers
# ---------------------------------------------------------------------------

def open_port(port: str, baud: int) -> serial.Serial:
    return serial.Serial(
        port=port, baudrate=baud,
        bytesize=serial.EIGHTBITS, parity=serial.PARITY_NONE,
        stopbits=serial.STOPBITS_ONE, timeout=TIMEOUT,
        rtscts=False, dsrdtr=False,
    )


def send_at(ser: serial.Serial, cmd: str, wait: float = 0.3) -> list[str]:
    ser.write((cmd + "\r\n").encode())
    time.sleep(wait)
    lines = []
    started = False
    while True:
        raw_line = ser.readline()
        if not raw_line:
            break  # readline timed out — no more data coming
        try:
            line = raw_line.decode('utf-8').strip()
        except UnicodeDecodeError:
            line = raw_line.decode('latin-1').strip()
        if not line:
            if started:
                lines.append("")  # preserve blank lines within message body
            continue
        started = True
        m = _CMTI_RE.match(line)
        if m:
            # +CMTI arrived mid-command; save it for later instead of discarding
            _pending.add(int(m.group(1)))
        else:
            lines.append(line)
        if line in ("OK", "ERROR") or line.startswith(("+CME ERROR", "+CMS ERROR")):
            break
    return lines


def expect_ok(ser: serial.Serial, cmd: str, wait: float = 0.3) -> bool:
    return any(l == "OK" for l in send_at(ser, cmd, wait))


def init_modem(ser: serial.Serial):
    print("[*] Initialising modem…")
    for _ in range(5):
        if expect_ok(ser, "AT"):
            break
        time.sleep(1)
    else:
        sys.exit("[!] Modem not responding. Check port / baud rate.")

    expect_ok(ser, "ATE0")
    expect_ok(ser, "AT+CMEE=2")
    expect_ok(ser, "AT+CMGF=1")
    expect_ok(ser, 'AT+CSCS="UTF-8"')
    expect_ok(ser, "AT+CNMI=2,1,0,0,0")
    expect_ok(ser, 'AT+CPMS="ME","ME","ME"')
    print("[*] Modem ready.\n")


def parse_cmgr(lines: list[str]) -> dict | None:
    header_re = re.compile(
        r'\+CMGR:\s*"([^"]*)",\s*"([^"]*)",\s*[^,]*,\s*"([^"]*)"'
    )
    for i, line in enumerate(lines):
        m = header_re.match(line)
        if m:
            status, sender, timestamp = m.group(1), m.group(2), m.group(3)
            body_lines = []
            for body_line in lines[i + 1:]:
                if body_line in ("OK", "ERROR"):
                    break
                body_lines.append(body_line)
            return {"status": status, "sender": sender,
                    "timestamp": timestamp, "text": "\n".join(body_lines)}
    return None


def read_message(ser: serial.Serial, index: int) -> dict | None:
    return parse_cmgr(send_at(ser, f"AT+CMGR={index}", wait=0.5))


def delete_message(ser: serial.Serial, index: int):
    send_at(ser, f"AT+CMGD={index}")


def list_all(ser: serial.Serial) -> list[int]:
    resp = send_at(ser, 'AT+CMGL="ALL"', wait=1.0)
    return [int(m.group(1)) for line in resp
            if (m := re.match(r'\+CMGL:\s*(\d+)', line))]


def handle_unsolicited(ser: serial.Serial, line: str):
    m = _CMTI_RE.match(line)
    if m:
        index = int(m.group(1))
        print(f"[+] New SMS at index {index}")
        msg = read_message(ser, index)
        if msg is None:
            raw = send_at(ser, f"AT+CMGR={index}", wait=1.0)
            msg = parse_cmgr(raw)
            if msg is None:
                print(f"[!] parse_cmgr failed. Raw response: {raw}")
        if msg:
            print_sms(msg, index)
            delete_message(ser, index)


def process_stored(ser: serial.Serial, label: str):
    for idx in list_all(ser):
        msg = read_message(ser, idx)
        if msg:
            print(f"[+] {label} SMS at index {idx}")
            print_sms(msg, idx)
            delete_message(ser, idx)


def listen(ser: serial.Serial):
    init_modem(ser)
    process_stored(ser, "Stored")

    print("[*] Listening for incoming SMS  (Ctrl-C to quit)…\n")
    last_poll = time.time()

    while True:
        while ser.in_waiting:
            line = ser.readline().decode(errors="replace").strip()
            if line:
                handle_unsolicited(ser, line)

        # Drain any +CMTI indices captured inside send_at during message processing
        while _pending:
            index = _pending.pop()
            print(f"[+] New SMS at index {index} (recovered from AT response)")
            msg = read_message(ser, index)
            if msg:
                print_sms(msg, index)
                delete_message(ser, index)

        if time.time() - last_poll >= POLL_SEC:
            last_poll = time.time()
            process_stored(ser, "Polled")

        time.sleep(0.05)


def run():
    try:
        ser = open_port(PORT, BAUD)
    except serial.SerialException as e:
        sys.exit(f"[!] Cannot open {PORT}: {e}")

    try:
        listen(ser)
    finally:
        ser.close()
