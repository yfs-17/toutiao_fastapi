from fastapi import FastAPI
from routers import news, users, favorite, history, ai
from fastapi.middleware.cors import CORSMiddleware
from utils.exception_handlers import register_exception_handler
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

register_exception_handler(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

@app.get("/")
async def root():
    return {"message": "Hello World"}


app.include_router(news.router)

app.include_router(users.router)

app.include_router(favorite.router)

app.include_router(history.router)

app.include_router(ai.router)
