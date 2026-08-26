"""FastAPI entrypoint for the application-processing backend.

Run with: uvicorn backend.app.main:app --reload
All business logic (extraction, validation, scoring, review, audit) lives
here and in src/*; the Streamlit app is a thin client that only calls this API,
so any future client (React, a government portal, etc.) can reuse it unchanged.
"""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api import applications, auth, health, notifications, reviews, schemes, users
from src.db.schema import init_db
from src.telemetry import setup_telemetry

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    setup_telemetry()
    yield


app = FastAPI(
    title="Application Intelligence Platform API",
    description=(
        "API-first application processing platform for submission ingestion, AI-assisted "
        "extraction, validation, explainable scoring, and human review. AI output is "
        "advisory; final decisions remain with authorized human reviewers."
    ),
    version="1.0.0",
    contact={"name": "Prompt Pioneers"},
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # POC only - restrict to known client origins before any real deployment
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(schemes.router)
app.include_router(applications.router)
app.include_router(reviews.router)
app.include_router(notifications.router)
app.include_router(users.router)
