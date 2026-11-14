"""A retrieval index in SQLite: one solved M3Kang problem per row."""
import json
import sqlite3
from array import array

from .embed import embed
from .llm import format_problem

SAME_LANGUAGE_SLACK = 0.05  # cosine score

SCHEMA = """
CREATE TABLE IF NOT EXISTS problems (
    key TEXT PRIMARY KEY,   -- id|language
    problem TEXT NOT NULL,  -- the full problem as JSON
    vec BLOB NOT NULL       -- float32 vector
)"""


def build(db_path, problems, batch=16):
    db = sqlite3.connect(db_path)
    db.execute(SCHEMA)
    for i in range(0, len(problems), batch):
        chunk = problems[i:i + batch]
        vectors = embed([format_problem(p) for p in chunk])
        db.executemany("INSERT OR REPLACE INTO problems VALUES (?, ?, ?)", [
            (f"{p['id']}|{p['language']}", json.dumps(p, ensure_ascii=False), array("f", v).tobytes())
            for p, v in zip(chunk, vectors)])
        db.commit()
        yield min(i + batch, len(problems))
    db.close()


class Index:
    """Loads every vector into memory once, so each search is a plain loop."""

    def __init__(self, db_path):
        db = sqlite3.connect(db_path)
        self.rows = []
        for key, problem, blob in db.execute("SELECT key, problem, vec FROM problems"):
            vec = array("f")
            vec.frombytes(blob)
            self.rows.append((key, json.loads(problem), vec))
        db.close()

    def search(self, problem, k=1, exclude_id=None):
        """Return up to k (score, problem) pairs, most similar first, one per problem id.

        exclude_id skips the same problem in other languages, so validation
        never retrieves its own translation. The index holds each id in several
        languages: the best-scoring row wins, except that the row in the query's
        language is taken when it scores within SAME_LANGUAGE_SLACK of it.
        """
        query = embed([format_problem(problem)], query=True)[0]
        language = problem.get("language")
        by_id = {}
        for _key, stored, vec in self.rows:
            if exclude_id and stored["id"] == exclude_id:
                continue
            by_id.setdefault(stored["id"], []).append((sum(a * b for a, b in zip(query, vec)), stored))
        scored = []
        for rows in by_id.values():
            pick = max(rows, key=lambda pair: pair[0])
            same = [r for r in rows if language and r[1].get("language") == language]
            if same:
                mine = max(same, key=lambda pair: pair[0])
                if mine[0] >= pick[0] - SAME_LANGUAGE_SLACK:
                    pick = mine
            scored.append(pick)
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return scored[:k]
