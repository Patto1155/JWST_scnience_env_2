"""Main FastAPI application."""

import sys
from pathlib import Path

# Add parent directory to path
_parent_dir = Path(__file__).parent.parent
if str(_parent_dir) not in sys.path:
    sys.path.insert(0, str(_parent_dir))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

# Now we can use normal imports since directory uses underscores
from core_api.db import init_db, SessionLocal
from core_api.routers import tools, catalog, experiments, runs
from core_api.startup import (
    register_tools,
    register_datasets,
    validate_dataset_catalog_integrity,
)
from core_api.models.datasets import Dataset

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown."""
    # Startup
    print("Starting Science OS API...")
    init_db()
    
    # Synchronize tool registry and initialize datasets if needed.
    db = SessionLocal()
    try:
        dataset_count = db.query(Dataset).count()

        registered_tools, updated_tools = register_tools(db)
        print(
            f"Tool registry sync complete: registered {registered_tools}, updated {updated_tools}"
        )
        if dataset_count == 0:
            print("No datasets found, registering sample datasets...")
            register_datasets(db)

        validate_dataset_catalog_integrity(db)
    finally:
        db.close()
    
    yield
    
    # Shutdown (if needed)
    print("Shutting down Science OS API...")

app = FastAPI(
    title="Science OS API",
    description="Science OS - A system for autonomous LLM scientific discovery",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(tools.router)
app.include_router(catalog.router)
app.include_router(experiments.router)
app.include_router(runs.router)

@app.get("/")
def root():
    """Root endpoint."""
    return {
        "name": "Science OS API",
        "version": "0.1.0",
        "endpoints": {
            "tools": "/tools",
            "datasets": "/datasets",
            "experiments": "/experiments",
            "runs": "/runs",
        },
    }

@app.get("/health")
def health():
    """Health check endpoint."""
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
