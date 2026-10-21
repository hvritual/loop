"""Transactional snapshots, idempotency and a verifiable local event journal."""
from __future__ import annotations

import hmac
from contextlib import closing
import json
import secrets
import sqlite3
import time
from pathlib import Path

from .model import ROLES, Rejected, digest, encode, identifier, policy_contract, require


class Store:
    def __init__(self, root, token, clock=time.time):
        self.root = Path(root).resolve()
        self.clock = clock
        require((self.root / "runtime.sqlite3").is_file(), "runtime not initialized")
        authority = json.loads((self.root / "authority.json").read_text())
        self.role = next((role for role, hashed in authority.items() if hmac.compare_digest(digest(token.strip()), hashed)), None)
        require(self.role is not None, "invalid credential")
        self.db = sqlite3.connect(self.root / "runtime.sqlite3", timeout=10, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.execute("PRAGMA synchronous=FULL")

    @staticmethod
    def initialize(root, policy):
        policy_contract(policy)
        root = Path(root).resolve()
        require(not root.exists(), "refusing to overwrite runtime directory")
        root.mkdir(parents=True, mode=0o700)
        (root / ".credentials").mkdir(mode=0o700)
        (root / "evidence").mkdir()
        (root / "work").mkdir()
        authority = {}
        for role in ROLES:
            token = secrets.token_urlsafe(32)
            p = root / ".credentials" / (role + ".token")
            p.write_text(token + "\n")
            p.chmod(0o600)
            authority[role] = digest(token)
        (root / "authority.json").write_text(encode(authority))
        (root / "authority.json").chmod(0o600)
        (root / "policy.json").write_text(encode(policy))
        with closing(sqlite3.connect(root / "runtime.sqlite3")) as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE intents(id TEXT PRIMARY KEY, state TEXT NOT NULL);
                CREATE TABLE events(seq INTEGER PRIMARY KEY AUTOINCREMENT, intent TEXT NOT NULL,
                    revision INTEGER NOT NULL, payload TEXT NOT NULL, previous TEXT NOT NULL,
                    hash TEXT NOT NULL, state_hash TEXT NOT NULL, UNIQUE(intent, revision));
                CREATE TABLE idempotency(intent TEXT, key TEXT, request_hash TEXT, result TEXT,
                    PRIMARY KEY(intent, key));
            """)
        return {"root": str(root), "credentials": str(root / ".credentials"), "policy_hash": digest(policy)}

    def close(self):
        self.db.close()

    def policy(self):
        return policy_contract(json.loads((self.root / "policy.json").read_text()))

    def get(self, intent):
        identifier(intent)
        row = self.db.execute("SELECT state FROM intents WHERE id=?", (intent,)).fetchone()
        require(row is not None, "unknown intent")
        state = json.loads(row["state"])
        last = self.db.execute("SELECT state_hash FROM events WHERE intent=? ORDER BY revision DESC LIMIT 1", (intent,)).fetchone()
        require(last and hmac.compare_digest(last["state_hash"], digest(state)), "snapshot integrity failure")
        require(state["policy_hash"] == digest(self.policy()), "policy drift: restore the pinned policy; do not self-approve edits")
        return state

    def mutate(self, intent, key, expected, action, data, apply):
        identifier(intent)
        identifier(key)
        request_hash = digest({"role": self.role, "action": action, "data": data})
        self.db.execute("BEGIN IMMEDIATE")
        try:
            old = self.db.execute("SELECT * FROM idempotency WHERE intent=? AND key=?", (intent, key)).fetchone()
            if old:
                require(hmac.compare_digest(old["request_hash"], request_hash), "idempotency key reused for a different request")
                self.db.execute("COMMIT")
                return json.loads(old["result"])
            exists = self.db.execute("SELECT 1 FROM intents WHERE id=?", (intent,)).fetchone()
            state = self.get(intent) if exists else None
            revision = state["revision"] if state else 0
            require(type(expected) is int and expected == revision, "revision conflict; reload before retry")
            result = apply(state)
            result["revision"] = revision + 1
            result["updated_at"] = self.clock()
            payload = {"action": action, "actor": self.role, "data": data, "at": self.clock(), "revision": result["revision"]}
            previous = self.db.execute("SELECT hash FROM events WHERE intent=? ORDER BY revision DESC LIMIT 1", (intent,)).fetchone()
            previous = previous["hash"] if previous else "0" * 64
            state_hash = digest(result)
            event_hash = digest({"previous": previous, "payload": payload, "state_hash": state_hash})
            self.db.execute("INSERT OR REPLACE INTO intents VALUES(?,?)", (intent, encode(result)))
            self.db.execute("INSERT INTO events(intent,revision,payload,previous,hash,state_hash) VALUES(?,?,?,?,?,?)",
                            (intent, result["revision"], encode(payload), previous, event_hash, state_hash))
            self.db.execute("INSERT INTO idempotency VALUES(?,?,?,?)", (intent, key, request_hash, encode(result)))
            self.db.execute("COMMIT")
            return result
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def audit(self, intent):
        state = self.get(intent)
        rows = self.db.execute("SELECT * FROM events WHERE intent=? ORDER BY revision", (intent,)).fetchall()
        previous = "0" * 64
        events = []
        for expected, row in enumerate(rows, 1):
            payload = json.loads(row["payload"])
            require(row["revision"] == expected and row["previous"] == previous, "audit sequence failure")
            require(row["hash"] == digest({"previous": previous, "payload": payload, "state_hash": row["state_hash"]}), "audit hash failure")
            previous = row["hash"]
            events.append(dict(row))
        require(len(events) == state["revision"], "truncated audit")
        return events
