from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(simulations_router)
app.include_router(reports_router)
app.include_router(predictions_router)


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "app": settings.app_name}
