from fastapi import FastAPI

from src.auth.router import router as auth_router
from src.events.router import router as events_router
from src.photos.router import router as photos_router

app = FastAPI(title="EventSnap", version="0.1.0")

app.include_router(auth_router)
app.include_router(events_router)
app.include_router(photos_router)


@app.get("/")
async def root():
    return {"message": "Hello World"}
