"""
Top-level API v1 router — aggregates all sub-routers.
"""

from fastapi import APIRouter

from app.api.v1.endpoints import adaptive, auth, documents, generate, health, learning

api_router = APIRouter()

api_router.include_router(health.router,    prefix="/health",    tags=["Health"])
api_router.include_router(generate.router,  prefix="/generate",  tags=["Generate"])
api_router.include_router(documents.router, prefix="/documents", tags=["Documents"])
api_router.include_router(auth.router,      prefix="/auth",      tags=["Auth"])
api_router.include_router(adaptive.router,  prefix="/adaptive",  tags=["Adaptive Learning"])
api_router.include_router(learning.router,  prefix="/learning",  tags=["Learning (legacy)"])
