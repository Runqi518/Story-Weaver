from __future__ import annotations

import sqlite3
from pathlib import Path

from story_weaver.models import GameState


class GameRepository:
    def __init__(self, database_path: str) -> None:
        self.database_path = database_path
        if database_path != ":memory:":
            Path(database_path).parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(database_path, check_same_thread=False)
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS games (
                id TEXT PRIMARY KEY,
                state_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        self._connection.commit()

    def save(self, state: GameState) -> None:
        self._connection.execute(
            """
            INSERT INTO games(id, state_json, updated_at) VALUES (?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET state_json=excluded.state_json, updated_at=excluded.updated_at
            """,
            (state.game_id, state.model_dump_json(), state.updated_at.isoformat()),
        )
        self._connection.commit()

    def get(self, game_id: str) -> GameState | None:
        row = self._connection.execute("SELECT state_json FROM games WHERE id = ?", (game_id,)).fetchone()
        return GameState.model_validate_json(row[0]) if row else None

    def close(self) -> None:
        self._connection.close()
