from fastapi import FastAPI
from app.database import engine
from app.models import Base
from app.routes import user_routes, meta_routes  # example imports

app = FastAPI()

# Include routers from other modules
app.include_router(user_routes.router, prefix="/users", tags=["Users"])
app.include_router(meta_routes.router, prefix="/meta", tags=["Meta"])


# Health check (optional)
@app.get("/")
async def root():
    return {"message": "Advise AI backend running"}