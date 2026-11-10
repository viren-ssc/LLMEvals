import json
import sqlite3
from contextlib import closing, contextmanager

from .models import Question, digest, now
from .v2_models import research_from_json


class Conflict(RuntimeError):
    pass


class Database:
    def __init__(self, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        with self.connect() as c:
            c.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY, ordinal INTEGER NOT NULL, fingerprint TEXT NOT NULL,
                    input TEXT NOT NULL, state TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
                    error TEXT, result TEXT, updated TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS steps (
                    task_id TEXT NOT NULL, name TEXT NOT NULL, signature TEXT NOT NULL,
                    value TEXT NOT NULL, PRIMARY KEY(task_id,name));
                CREATE TABLE IF NOT EXISTS events (
                    id TEXT PRIMARY KEY, task_id TEXT NOT NULL, payload TEXT NOT NULL,
                    state TEXT NOT NULL, updated TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY,value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS sources (
                    cache_key TEXT PRIMARY KEY, url TEXT NOT NULL, payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS audit (
                    event_id TEXT PRIMARY KEY, question_id TEXT NOT NULL,
                    payload TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS claim_results (
                    claim_id TEXT PRIMARY KEY, question_id TEXT NOT NULL,
                    event_id TEXT NOT NULL, payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS corrected_answers (
                    event_id TEXT PRIMARY KEY, question_id TEXT NOT NULL,
                    answer TEXT NOT NULL, verified INTEGER NOT NULL DEFAULT 0);
                CREATE TABLE IF NOT EXISTS attempts (
                    question_id TEXT NOT NULL, attempt INTEGER NOT NULL,
                    started TEXT NOT NULL, ended TEXT, outcome TEXT NOT NULL,
                    error TEXT, PRIMARY KEY(question_id,attempt));
            """)

    @contextmanager
    def connect(self):
        c = sqlite3.connect(self.path, timeout=30)
        c.row_factory = sqlite3.Row
        with closing(c), c:
            yield c

    @contextmanager
    def transaction(self):
        with self.connect() as c:
            c.execute("BEGIN IMMEDIATE")
            yield c

    def bind(self, signature):
        with self.transaction() as c:
            old = c.execute("SELECT value FROM metadata WHERE key='signature'").fetchone()
            if old and old[0] != signature:
                raise Conflict(
                    "Model/instructions/pipeline configuration changed; use a new database"
                )
            c.execute("INSERT OR IGNORE INTO metadata VALUES ('signature',?)", (signature,))

    def ingest(self, questions):
        ids = [q.question_id for q in questions]
        if len(ids) != len(set(ids)):
            raise Conflict("Duplicate question IDs")
        with self.transaction() as c:
            for i, q in enumerate(questions):
                old = c.execute(
                    "SELECT fingerprint FROM tasks WHERE id=?", (q.question_id,)
                ).fetchone()
                if old and old[0] != q.fingerprint:
                    raise Conflict(f"Local input changed: {q.question_id}; use a new database")
                c.execute(
                    "INSERT OR IGNORE INTO tasks (id,ordinal,fingerprint,input,state,updated) "
                    "VALUES (?,?,?,?,?,?)",
                    (q.question_id, i, q.fingerprint, q.model_dump_json(), "pending", now()),
                )

    def recover(self):
        # Caller must hold the process lock. No live workers can be reset by a second CLI.
        with self.transaction() as c:
            c.execute(
                "UPDATE attempts SET outcome='interrupted',ended=? WHERE outcome='running'",
                (now(),),
            )
            c.execute("UPDATE tasks SET state='pending',updated=? WHERE state='running'", (now(),))

    def pending(self, limit, retry_failed=False):
        states = ("pending", "failed") if retry_failed else ("pending",)
        with self.connect() as c:
            return [
                r[0]
                for r in c.execute(
                    "SELECT id FROM tasks WHERE state IN ("
                    + ",".join("?" for _ in states)
                    + ") ORDER BY ordinal LIMIT ?",
                    (*states, limit),
                )
            ]

    def start(self, task_id):
        with self.transaction() as c:
            r = c.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
            if r["state"] not in ("pending", "failed"):
                raise Conflict("Task already running or completed")
            c.execute(
                "UPDATE tasks SET state='running',attempts=attempts+1,updated=? WHERE id=?",
                (now(), task_id),
            )
            c.execute(
                "INSERT INTO attempts (question_id,attempt,started,outcome) VALUES (?,?,?,?)",
                (task_id, r["attempts"] + 1, now(), "running"),
            )
            return Question.model_validate_json(r["input"])

    def step(self, task_id, name, signature, fn, schema):
        signature = digest(signature)
        with self.connect() as c:
            old = c.execute(
                "SELECT * FROM steps WHERE task_id=? AND name=?", (task_id, name)
            ).fetchone()
        if old:
            if old["signature"] != signature:
                raise Conflict(f"Checkpoint input changed: {name}")
            return schema.model_validate_json(old["value"])
        result = schema.model_validate(fn())
        with self.transaction() as c:
            c.execute(
                "INSERT INTO steps VALUES (?,?,?,?)",
                (task_id, name, signature, result.model_dump_json()),
            )
        return result

    def finish(self, result):
        with self.transaction() as c:
            c.execute(
                "UPDATE tasks SET state='researched',result=?,error=NULL,updated=? WHERE id=?",
                (result.model_dump_json(), now(), result.question_id),
            )
            c.execute(
                "INSERT OR IGNORE INTO events VALUES (?,?,?,?,?)",
                (result.event_id, result.question_id, result.model_dump_json(), "pending", now()),
            )
            original = c.execute(
                "SELECT input FROM tasks WHERE id=?", (result.question_id,)
            ).fetchone()
            q = Question.model_validate_json(original[0])
            audit = {
                "event_id": result.event_id,
                "question_id": q.question_id,
                "original_fingerprint": q.fingerprint,
                "original_answer": q.answer,
                "proposed_answer": result.proposal.corrected_answer,
                "original_metric": q.metric,
                "proposed_metric": result.metric.primary_metric,
                "reason": result.proposal.explanation,
                "source_urls": [s.url for s in result.sources if s.status == "ok"],
                "agent": result.judge_model,
                "human_approval": "",
                "independent_ai_audit": "",
                "created_at": result.created_at,
            }
            if hasattr(result, "baseline_event_id"):
                audit["baseline_event_id"] = result.baseline_event_id
                audit["research_version"] = 2
                audit["reference_status"] = result.reference_status
            c.execute(
                "INSERT OR IGNORE INTO audit VALUES (?,?,?,?)",
                (result.event_id, q.question_id, json.dumps(audit), now()),
            )
            for claim in result.claims:
                c.execute(
                    "INSERT INTO claim_results VALUES (?,?,?,?)",
                    (claim.claim_id, q.question_id, result.event_id, claim.model_dump_json()),
                )
            c.execute(
                "INSERT INTO corrected_answers VALUES (?,?,?,0)",
                (result.event_id, q.question_id, result.proposal.corrected_answer),
            )
            c.execute(
                "UPDATE attempts SET outcome='researched',ended=? "
                "WHERE question_id=? AND outcome='running'",
                (now(), q.question_id),
            )

    def fail(self, task_id, error):
        with self.transaction() as c:
            c.execute(
                "UPDATE tasks SET state='failed',error=?,updated=? WHERE id=?",
                (error, now(), task_id),
            )
            c.execute(
                "UPDATE attempts SET outcome='failed',error=?,ended=? "
                "WHERE question_id=? AND outcome='running'",
                (error, now(), task_id),
            )

    def bind_model(self, model):
        with self.transaction() as c:
            old = c.execute("SELECT value FROM metadata WHERE key='judge_model'").fetchone()
            if old and old[0] != model:
                raise Conflict("Resolved judge model changed; use a new database")
            c.execute("INSERT OR IGNORE INTO metadata VALUES ('judge_model',?)", (model,))

    def results(self):
        with self.connect() as c:
            return [
                (r["id"], research_from_json(r["payload"]))
                for r in c.execute("SELECT * FROM events ORDER BY rowid")
            ]

    def audits(self):
        with self.connect() as c:
            return [json.loads(r[0]) for r in c.execute("SELECT payload FROM audit ORDER BY rowid")]

    def source_get(self, key):
        from .models import Source

        with self.connect() as c:
            row = c.execute("SELECT payload FROM sources WHERE cache_key=?", (key,)).fetchone()
        return Source.model_validate_json(row[0]) if row else None

    def source_put(self, key, source):
        with self.transaction() as c:
            c.execute(
                "INSERT OR REPLACE INTO sources VALUES (?,?,?)",
                (key, source.url, source.model_dump_json()),
            )

    def archives(self, url):
        from .models import Source

        with self.connect() as c:
            return [
                Source.model_validate_json(r[0])
                for r in c.execute(
                    "SELECT payload FROM sources WHERE url=? AND cache_key LIKE 'warc:%'", (url,)
                )
            ]

    def report(self):
        with self.connect() as c:
            states = dict(c.execute("SELECT state,count(*) FROM tasks GROUP BY state").fetchall())
            results = [
                json.loads(r[0])
                for r in c.execute("SELECT result FROM tasks WHERE result IS NOT NULL")
            ]
            return {
                "states": states,
                "total": sum(states.values()),
                "fully_supported": sum(r["fully_supported"] for r in results),
                "dispositions": {
                    d: sum(r["proposal"]["disposition"] == d for r in results)
                    for d in ("accept", "revise", "reject", "unresolved", "needs_more_evidence")
                },
                "failures": [
                    dict(r)
                    for r in c.execute(
                        "SELECT id,state,attempts,error FROM tasks WHERE error IS NOT NULL"
                    )
                ],
            }

    def check_integrity(self):
        """Reject progress/status drift and incomplete writes before creating an import package."""
        from .gates import extraction_errors

        with self.connect() as c:
            rows = c.execute("SELECT * FROM tasks").fetchall()
            researched = [r for r in rows if r["state"] == "researched"]
            for table in ("events", "audit", "corrected_answers"):
                if c.execute("SELECT count(*) FROM " + table).fetchone()[0] != len(researched):
                    raise Conflict(f"Progress count inconsistent with {table}")
            for row in rows:
                if row["state"] not in {"pending", "running", "researched", "failed"}:
                    raise Conflict("Invalid processing status")
                if (row["result"] is not None) != (row["state"] == "researched"):
                    raise Conflict("Result/status inconsistency")
            for row in researched:
                result = research_from_json(row["result"])
                q = Question.model_validate_json(row["input"])
                event = c.execute(
                    "SELECT payload FROM events WHERE id=? AND task_id=?",
                    (result.event_id, q.question_id),
                ).fetchone()
                audit = c.execute(
                    "SELECT payload FROM audit WHERE event_id=? AND question_id=?",
                    (result.event_id, q.question_id),
                ).fetchone()
                if not event or event[0] != row["result"] or not audit:
                    raise Conflict("Research event/audit inconsistency")
                if result.input_fingerprint != q.fingerprint:
                    raise Conflict("Research input fingerprint mismatch")
                if result.fully_supported and extraction_errors(
                    q.answer, result.extraction, result.coverage
                ):
                    raise Conflict("Supported answer has invalid claim coverage")
                count = c.execute(
                    "SELECT count(*) FROM claim_results WHERE event_id=?", (result.event_id,)
                ).fetchone()[0]
                if count != len(result.claims):
                    raise Conflict("Progress count inconsistent with claim records")


@contextmanager
def process_lock(path):
    """Kernel lock releases after termination; lock file can safely remain on disk."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as f:
        try:
            if __import__("os").fstat(f.fileno()).st_size == 0:
                f.write(b"0")
                f.flush()
            f.seek(0)
            if __import__("os").name == "nt":
                import msvcrt

                msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise Conflict("Another process is using this database") from None
        try:
            yield
        finally:
            f.seek(0)
            if __import__("os").name == "nt":
                msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(f, fcntl.LOCK_UN)
