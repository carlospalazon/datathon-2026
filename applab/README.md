# Tutor Cangur on the UNO Q (App Lab)

The teaching copilot as an Arduino App Lab app. The board serves the student's web page on port 7000, runs the tutor in the app's Python, and shows every tutor event on the 8x13 LED matrix through the Bridge. No language model is called, and nothing needs the internet once the app is built.

| Part | Where | What |
| --- | --- | --- |
| `math-tutor/python/main.py` | Linux | The API for the page, and the matrix calls |
| `copilot/tutor.py`, `copilot/matrix.py` | Linux | The tutor and the LED frames, copied in by `package.py` |
| `teach/index.html` | Browser | The page, copied to `assets/`. The same page runs on the laptop with `teach/server.py` |
| `math-tutor/sketch/` | Microcontroller | Draws the frames it receives (from Mohamed's `led_demo`) |

## Build and run

On the laptop, with `data/catalog/` built (see `laptop/build_catalog.py`):

```bash
python3 applab/package.py
adb push applab/build/math-tutor /home/arduino/ArduinoApps/
```

`applab/build/` holds M3Kang problems and images, so Git ignores it. Never commit it.

On the board (over `adb shell`, set `TMPDIR` first, see below):

```bash
export TMPDIR=/tmp
arduino-app-cli app start user:math-tutor
arduino-app-cli app logs /home/arduino/ArduinoApps/math-tutor --all
```

Open it on the laptop over USB: `adb forward tcp:7000 tcp:7000`, then <http://127.0.0.1:7000>.

## Two problems we hit, and the fixes

- **`stat /data/local/tmp: no such file or directory`** when starting an app from `adb shell`: adb sets `TMPDIR` to an Android path that doesn't exist on the board. Run `export TMPDIR=/tmp` first. Over SSH this doesn't happen.
- **`#error "Please update the Arduino_RouterBridge library..."`** when the sketch compiles: the board's library index was a year old, so it only knew Arduino_RouterBridge 0.2.2, and the zephyr core 1.1.0 needs a newer one. With internet on the board, refresh the index once: `arduino-cli lib update-index`. The next start downloads Arduino_RouterBridge 0.4.4 and compiles. The same fix applies to `led_demo/`.

## Measured on our board (14 November 2026)

- The app starts, the page and the API answer on port 7000, and the logs show no Bridge errors.
- With App Lab and both model services running: 2,765 MB of RAM available (`free -m`).
- Not yet checked: what the matrix looks like to a person, and a demo with Wi-Fi off.
