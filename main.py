"""
HealthLink - Smart Health Management System
Main FastAPI application entry point.
"""
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config.settings import get_settings
from config.logging import setup_logging
from api.routes import router
from core.database import get_db_manager
from core.rag import load_knowledge_base


settings = get_settings()
logger = setup_logging(log_level=settings.log_level)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    Handles startup and shutdown events.
    """
    logger.info("Starting HealthLink application...")

    try:
        db_manager = get_db_manager(settings)
        logger.info("Database initialized successfully")

        from core.database import seed_doctors
        import json

        if settings.auto_seed_doctors_on_startup:
            doctors_file = "./data/doctors.csv"
            if os.path.exists(doctors_file):
                import pandas as pd
                doctors_df = pd.read_csv(doctors_file)
                doctors_data = doctors_df.to_dict('records')

                with db_manager.session_scope() as session:
                    seed_doctors(session, doctors_data)
                logger.info("Database seeded with doctor data")
            else:
                logger.warning(f"Doctors data file not found: {doctors_file}")
        else:
            logger.info("Skipping doctor seed on startup (auto_seed_doctors_on_startup=false)")

    except Exception as e:
        logger.error(f"Database initialization failed: {e}", exc_info=True)

    try:
        if settings.auto_load_kb_on_startup:
            kb_file = "./data/symptoms_kb.json"
            if os.path.exists(kb_file):
                load_knowledge_base(kb_file, settings)
                logger.info("Knowledge base loaded successfully")
            else:
                logger.warning(f"Knowledge base file not found: {kb_file}")
        else:
            logger.info("Skipping KB load on startup (auto_load_kb_on_startup=false)")
    except Exception as e:
        logger.error(f"RAG initialization failed: {e}", exc_info=True)

    logger.info("HealthLink startup complete")

    yield

    logger.info("Shutting down HealthLink...")
    logger.info("Shutdown complete")


app = FastAPI(
    title="HealthLink API",
    description="Smart Health Management System with AI-powered symptom analysis and doctor recommendations",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler for unhandled errors."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "message": "An unexpected error occurred. Please try again later.",
            "detail": str(exc) if settings.log_level == "DEBUG" else None
        }
    )


app.include_router(router, prefix="/api/v1")


@app.get("/", tags=["Root"])
async def root():
    """Root endpoint with API information."""
    return {
        "name": "HealthLink API",
        "version": "1.0.0",
        "description": "Smart Health Management System",
        "docs": "/docs",
        "health": "/api/v1/health"
    }


if __name__ == "__main__":
    import uvicorn

    logger.info(f"Starting server on {settings.api_host}:{settings.api_port}")

    uvicorn.run(
        "main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.api_reload,
        log_level=settings.log_level.lower()
    )
