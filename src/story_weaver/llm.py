from __future__ import annotations

import json
from abc import ABC, abstractmethod

from story_weaver.models import (
    Chapter,
    CreateGameRequest,
    DirectorDecision,
    GameState,
    NPC,
    NPCGeneration,
    NPCReply,
    WorldSpec,
)
from story_weaver.prompts import DIRECTOR_PROMPT, NPC_PROMPT, WORLD_PROMPT


class NarrativeModel(ABC):
    @abstractmethod
    def build_world(self, request: CreateGameRequest) -> WorldSpec: ...

    @abstractmethod
    def direct(
        self,
        state: GameState,
        player_action: str,
        replies: list[NPCReply],
        max_replies: int,
    ) -> DirectorDecision: ...

    @abstractmethod
    def play_npc(
        self,
        state: GameState,
        npc: NPC,
        player_action: str,
        replies: list[NPCReply],
    ) -> NPCGeneration: ...


class MockNarrativeModel(NarrativeModel):
    """Deterministic local model so the backend works without an API key."""

    def build_world(self, request: CreateGameRequest) -> WorldSpec:
        magical = any(token in request.scene.lower() for token in ("魔法", "巫师", "magic", "wizard"))
        profiles = (
            (
                "塞拉教授" if magical else "艾琳",
                "guide",
                "A patient mentor who answers with riddles and values courage over obedience.",
                "Test whether the player can make decisions without relying on authority.",
                "The safest-looking passage is an illusion.",
            ),
            (
                "诺克斯" if magical else "罗文",
                "rival",
                "A proud rival who challenges weak plans but respects evidence.",
                "Reach the final chamber before the player without becoming a villain.",
                "They secretly removed one seal to protect another student.",
            ),
            (
                "石像守卫奥伦" if magical else "守门人奥伦",
                "guardian",
                "A literal-minded guardian who only responds to precise questions.",
                "Keep unprepared explorers away from the sealed route.",
                "The gate reacts to a spoken promise rather than a physical key.",
            ),
            (
                "米拉" if magical else "米拉",
                "witness",
                "An anxious witness who notices tiny details and distrusts the guide.",
                "Reveal the truth without exposing their own forbidden visit.",
                "They saw the rival return from the restricted corridor at midnight.",
            ),
            (
                "芬奇" if magical else "芬奇",
                "trickster",
                "A playful opportunist who trades information for interesting favors.",
                "Turn the expedition into a story that makes them famous.",
                "One of their jokes accidentally reveals the correct rune order.",
            ),
            (
                "维尔档案官" if magical else "维尔学者",
                "scholar",
                "A meticulous scholar who trusts records more than eyewitnesses.",
                "Recover a missing page before anyone damages it.",
                "The official history deliberately reverses the second and third trials.",
            ),
            (
                "露西亚" if magical else "露西亚",
                "healer",
                "A calm healer who reads fear through body language.",
                "Keep the group together even when their goals conflict.",
                "The artifact amplifies intention, not magical strength.",
            ),
            (
                "灰斗篷旅人" if magical else "灰衣旅人",
                "outsider",
                "A courteous outsider who knows too much and never gives a direct reason for being here.",
                "Confirm whether the player deserves the artifact.",
                "They once reached the final chamber and chose to leave empty-handed.",
            ),
        )
        chapters = []
        locations = (
            "the whispering entrance hall",
            "the rotating archive",
            "the moonlit trial chamber",
            "the sealed observatory",
            "the underground mirror lake",
            "the final vault",
        )
        for index in range(request.chapter_count):
            final = index == request.chapter_count - 1
            chapters.append(
                Chapter(
                    id=f"chapter-{index + 1}",
                    title=("The Final Trial" if final else f"Clue {index + 1}"),
                    objective=(request.final_goal if final else f"Discover the truth behind clue {index + 1}"),
                    completion_condition=(
                        f"The player explicitly succeeds at: {request.final_goal}"
                        if final
                        else f"At least one NPC reveals the key clue for stage {index + 1}"
                    ),
                    allowed_locations=[locations[index]],
                )
            )
        npcs = []
        for index in range(request.npc_count):
            name, role, persona, motivation, secret = profiles[index]
            npcs.append(
                NPC(
                    id=f"npc-{index + 1}",
                    name=name,
                    role=role,
                    persona=persona,
                    motivation=motivation,
                    secret=secret,
                )
            )
        return WorldSpec(
            title="The Shifting Quest",
            premise=request.scene,
            player_role="the newcomer whose choices determine the route",
            tone=request.tone,
            rules=[
                "NPCs cannot contradict established facts.",
                "Chapters advance only when their completion condition is met.",
                "The story must end at one of the declared endings.",
            ],
            chapters=chapters,
            npcs=npcs,
            final_goal=request.final_goal,
            endings=[f"Success: {request.final_goal}", "The player withdraws before completing the quest"],
        )

    def direct(
        self,
        state: GameState,
        player_action: str,
        replies: list[NPCReply],
        max_replies: int,
    ) -> DirectorDecision:
        action = player_action.lower()
        should_advance = any(token in action for token in ("成功", "完成", "找到", "solve", "found", "complete"))
        candidates = state.active_npc_ids[:max_replies]
        return DirectorDecision(
            speaker_ids=candidates,
            reason="These NPCs offer distinct perspectives on the current beat.",
            should_advance=should_advance,
        )

    def play_npc(
        self,
        state: GameState,
        npc: NPC,
        player_action: str,
        replies: list[NPCReply],
    ) -> NPCGeneration:
        chapter = state.current_chapter
        location = chapter.allowed_locations[0]
        performances = {
            "guide": (
                "draws a broken map, leaving one route deliberately unmarked",
                f'“I will not choose for you. Tell me why you believe the route through {location} is safe.”',
                "measured",
            ),
            "rival": (
                "steps between the player and the door, holding up a scorched clue",
                f'“Asking is easy. I already tested one entrance to {location}, and it nearly trapped me.”',
                "competitive",
            ),
            "guardian": (
                "remains motionless while the symbols across the gate begin to glow",
                '“A key opens a lock. This threshold opens only for a promise. State yours precisely.”',
                "unyielding",
            ),
            "witness": (
                "checks the corridor twice, then slips a charcoal rubbing onto the table",
                '“Keep your voice down. Someone changed these markings after midnight.”',
                "anxious",
            ),
            "trickster": (
                "flips a silver token across their knuckles and grins",
                '“I know where your clue went. The interesting question is what you will trade for it.”',
                "amused",
            ),
            "scholar": (
                "opens a weathered ledger to a page whose numbering has been altered",
                '“Ignore the legend everyone repeats. The archive says the trials were recorded out of order.”',
                "intent",
            ),
            "healer": (
                "studies the group rather than the passage ahead",
                '“The chamber responds to intention. If one of us lies, no key will protect us.”',
                "concerned",
            ),
            "outsider": (
                "turns an old scar toward the light, then covers it again",
                '“I reached the end once. Finding the artifact was simpler than deciding whether to take it.”',
                "cryptic",
            ),
        }
        action, speech, emotion = performances[npc.role]
        fact = f"{npc.name}'s clue for {chapter.title}: {npc.secret}"
        return NPCGeneration(
            speech=speech,
            action=f"{npc.name} {action}.",
            emotion=emotion,
            revealed_fact=fact,
            relationship_delta=1,
        )


class LangChainNarrativeModel(NarrativeModel):
    def __init__(self, model_name: str, api_key: str | None = None, base_url: str | None = None) -> None:
        try:
            from langchain_openai import ChatOpenAI
        except ImportError as exc:
            raise RuntimeError("Install the OpenAI extra: pip install -e '.[openai]'") from exc
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is required when STORY_MODEL_PROVIDER=openai")
        self.model = ChatOpenAI(
            model=model_name,
            api_key=api_key,
            base_url=base_url,
            temperature=0.8,
            timeout=45,
            max_retries=1,
        )

    def _structured(self, schema: type, prompt: str):
        return self.model.with_structured_output(schema).invoke(prompt)

    def build_world(self, request: CreateGameRequest) -> WorldSpec:
        prompt = WORLD_PROMPT.format(**request.model_dump())
        return self._structured(WorldSpec, prompt)

    def direct(
        self,
        state: GameState,
        player_action: str,
        replies: list[NPCReply],
        max_replies: int,
    ) -> DirectorDecision:
        if len(replies) >= max_replies:
            return DirectorDecision(reason="Turn reply limit reached.", should_end_turn=True)
        prompt = DIRECTOR_PROMPT.format(
            world=json.dumps(state.world.model_dump(mode="json"), ensure_ascii=False),
            chapter=json.dumps(state.current_chapter.model_dump(), ensure_ascii=False),
            active_npc_ids=state.active_npc_ids,
            player_action=player_action,
            max_replies=max_replies,
            memory=self._memory(state),
        )
        decision = self._structured(DirectorDecision, prompt)
        active_ids = set(state.active_npc_ids)
        decision.speaker_ids = list(
            dict.fromkeys(npc_id for npc_id in decision.speaker_ids if npc_id in active_ids)
        )[:max_replies]
        # 玩家每次行动后至少要有一个 NPC 回应，禁止空回合。
        if not decision.speaker_ids and state.active_npc_ids:
            decision.speaker_ids = state.active_npc_ids[:1]
        if decision.speaker_ids:
            decision.should_end_turn = False
        return decision

    def play_npc(
        self,
        state: GameState,
        npc: NPC,
        player_action: str,
        replies: list[NPCReply],
    ) -> NPCGeneration:
        prompt = NPC_PROMPT.format(
            premise=state.world.premise,
            final_goal=state.world.final_goal,
            chapter=json.dumps(state.current_chapter.model_dump(), ensure_ascii=False),
            npc=json.dumps(npc.model_dump(), ensure_ascii=False),
            player_action=player_action,
            replies=json.dumps([reply.model_dump() for reply in replies], ensure_ascii=False),
            memory=self._memory(state),
        )
        return self._structured(NPCGeneration, prompt)

    @staticmethod
    def _memory(state: GameState) -> str:
        return json.dumps(
            [event.model_dump(mode="json") for event in state.recent_events[-12:]],
            ensure_ascii=False,
        )


def create_model(
    provider: str,
    model_name: str,
    api_key: str | None = None,
    base_url: str | None = None,
) -> NarrativeModel:
    if provider == "mock":
        return MockNarrativeModel()
    if provider == "openai":
        return LangChainNarrativeModel(model_name, api_key)
    if provider == "qwen":
        if not api_key:
            raise RuntimeError("DASHSCOPE_API_KEY is required when STORY_MODEL_PROVIDER=qwen")
        return LangChainNarrativeModel(model_name, api_key, base_url)
    raise ValueError(f"Unsupported STORY_MODEL_PROVIDER: {provider}")
