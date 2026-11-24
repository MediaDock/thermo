# thermo

Thermal printer kiosk for an Epson printer (USB, `/dev/usb/lp0`) on a Raspberry Pi. Two modes:

- **questions** (default): prints a random question from `questions.txt` when a button on GPIO17 (BCM, wired to GND) is pressed.
- **sms**: receives SMS via a SIMCom SIM7672E on `/dev/ttyS0` and prints each one (sender masked).

| File           | Purpose                                         |
|----------------|-------------------------------------------------|
| `main.py`      | Entry point, picks the mode                     |
| `printer.py`   | Shared printer helpers (open/close, wrap, logo) |
| `questions.py` | Button → random question                        |
| `sms.py`       | Modem → SMS                                     |

## Setup

```bash
# 1. Hardware access (gpio for questions, dialout for sms)
sudo usermod -aG gpio,dialout,lp $USER && newgrp lp

# 2. Printer udev rule
echo 'SUBSYSTEM=="usb", ATTRS{idVendor}=="04b8", ATTRS{idProduct}=="0202", MODE="0666"' \
  | sudo tee /etc/udev/rules.d/99-escpos.rules
sudo udevadm control --reload-rules && sudo udevadm trigger

# 3. Dependencies (GPIO libs from apt, the rest in a venv; install pyserial, NOT serial)
sudo apt install -y python3-venv python3-gpiozero python3-lgpio
python3 -m venv --system-site-packages venv
venv/bin/pip install python-escpos pyserial
```

## Run

```bash
venv/bin/python main.py            # questions mode
venv/bin/python main.py sms        # SMS mode
```

## Run as a Service

```bash
sudo nano /etc/systemd/system/thermo.service
```

```ini
[Unit]
Description=Thermo Printer
After=network.target

[Service]
Type=simple
User=gd
WorkingDirectory=/home/gd/thermo
Environment=PYTHONUNBUFFERED=1
# Append "sms" for SMS mode
ExecStart=/home/gd/thermo/venv/bin/python /home/gd/thermo/main.py
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now thermo
sudo journalctl -u thermo -f  # view logs
```

## Config

Edit the constants at the top of `questions.py` (GPIO pin, logo, spacing), `sms.py` (serial port, header text)
or `printer.py` (printer device, line width).
TM-T20III uses product ID `0x0E28` instead of `0x0202` — confirm yours with `lsusb`.
