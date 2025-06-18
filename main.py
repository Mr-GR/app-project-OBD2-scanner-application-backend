import os
import uvicorn  # type: ignore
from fastapi import FastAPI, Header, HTTPException, Depends  # type: ignore
from fastapi.middleware.cors import CORSMiddleware  # type: ignore
from dotenv import load_dotenv  # type: ignore
from api.manaul import router as manaul_router

load_dotenv()

app = FastAPI(
    title='Obd2-Scanner',
    description='Obd2-Scanner API',
    version='1.0.0'
)

app.include_router(manaul_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def read_root():
    return {"message": "Welcome to the OBD2 Scanner API!"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8080, reload=True)
