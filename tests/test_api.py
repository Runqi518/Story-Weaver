from fastapi.testclient import TestClient

from story_weaver.api import create_app
from story_weaver.config import Settings


def make_client() -> TestClient:
    app = create_app(Settings(model_provider="mock", database_path=":memory:", max_npc_replies=2))
    return TestClient(app)


def test_full_game_flow() -> None:
    with make_client() as client:
        created = client.post(
            "/games",
            json={
                "scene": "A school of magic hides an ancient artifact",
                "final_goal": "find the star stone",
                "npc_count": 3,
                "chapter_count": 2,
            },
        )
        assert created.status_code == 201
        game = created.json()
        assert game["status"] == "ready"
        assert len(game["world"]["npcs"]) == 3

        started = client.post(f"/games/{game['game_id']}/start")
        assert started.status_code == 200
        assert started.json()["status"] == "playing"
        assert started.json()["replies"]
        assert len({reply["speech"] for reply in started.json()["replies"]}) == 2

        advanced = client.post(
            f"/games/{game['game_id']}/turns",
            json={"action": "I found the clue and completed this stage"},
        )
        assert advanced.status_code == 200
        assert advanced.json()["chapter"]["id"] == "chapter-2"

        completed = client.post(
            f"/games/{game['game_id']}/turns",
            json={"action": "I found the star stone and completed the quest"},
        )
        assert completed.status_code == 200
        assert completed.json()["status"] == "completed"
        assert completed.json()["ending"]


def test_unknown_game_returns_404() -> None:
    with make_client() as client:
        response = client.get("/games/missing")
        assert response.status_code == 404


def test_health_exposes_model_mode() -> None:
    with make_client() as client:
        response = client.get("/health")
        assert response.json() == {"status": "ok", "model_provider": "mock"}


def test_playable_home_page() -> None:
    with make_client() as client:
        response = client.get("/")
        assert response.status_code == 200
        assert "创建你的故事" in response.text
        assert "[hidden] { display:none !important; }" in response.text
        assert response.headers["cache-control"] == "no-store"
