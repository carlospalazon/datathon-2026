"""What the tutor shows on the UNO Q's 8x13 LED matrix, as plain frames.

The tutor only emits events, such as {"event": "tick"}. frame(event) turns one into
8 rows of 13 brightness values (0 to 7). On the board, the App Lab app sends the
frame to the sketch over the Bridge; on a laptop, FakeMatrix prints it.
Standard library only: no numpy here, so the tutor runs anywhere.
"""
ROWS, COLS, ON = 8, 13, 7

# 5x7 characters
FONT = {
    "A": [".###.", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"],
    "B": ["####.", "#...#", "#...#", "####.", "#...#", "#...#", "####."],
    "C": [".###.", "#...#", "#....", "#....", "#....", "#...#", ".###."],
    "D": ["####.", "#...#", "#...#", "#...#", "#...#", "#...#", "####."],
    "E": ["#####", "#....", "#....", "####.", "#....", "#....", "#####"],
    "?": [".###.", "#...#", "....#", "...#.", "..#..", ".....", "..#.."],
    "0": [".###.", "#...#", "#..##", "#.#.#", "##..#", "#...#", ".###."],
    "1": ["..#..", ".##..", "..#..", "..#..", "..#..", "..#..", ".###."],
    "2": [".###.", "#...#", "....#", "...#.", "..#..", ".#...", "#####"],
    "3": ["####.", "....#", "....#", ".###.", "....#", "....#", "####."],
    "4": ["...#.", "..##.", ".#.#.", "#..#.", "#####", "...#.", "...#."],
    "5": ["#####", "#....", "####.", "....#", "....#", "#...#", ".###."],
    "6": [".###.", "#....", "#....", "####.", "#...#", "#...#", ".###."],
    "7": ["#####", "....#", "...#.", "..#..", ".#...", ".#...", ".#..."],
    "8": [".###.", "#...#", "#...#", ".###.", "#...#", "#...#", ".###."],
    "9": [".###.", "#...#", "#...#", ".####", "....#", "....#", ".###."],
}
TICK = ["........#", ".......#.", "......#..", "#....#...", ".#..#....", "..##....."]
CROSS = ["#.....#", ".#...#.", "..#.#..", "...#...", "..#.#..", ".#...#.", "#.....#"]
DOTS = ["...........", "...........", "...........", "##..##..##.", "##..##..##.", "..........."]


def blank():
    return [[0] * COLS for _ in range(ROWS)]


def stamp(grid, pattern, top, left, value=ON):
    for r, line in enumerate(pattern):
        for c, pixel in enumerate(line):
            if pixel == "#" and 0 <= top + r < ROWS and 0 <= left + c < COLS:
                grid[top + r][left + c] = value
    return grid


def text(chars):
    """One character centred, or two side by side (5 + 1 + 5 columns)."""
    chars = str(chars).upper()[:2]
    grid = blank()
    if len(chars) == 1:
        return stamp(grid, FONT.get(chars, FONT["?"]), 0, 4)
    stamp(grid, FONT.get(chars[0], FONT["?"]), 0, 1)
    return stamp(grid, FONT.get(chars[1], FONT["?"]), 0, 7)


def bar(value, maximum, row=7):
    """A horizontal bar on one row, for a level or a help step."""
    grid = blank()
    lit = round(COLS * max(0, min(value, maximum)) / maximum) if maximum else 0
    for c in range(lit):
        grid[row][c] = ON
    return grid


def frame(event):
    """Turn one tutor event into an 8x13 frame."""
    kind = event["event"]
    if kind == "letter":
        return text(event["value"])
    if kind == "number":
        return text(str(event["value"])[-2:])
    if kind == "tick":
        return stamp(blank(), TICK, 1, 2)
    if kind == "cross":
        return stamp(blank(), CROSS, 0, 3)
    if kind == "thinking":
        return stamp(blank(), DOTS, 1, 1)
    if kind == "help_step":  # the help rung, as a bar out of the number of rungs
        return bar(event["value"], event.get("of", 4))
    if kind == "level":  # level 0..7 as 1..8 lit columns, with the digit above
        grid = text(str(event["value"] + 1))
        for c in range(event["value"] + 1):
            grid[7][c] = ON
        return grid
    if kind == "clear":
        return blank()
    raise ValueError(f"unknown matrix event: {kind}")


class FakeMatrix:
    """Stands in for the LED matrix on a laptop: keeps the frames and can print them."""

    def __init__(self):
        self.frames = []

    def show(self, event):
        self.frames.append((event, frame(event)))

    @staticmethod
    def render(grid):
        return "\n".join("".join("#" if v else "." for v in row) for row in grid)
