# app/main.py
from fastapi import FastAPI
from app.database import engine, Base
from app import models  # pour que Base connaisse tous les modèles
from app.Auth import router as AuthRouter


# Crée les tables si besoin
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="AdsAi API",
    description="Backend FastAPI pour AdsAi",
    version="1.0.0",
)




app.include_router(AuthRouter, prefix="/auth", tags=["auth"])


