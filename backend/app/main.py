import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

logger = logging.getLogger(__name__)

from app.api.routes.data_sources import router as data_sources_router
from app.api.routes.evaluation import router as evaluation_router
from app.api.routes.predictions import router as predictions_router
from app.api.routes.reports import router as reports_router
from app.api.routes.simulations import router as simulations_router
from app.config import settings

app = FastAPI(
    title=settings.app_name,
    description="AI-powered IT labor market prediction simulator for Japan",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174", "http://localhost:5175"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(simulations_router)
app.include_router(reports_router)
app.include_router(predictions_router)
app.include_router(data_sources_router)
app.include_router(evaluation_router)


@app.get("/api/health")
async def health_check():
    """ヘルスチェック — 各サービスの接続状態を返す."""
    from app.core.graph.client import GraphClient
    from app.core.redis_client import RedisClient

    redis_ok = False
    neo4j_ok = False

    try:
        redis = RedisClient()
        redis_ok = await redis.is_available()
        await redis.close()
    except Exception:
        logger.warning("ヘルスチェック: Redis接続確認に失敗")

    try:
        graph = GraphClient()
        neo4j_ok = await graph.is_available()
        await graph.close()
    except Exception:
        logger.warning("ヘルスチェック: Neo4j接続確認に失敗")

    return {
        "status": "ok",
        "app": settings.app_name,
        "services": {
            "redis": "connected" if redis_ok else "unavailable",
            "neo4j": "connected" if neo4j_ok else "unavailable",
        },
    }
