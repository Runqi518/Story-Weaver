# Story Weaver

LLM 驱动的多 NPC 交互叙事。初始目标被编译为章节骨架，LLM 在每回合生成 NPC 行为和剧情细节。

## Architecture

- Bottom layer: `WorldSpec` 和 `Chapter` 构成受控剧情状态机。
- Middle layer: 每个 NPC 是 LangGraph 节点，节点执行独立角色提示词。
- Top layer: `director` 节点单次规划本轮接话 NPC 或推进章节，NPC 节点并行生成回复。
- Memory layer: LangGraph checkpointer 保存单次图执行，SQLite 保存游戏状态、事实和事件历史。
- Model layer: 默认 `mock` 可离线运行；配置为 `openai` 后使用 LangChain structured output。

当前版本采用每局固定 NPC 节点、每回合动态路由。动态增删边、向量检索和生产级并发存储留作后续扩展。

## User Journey

1. 创建世界：

```bash
curl -X POST http://127.0.0.1:8000/games \
  -H 'Content-Type: application/json' \
  -d '{
    "scene": "我想玩一个魔法学院探险游戏",
    "final_goal": "通过试炼并找到魔法石",
    "tone": "神秘、温暖、有危险感",
    "npc_count": 5,
    "chapter_count": 3
  }'
```

2. 使用返回的 `game_id` 开场：

```bash
curl -X POST http://127.0.0.1:8000/games/GAME_ID/start
```

3. 提交玩家行动：

```bash
curl -X POST http://127.0.0.1:8000/games/GAME_ID/turns \
  -H 'Content-Type: application/json' \
  -d '{"action":"我质问守门人，并展示刚找到的符文钥匙"}'
```

4. 查询完整当前状态：

```bash
curl http://127.0.0.1:8000/games/GAME_ID
```

## Control Boundaries

- `chapters`、`completion_condition`、`final_goal`、`endings` 是硬约束。
- 导演只能选择活跃 NPC、结束回合或顺序推进章节。
- NPC 只能扩写当前场景，不能替玩家行动或创建未声明结局。
- 每回合最多生成 `STORY_MAX_NPC_REPLIES` 条 NPC 回复，避免抢话和失控循环。

## Test

```bash
pytest
```
