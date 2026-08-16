"""Frontend-master FastAPI application."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from src.master.routes.cold_start import router as cold_start_router
from src.master.rag.routes import router as rag_router
from src.config.config import get_config
from src.schemas import HealthResponse


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting SamLang frontend-master service")
    config = get_config()

    try:
        from src.code_start import StudentScorePredictor

        app.state.cold_start_predictor = StudentScorePredictor().load()
        logger.info("Cold-start predictor loaded")
    except Exception as exc:
        logger.error(f"Cold-start predictor failed to load: {exc}")
        app.state.cold_start_predictor = None

    try:
        from src.master.rag.pipeline import IngestionPipeline, RetrievalPipeline
        from src.ocr import get_ocr_client
        from src.rag.rag import RAG

        rag = RAG.from_config(
            rag_config=config.rag,
            embedding_config=config.embedding,
            rerank_config=config.rerank,
            ocr_client=get_ocr_client(),
        )
        app.state.ingestion_pipeline = IngestionPipeline(rag)
        app.state.retrieval_pipeline = RetrievalPipeline(rag)
        logger.info("RAG/OCR pipelines loaded for master service")
    except Exception as exc:
        logger.error(f"RAG/OCR pipelines failed to load: {exc}")

    yield

    if hasattr(app.state, "ingestion_pipeline"):
        try:
            app.state.ingestion_pipeline.rag.close()
        except Exception as exc:
            logger.error(f"Failed to close RAG resources: {exc}")
    logger.info("Stopping SamLang frontend-master service")


def create_app() -> FastAPI:
    app = FastAPI(
        title="SamLang Frontend Master",
        description="Frontend-facing backend service for SamLang v2",
        version="0.2.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/", response_model=HealthResponse)
    async def root():
        return {"status": "healthy", "message": "SamLang frontend-master is running", "version": "0.2.0"}

    @app.get("/api/health", response_model=HealthResponse)
    async def health_check():
        return {"status": "healthy", "message": "API is running", "version": "0.2.0"}

    app.include_router(cold_start_router)
    app.include_router(rag_router)
    return app


app = create_app()
