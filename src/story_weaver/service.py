from __future__ import annotations

from datetime import datetime, timezone

from story_weaver.graph import NarrativeGraph
from story_weaver.llm import NarrativeModel
from story_weaver.models import (
    CreateGameRequest,
    GameState,
    GameStatus,
    GameView,
    MemoryEvent,
    NPCReply,
    PlayerTurnRequest,
    TurnResponse,
)
from story_weaver.repository import GameRepository


class GameNotFoundError(Exception):
    pass


class InvalidGameStateError(Exception):
    pass


class GameService:
    def __init__(self, repository: GameRepository, model: NarrativeModel, max_replies: int = 3) -> None:
        self.repository = repository
        self.model = model
        self.graph = NarrativeGraph(model, max_replies)

    def create_game(self, request: CreateGameRequest) -> GameView:
        world = self.model.build_world(request)
        state = GameState(
            world=world,
            current_location=world.chapters[0].allowed_locations[0] if world.chapters[0].allowed_locations else "opening",
            active_npc_ids=[npc.id for npc in world.npcs[: min(3, len(world.npcs))]],
        )
        self._remember(state, "system", f"World created: {world.premise}", important=True)
        self.repository.save(state)
        return self._view(state)

    def start_game(self, game_id: str) -> TurnResponse:
        state = self._get(game_id)
        if state.status != GameStatus.READY:
            raise InvalidGameStateError("Game has already started.")
        state.status = GameStatus.PLAYING
        self._touch(state)
        self.repository.save(state)
        return self.play_turn(game_id, PlayerTurnRequest(action="enter the scene and observe"))

    def play_turn(self, game_id: str, request: PlayerTurnRequest) -> TurnResponse:
        state = self._get(game_id)
        if state.status != GameStatus.PLAYING:
            raise InvalidGameStateError("Game is not currently playing.")
        state.turn += 1
        self._remember(state, "player", request.action, actor_id="player", important=True)

        app = self.graph.compile_for(state)
        try:
            result = app.invoke(
                {
                    "game": state,
                    "player_action": request.action,
                    "replies": [],
                    "decision": None,
                    "messages": [],
                },
                config={"configurable": {"thread_id": f"{game_id}:{state.turn}"}},
            )
        except Exception:
            result = {"game": state, "replies": [], "decision": None}
        state = result.get("game", state)
        replies = result["replies"]
        # 最终保险：任何原因导致空回合时，强制让第一个活跃 NPC 直接回应玩家。
        if not replies and state.active_npc_ids:
            fallback_npc = next(
                npc for npc in state.world.npcs if npc.id == state.active_npc_ids[0]
            )
            generated = self.model.play_npc(state, fallback_npc, request.action, [])
            replies = [
                NPCReply(
                    npc_id=fallback_npc.id,
                    npc_name=fallback_npc.name,
                    speech=generated.speech,
                    action=generated.action,
                    emotion=generated.emotion,
                    revealed_fact=generated.revealed_fact,
                    relationship_delta=generated.relationship_delta,
                )
            ]
        for reply in replies:
            npc = next(npc for npc in state.world.npcs if npc.id == reply.npc_id)
            npc.relationship_to_player = max(
                -100,
                min(100, npc.relationship_to_player + reply.relationship_delta),
            )
            content = f"{reply.action}\n{reply.speech}"
            self._remember(state, "npc", content, actor_id=reply.npc_id, important=bool(reply.revealed_fact))
            if reply.revealed_fact and reply.revealed_fact not in state.facts:
                state.facts.append(reply.revealed_fact)

        decision = result.get("decision")
        if decision and decision.should_advance:
            self._advance(state)
        self._touch(state)
        self.repository.save(state)
        return TurnResponse(
            game_id=state.game_id,
            turn=state.turn,
            chapter=state.current_chapter,
            replies=replies,
            status=state.status,
            ending=state.ending,
        )

    def get_game(self, game_id: str) -> GameView:
        return self._view(self._get(game_id))

    def _advance(self, state: GameState) -> None:
        previous = state.current_chapter
        if state.current_chapter_index == len(state.world.chapters) - 1:
            state.status = GameStatus.COMPLETED
            state.ending = state.world.endings[0]
            self._remember(state, "state_transition", f"Completed: {state.ending}", important=True)
            return
        state.current_chapter_index += 1
        current = state.current_chapter
        state.current_location = current.allowed_locations[0] if current.allowed_locations else state.current_location
        self._remember(
            state,
            "state_transition",
            f"Advanced from {previous.title} to {current.title}",
            important=True,
        )

    def _remember(
        self,
        state: GameState,
        kind: str,
        content: str,
        actor_id: str | None = None,
        important: bool = False,
    ) -> None:
        state.recent_events.append(
            MemoryEvent(
                kind=kind,
                actor_id=actor_id,
                content=content,
                chapter_id=state.current_chapter.id,
                turn=state.turn,
                important=important,
            )
        )
        state.recent_events = state.recent_events[-50:]

    def _get(self, game_id: str) -> GameState:
        state = self.repository.get(game_id)
        if state is None:
            raise GameNotFoundError(game_id)
        return state

    @staticmethod
    def _touch(state: GameState) -> None:
        state.updated_at = datetime.now(timezone.utc)

    @staticmethod
    def _view(state: GameState) -> GameView:
        active = [npc for npc in state.world.npcs if npc.id in state.active_npc_ids]
        return GameView(
            game_id=state.game_id,
            status=state.status,
            world=state.world,
            current_chapter=state.current_chapter,
            current_location=state.current_location,
            turn=state.turn,
            active_npcs=active,
            recent_events=state.recent_events[-20:],
            ending=state.ending,
        )
