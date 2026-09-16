from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import FileResponse

from story_weaver.config import Settings, get_settings
from story_weaver.llm import create_model
from story_weaver.models import CreateGameRequest, GameView, PlayerTurnRequest, TurnResponse
from story_weaver.repository import GameRepository
from story_weaver.service import GameNotFoundError, GameService, InvalidGameStateError


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        repository = GameRepository(config.database_path)
        app.state.repository = repository
        api_key = config.qwen_api_key if config.model_provider == "qwen" else config.openai_api_key
        app.state.service = GameService(
            repository,
            create_model(
                config.model_provider,
                config.model_name,
                api_key.get_secret_value() if api_key else None,
                config.qwen_base_url if config.model_provider == "qwen" else None,
            ),
            config.max_npc_replies,
        )
        yield
        repository.close()

    app = FastAPI(title="Story Weaver API", version="0.1.0", lifespan=lifespan)
    index_path = Path(__file__).parent / "static" / "index.html"

    @app.exception_handler(GameNotFoundError)
    async def not_found_handler(_: Request, exc: GameNotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Game {exc} not found")

    @app.exception_handler(InvalidGameStateError)
    async def invalid_state_handler(_: Request, exc: InvalidGameStateError):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))

    def service(request: Request) -> GameService:
        return request.app.state.service

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "model_provider": config.model_provider}

    @app.get("/", include_in_schema=False, response_class=FileResponse)
    def index() -> FileResponse:
        return FileResponse(index_path, headers={"Cache-Control": "no-store"})

    @app.post("/games", response_model=GameView, status_code=status.HTTP_201_CREATED)
    def create_game(payload: CreateGameRequest, request: Request) -> GameView:
        return service(request).create_game(payload)

    @app.post("/games/{game_id}/start", response_model=TurnResponse)
    def start_game(game_id: str, request: Request) -> TurnResponse:
        return service(request).start_game(game_id)

    @app.post("/games/{game_id}/turns", response_model=TurnResponse)
    def play_turn(game_id: str, payload: PlayerTurnRequest, request: Request) -> TurnResponse:
        return service(request).play_turn(game_id, payload)

    @app.get("/games/{game_id}", response_model=GameView)
    def get_game(game_id: str, request: Request) -> GameView:
        return service(request).get_game(game_id)

    return app


app = create_app()
