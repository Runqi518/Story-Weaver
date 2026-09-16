from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class GameStatus(str, Enum):
    READY = "ready"
    PLAYING = "playing"
    COMPLETED = "completed"


class Chapter(BaseModel):
    id: str
    title: str
    objective: str
    completion_condition: str
    allowed_locations: list[str] = Field(default_factory=list)


class NPC(BaseModel):
    id: str
    name: str
    role: str
    persona: str
    motivation: str
    secret: str
    current_mood: str = "neutral"
    relationship_to_player: int = Field(default=0, ge=-100, le=100)
    active: bool = True


class WorldSpec(BaseModel):
    title: str
    premise: str
    player_role: str
    tone: str
    rules: list[str]
    chapters: list[Chapter] = Field(min_length=1)
    npcs: list[NPC] = Field(min_length=1)
    final_goal: str
    endings: list[str] = Field(min_length=1)


class MemoryEvent(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    kind: Literal["system", "player", "npc", "state_transition"]
    actor_id: str | None = None
    content: str
    chapter_id: str
    turn: int
    important: bool = False
    created_at: datetime = Field(default_factory=utc_now)


class GameState(BaseModel):
    game_id: str = Field(default_factory=lambda: str(uuid4()))
    status: GameStatus = GameStatus.READY
    world: WorldSpec
    current_chapter_index: int = 0
    current_location: str = "opening scene"
    turn: int = 0
    active_npc_ids: list[str] = Field(default_factory=list)
    facts: list[str] = Field(default_factory=list)
    recent_events: list[MemoryEvent] = Field(default_factory=list)
    ending: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    @property
    def current_chapter(self) -> Chapter:
        return self.world.chapters[self.current_chapter_index]


class CreateGameRequest(BaseModel):
    scene: str = Field(min_length=3, max_length=2000)
    final_goal: str = Field(min_length=2, max_length=500)
    tone: str = Field(default="adventure", max_length=100)
    npc_count: int = Field(default=4, ge=2, le=8)
    chapter_count: int = Field(default=3, ge=1, le=6)


class PlayerTurnRequest(BaseModel):
    action: str = Field(min_length=1, max_length=2000)


class NPCReply(BaseModel):
    npc_id: str
    npc_name: str
    speech: str
    action: str
    emotion: str
    revealed_fact: str | None = None
    relationship_delta: int = Field(default=0, exclude=True)


class DirectorDecision(BaseModel):
    speaker_ids: list[str] = Field(default_factory=list)
    reason: str
    should_advance: bool = False
    should_end_turn: bool = False


class NPCGeneration(BaseModel):
    speech: str
    action: str
    emotion: str
    revealed_fact: str | None = None
    relationship_delta: int = Field(default=0, ge=-20, le=20)
    next_speaker_id: str | None = None


class TurnResponse(BaseModel):
    game_id: str
    turn: int
    chapter: Chapter
    replies: list[NPCReply]
    status: GameStatus
    ending: str | None = None


class GameView(BaseModel):
    game_id: str
    status: GameStatus
    world: WorldSpec
    current_chapter: Chapter
    current_location: str
    turn: int
    active_npcs: list[NPC]
    recent_events: list[MemoryEvent]
    ending: str | None = None

    @model_validator(mode="after")
    def validate_active_npcs(self) -> GameView:
        return self
