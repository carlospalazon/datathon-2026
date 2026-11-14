"""Math Copilot events rendered on the UNO Q's built-in 8 x 13 LED matrix.

render_frame() is pure Python so the display contract can be checked on a laptop.
publish() imports the Arduino runtime only when called on the board.
"""

ROWS = 8
COLS = 13
ON = 7

# The matrix itself is blue and monochrome. These colours use the UNO Q's
# built-in, Linux-controlled RGB LED 1; RGB LED 2 is reserved for system status.
RGB = {
    "ready": (0, 0, 1),       # blue: a new problem is ready
    "selected": (0, 0, 1),    # blue: the student's answer was received
    "thinking": (1, 1, 0),    # yellow: checking
    "correct": (0, 1, 0),     # green
    "incorrect": (1, 0, 0),   # red
    "hint": (1, 0, 1),        # purple: learning support
    "error": (1, 0, 0),       # red, paired with ! on the matrix
}

BRIGHTNESS = {
    "ready": 3,
    "selected": 5,
    "thinking": 2,
    "correct": 7,
    "incorrect": 7,
    "hint": 5,
    "error": 7,
}

# Five-column, seven-row glyphs; two glyphs fit side by side on the matrix.
FONT = {
    "A": (".###.", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"),
    "B": ("####.", "#...#", "#...#", "####.", "#...#", "#...#", "####."),
    "C": (".###.", "#...#", "#....", "#....", "#....", "#...#", ".###."),
    "D": ("####.", "#...#", "#...#", "#...#", "#...#", "#...#", "####."),
    "E": ("#####", "#....", "#....", "####.", "#....", "#....", "#####"),
    "H": ("#...#", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"),
    "1": ("..#..", ".##..", "..#..", "..#..", "..#..", "..#..", ".###."),
    "2": (".###.", "#...#", "....#", "...#.", "..#..", ".#...", "#####"),
    "3": ("####.", "....#", "....#", ".###.", "....#", "....#", "####."),
    "?": (".###.", "#...#", "....#", "...#.", "..#..", ".....", "..#.."),
    "!": ("..#..", "..#..", "..#..", "..#..", "..#..", ".....", "..#.."),
}

EVENTS = frozenset(RGB)


def _draw_glyph(grid, glyph, left, brightness):
    for row, pattern in enumerate(FONT[glyph]):
        for col, pixel in enumerate(pattern):
            if pixel == "#":
                grid[row][left + col] = brightness


def rgb_for_event(event):
    """Return the RGB LED 1 state as three on/off channel values."""
    if event not in EVENTS:
        raise ValueError("unknown display event")
    return RGB[event]


def render_frame(event, answer=None, hint_level=None):
    """Return an immutable 8 x 13 brightness frame (values 0 to 7)."""
    if event not in EVENTS:
        raise ValueError("event must be ready, selected, thinking, correct, incorrect, hint, or error")
    if event == "selected":
        if not isinstance(answer, str) or answer not in "ABCDE" or len(answer) != 1:
            raise ValueError("selected requires exactly one answer from A to E")
    elif answer is not None:
        raise ValueError("answer is only valid for selected")
    if event == "hint":
        if type(hint_level) is not int or hint_level not in (1, 2, 3):
            raise ValueError("hint requires hint_level 1, 2, or 3")
    elif hint_level is not None:
        raise ValueError("hint_level is only valid for hint")

    grid = [[0] * COLS for _ in range(ROWS)]
    brightness = BRIGHTNESS[event]
    if event in ("ready", "thinking", "error", "selected"):
        glyph = {"ready": "?", "thinking": "?", "error": "!"}.get(event, answer)
        _draw_glyph(grid, glyph, 4, brightness)
    elif event == "hint":
        _draw_glyph(grid, "H", 1, brightness)
        _draw_glyph(grid, str(hint_level), 7, brightness)
    elif event == "correct":
        for row, col in ((2, 8), (3, 7), (4, 6), (5, 5), (6, 4), (5, 3), (4, 2)):
            grid[row][col] = brightness
    else:  # incorrect
        for row in range(1, 7):
            grid[row][row + 2] = brightness
            grid[row][10 - row] = brightness
    return tuple(tuple(row) for row in grid)


def publish(event, answer=None, hint_level=None):
    """Render an event on the blue matrix and built-in RGB LED 1."""
    frame = render_frame(event, answer=answer, hint_level=hint_level)
    import numpy as np
    from arduino.app_utils import Bridge, Frame, Leds

    Bridge.call("draw", Frame(np.asarray(frame, dtype=np.uint8)).to_board_bytes())
    Leds.set_led1_color(*rgb_for_event(event))
