#!/usr/bin/env python3
"""HTTP API поверх той же tasks.db, что использует todo.py."""
import os
import sqlite3
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

DB_DIR = Path(os.environ.get("TODO_DB_DIR", Path(__file__).resolve().parent))
DB_PATH = DB_DIR / "tasks.db"

app = FastAPI(title="Todo API", version="0.1.0")


def get_con() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            title    TEXT    NOT NULL,
            priority INTEGER NOT NULL DEFAULT 2,
            done     INTEGER NOT NULL DEFAULT 0,
            created  TEXT    NOT NULL
        )
    """)
    con.commit()
    return con


class TaskIn(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    priority: int = Field(2, ge=1, le=3)


class TaskPatch(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=200)
    priority: int | None = Field(None, ge=1, le=3)
    done: bool | None = None


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.get("/tasks")
def list_tasks():
    with get_con() as con:
        rows = con.execute(
            "SELECT id, title, priority, done, created FROM tasks "
            "ORDER BY done ASC, priority DESC, id ASC"
        ).fetchall()
    return [dict(r) for r in rows]


@app.post("/tasks", status_code=201)
def create_task(task: TaskIn):
    with get_con() as con:
        cur = con.execute(
            "INSERT INTO tasks (title, priority, done, created) VALUES (?, ?, 0, ?)",
            (task.title, task.priority, datetime.now().isoformat(timespec="seconds")),
        )
        con.commit()
        new_id = cur.lastrowid
        row = con.execute("SELECT * FROM tasks WHERE id = ?", (new_id,)).fetchone()
    return dict(row)


@app.patch("/tasks/{task_id}")
def update_task(task_id: int, patch: TaskPatch):
    fields, values = [], []
    if patch.title is not None:
        fields.append("title = ?")
        values.append(patch.title)
    if patch.priority is not None:
        fields.append("priority = ?")
        values.append(patch.priority)
    if patch.done is not None:
        fields.append("done = ?")
        values.append(1 if patch.done else 0)
    if not fields:
        raise HTTPException(400, "nothing to update")
    values.append(task_id)
    with get_con() as con:
        cur = con.execute(f"UPDATE tasks SET {', '.join(fields)} WHERE id = ?", values)
        con.commit()
        if cur.rowcount == 0:
            raise HTTPException(404, "task not found")
        row = con.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    return dict(row)


@app.delete("/tasks/{task_id}", status_code=204)
def delete_task(task_id: int):
    with get_con() as con:
        cur = con.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        con.commit()
        if cur.rowcount == 0:
            raise HTTPException(404, "task not found")
    return None
