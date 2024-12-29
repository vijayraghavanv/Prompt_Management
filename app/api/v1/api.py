from fastapi import APIRouter
from app.api.v1.endpoints import projects, prompts, settings, runs

api_router = APIRouter()

# Include routers for different resources
api_router.include_router(projects.router, prefix="/projects", tags=["projects"])
api_router.include_router(prompts.router, prefix="/prompts", tags=["prompts"])
api_router.include_router(settings.router, prefix="/settings", tags=["settings"])
api_router.include_router(runs.router, prefix="/runs", tags=["runs"])
