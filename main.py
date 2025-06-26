# main.py

import os
import uvicorn  # type: ignore
from fastapi import FastAPI  # type: ignore
from fastapi.middleware.cors import CORSMiddleware  # type: ignore
from dotenv import load_dotenv  # type: ignore

load_dotenv()  # Load environment variables from .env

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

    app.include_router(vin_router, prefix="/api", tags=["VIN Decoder"])
    app.include_router(diag_router, prefix="/api", tags=["Diagnostics"])
    app.include_router(scanner_router, prefix="/api", tags=["OBD2 Scanner"])
    app.include_router(chat_router, prefix="/api", tags=["AI Chat"])
    app.include_router(vehicles_router, prefix="/api", tags=["Vehicle Management"])

    # ── CORS middleware ───────────────────────────────────────────────────────
    allow_origins = os.getenv("CORS_ORIGINS", "*").split(",")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

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
