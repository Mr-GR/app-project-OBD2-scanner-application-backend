# main.py

import os
import uvicorn  # type: ignore
import logging
from fastapi import FastAPI, Request  # type: ignore
from fastapi.middleware.cors import CORSMiddleware  # type: ignore
from dotenv import load_dotenv  # type: ignore

load_dotenv()  # Load environment variables from .env
logger = logging.getLogger(__name__)

def get_application() -> FastAPI:
    app = FastAPI(
        title="OBD2-Scanner",
        description="OBD2-Scanner API with ELM327 support",
        version=os.getenv("API_VERSION", "1.0.0"),
    )

    # ── Routers ───────────────────────────────────────────────────────────────
    from api.manual import router as vin_router
    from api.routers.diagnostics import router as diag_router
    from api.routers.scanner import router as scanner_router
    from api.routers.chat import router as chat_router
    from api.routers.vehicles import router as vehicles_router
    from api.routers.auth import router as auth_router

    # ── Debug middleware to log request headers (BEFORE routers) ──────────────
    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        # Log request details for debugging auth issues
        if request.url.path.startswith("/api/chat"):
            logger.info(f"Request to {request.method} {request.url.path}")
            auth_header = request.headers.get("authorization")
            logger.info(f"Authorization header: {'Present' if auth_header else 'Missing'}")
            if auth_header:
                logger.info(f"Auth header starts with Bearer: {auth_header.startswith('Bearer ')}")
        
        response = await call_next(request)
        return response

    # ── CORS middleware ───────────────────────────────────────────────────────
    allow_origins = os.getenv("CORS_ORIGINS", "*").split(",")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Routers ───────────────────────────────────────────────────────────────
    app.include_router(vin_router, prefix="/api", tags=["VIN Decoder"])
    app.include_router(diag_router, prefix="/api", tags=["Diagnostics"])
    app.include_router(scanner_router, prefix="/api", tags=["OBD2 Scanner"])
    app.include_router(chat_router, prefix="/api", tags=["AI Chat"])
    app.include_router(vehicles_router, prefix="/api", tags=["Vehicle Management"])
    app.include_router(auth_router, prefix="/api", tags=["Authentication"])

    # ── Health check ─────────────────────────────────────────────────────────
    @app.get("/", tags=["Health"])
    async def read_root():
        return {"message": "Welcome to the OBD2 Scanner API!"}

    return app


app = get_application()

# ── Entry point ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
