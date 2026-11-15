# Product lab: original features for Tutor Cangur

Memory of the **Product** role. Newest "Built" entry at the bottom. No problem text here.

## Backlog (best first)

| # | Feature | Why a student or teacher wants it | Uses | Status |
|---|---|---|---|---|
| 1 | **"One like this, but yours."** After a wrong answer (or on request), generate a fresh problem of the same kind with smaller numbers, solvable in a minute, then return to the original. | Practice on the exact skill that failed, never the same problem twice, nothing to memorise. | synthetic generators (computed answers, worked solutions, 3 languages), topic of the current problem | open |
| 2 | **Mistake names on generated problems.** Each wrong option of a generated problem is the result of a known slip: say which ("you added the prices but forgot the quantities"), without giving the answer. | Feedback that is specific, instant and needs no model. | generators' wrong-option formulas, `copilot/diagnose.py` | open |
| 3 | **Cangur exam mode.** A timed paper built from the catalogue by level, with the real scoring (3/4/5 points, a quarter of the points lost per wrong answer, blank is free), a countdown on the LED matrix, and a review at the end that leads into the tutor. | The real competition experience; shows when leaving a blank is the right call. | catalogue levels, LED matrix, student memory | open |
| 4 | **Skill map.** One screen (and a matrix view) of the student's topics by level: tried, mastered, shaky, with "what to try next". A teacher view of the class as a heat map, by pseudonym. | Students see progress; teachers see where the class is stuck. | SQLite student memory, topics | open |
| 5 | **Think-first timer.** The page hides the hint button for the first seconds of a new problem and shows a calm progress ring; the board uses that time to get the help ready. | Encourages a real attempt, and makes the wait invisible. | read-ahead of the problem (already in the app), LED matrix | open |
| 6 | **Explain it back.** After a right answer, one tap picks which of three explanations matches how the student solved it (the checked solution and two wrong methods that also give that number). | Checks understanding, not luck. | checked solutions, generators' typical mistakes | open |
| 7 | **Reading modes.** One idea per line, larger spacing, key data highlighted, a "numbers only" strip; chosen by the student, remembered, never labelled. | Dyslexia- and dyscalculia-friendly without a separate product. | key data and key condition already in the catalogue | open |
| 8 | **Class duel.** Two students (or two halves of the class) answer the same problem on two devices; the matrix shows the vote split before the answer is revealed. | Makes the board the centre of a classroom debate. | LED matrix, web page | open |

## For the model lab

(Requests from Product to the model lab, and answers.)

## Built

<!-- Template:
### YYYY-MM-DD HH:MM · short name
- **What:**
- **Why:**
- **See it:** command, URL, what to click
- **Tests / checks run:**
- **Not done:**
- **Commit:**
-->
