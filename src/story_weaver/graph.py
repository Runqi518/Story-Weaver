from __future__ import annotations

import operator
from typing import Annotated, Optional, Sequence, TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

from story_weaver.llm import NarrativeModel
from story_weaver.models import DirectorDecision, GameState, NPCReply


class TurnGraphState(TypedDict):
    game: GameState
    player_action: str
    replies: Annotated[list[NPCReply], operator.add]
    decision: Optional[DirectorDecision]
    messages: Annotated[list, add_messages]


class NarrativeGraph:
    def __init__(self, model: NarrativeModel, max_replies: int) -> None:
        self.model = model
        self.max_replies = max_replies
        self.checkpointer = MemorySaver()

    def compile_for(self, game: GameState):
        builder = StateGraph(TurnGraphState)
        builder.add_node("director", self._director)
        builder.add_edge(START, "director")
        route_map = {"finish": END}

        for npc in game.world.npcs:
            node_name = npc.id
            builder.add_node(node_name, self._npc_node(npc.id))
            builder.add_edge(node_name, END)
            route_map[node_name] = node_name

        builder.add_conditional_edges("director", self._route, route_map)
        return builder.compile(checkpointer=self.checkpointer)

    def _director(self, graph_state: TurnGraphState) -> dict:
        decision = self.model.direct(
            graph_state["game"],
            graph_state["player_action"],
            graph_state["replies"],
            self.max_replies,
        )
        return {"decision": decision}

    @staticmethod
    def _route(graph_state: TurnGraphState) -> str | Sequence[str]:
        decision = graph_state["decision"]
        if decision is None or decision.should_end_turn or not decision.speaker_ids:
            return "finish"
        return decision.speaker_ids

    def _npc_node(self, npc_id: str):
        def run(graph_state: TurnGraphState) -> dict:
            game = graph_state["game"]
            npc = next(npc for npc in game.world.npcs if npc.id == npc_id)
            generated = self.model.play_npc(
                game,
                npc,
                graph_state["player_action"],
                graph_state["replies"],
            )
            reply = NPCReply(
                npc_id=npc.id,
                npc_name=npc.name,
                speech=generated.speech,
                action=generated.action,
                emotion=generated.emotion,
                revealed_fact=generated.revealed_fact,
                relationship_delta=generated.relationship_delta,
            )
            return {"replies": [reply]}

        return run
