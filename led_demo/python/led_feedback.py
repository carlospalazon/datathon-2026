"""Math Copilot events rendered on the UNO Q's built-in 8 x 13 LED matrix.

render_frame() is pure Python so the display contract can be checked on a laptop.
publish() imports the Arduino runtime only when called on the board.
"""

ROWS = 8
COLS = 13
ON = 7

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

EVENTS = frozenset({"ready", "selected", "thinking", "correct", "incorrect", "hint", "error"})


def _draw_glyph(grid, glyph, left):
    for row, pattern in enumerate(FONT[glyph]):
        for col, pixel in enumerate(pattern):
            if pixel == "#":
                grid[row][left + col] = ON


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
    if event in ("ready", "thinking", "error", "selected"):
        glyph = {"ready": "?", "thinking": "?", "error": "!"}.get(event, answer)
        _draw_glyph(grid, glyph, 4)
    elif event == "hint":
        _draw_glyph(grid, "H", 1)
        _draw_glyph(grid, str(hint_level), 7)
    elif event == "correct":
        for row, col in ((2, 8), (3, 7), (4, 6), (5, 5), (6, 4), (5, 3), (4, 2)):
            grid[row][col] = ON
    else:  # incorrect
        for row in range(1, 7):
            grid[row][row + 2] = ON
            grid[row][10 - row] = ON
    return tuple(tuple(row) for row in grid)


def publish(event, answer=None, hint_level=None):
    """Render one copilot event on the board; call from App Lab's Python process."""
    frame = render_frame(event, answer=answer, hint_level=hint_level)
    import numpy as np
    from arduino.app_utils import Bridge, Frame

    Bridge.call("draw", Frame(np.asarray(frame, dtype=np.uint8)).to_board_bytes())
