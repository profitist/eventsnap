from fastapi import FastAPI

from fastapi.middleware.cors import CORSMiddleware

from src.auth.router import router as auth_router
from src.events.router import router as events_router
from src.photos.router import router as photos_router
from src.users.router import router as users_router

app = FastAPI(title="EventSnap", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(events_router)
app.include_router(photos_router)


@app.get("/")
async def root():
    return {"message": "Hello World"}
