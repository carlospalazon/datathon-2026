# LED feedback contribution

`led_demo/` is an Arduino App Lab app for the UNO Q's built-in 8 x 13 blue LED matrix and its onboard RGB LED 1. The matrix shows the student's selected answer (A-E), a waiting symbol, correct/incorrect feedback, and hint levels H1-H3. RGB LED 1 is blue for ready/selected, yellow for checking, green for correct, red for incorrect/error, and purple for a hint. The matrix varies brightness so feedback is readable without relying on colour alone. The question, answer options, and hint text stay on the board-served web page.

The demo uses an original `2 + 3 x 4` problem and needs no model or M3Kang files. It lets the LED part be tested before the team's copilot is integrated. No external hardware, cloud service, CDN, or runtime internet connection is required. RGB LED 2 remains available for system status.

### Integration contract

Copy `led_demo/python/led_feedback.py` into the Python directory of the team's App Lab app. After the app starts its sketch, call:

```python
from led_feedback import publish

publish("ready")
publish("selected", answer="B")
publish("thinking")
publish("correct")       # or publish("incorrect")
publish("hint", hint_level=1)  # levels 1, 2, or 3
publish("error")
```

The copilot decides correctness and when a hint is appropriate; the LED module only draws the event it receives. Do not send the correct option to `selected`: that argument is the **student's** selected letter. `render_frame(...)` and `rgb_for_event(...)` are pure Python for local checks. `publish(...)` sends the frame over the Arduino Bridge using `Frame` and the `draw` function in `sketch/sketch.ino`, then sets onboard RGB LED 1 with Arduino's `Leds` API. The integrated tutor app uses its existing events and `copilot.matrix.rgb(...)` for the same colour meanings. Keep the team's `predict.py` separate from App Lab and these display calls.

### Run the demo on the board

1. Set up the UNO Q with Arduino App Lab and copy `led_demo/` to `/home/arduino/ArduinoApps/math-led-feedback/` on the board. Keep `app.yaml`, `python/`, `sketch/`, and `assets/` together.
2. In App Lab, open and start the app. The sketch may take a minute to compile at first start. Alternatively run `arduino-app-cli app start user:math-led-feedback` on the board. If startup fails, read `arduino-app-cli app logs /home/arduino/ArduinoApps/math-led-feedback --all`.
3. On a laptop connected to the same network, visit `http://<board-ip>:7000`. For an offline demo over USB, turn off the board's Wi-Fi, run `adb forward tcp:7000 tcp:7000` on the laptop, and visit `http://127.0.0.1:7000`.
4. Press **A** to see an incorrect result (red LED 1), then **Next hint** three times to see H1-H3 (purple). Press **Reset** (blue), then **B** to see a correct result (green). Watch for yellow while checking. Confirm the matrix, RGB LED 1, and webpage agree at each step. Restart the app and repeat the test.

No hardware test results are claimed here until the demo has been run on an UNO Q. The App Lab and Bridge pattern follows [Arduino's official LED matrix example](https://github.com/arduino/app-bricks-examples/tree/main/core-and-foundational/02-led-matrix/02-led-matrix-frame). Colour uses [Arduino's documented `Leds.set_led1_color` API](https://docs.arduino.cc/tutorials/uno-q/user-manual/). The matrix itself is monochrome blue; it cannot display green or red pixels.

### Local checks

```bash
python3 -m unittest discover -s tests -v
```

The tests cover every display state, frame dimensions and brightness, distinct symbols, and invalid inputs. The board-specific `Frame`/Bridge call and physical appearance still require the on-device test above.
