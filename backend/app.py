from fastapi import FastAPI
from .db import Base, engine
from .routers.auth_routes import router as auth_router
from .routers import auth_routes, dataset_routes, stats_routes

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Data Entry API")

app.include_router(auth_router)
app.include_router(auth_routes.router)
app.include_router(dataset_routes.router)
app.include_router(stats_routes.router)

@app.get("/")
def root():
    return {"message": "API funcionando 🚀"}

@app.get("/health")
def health():
    return {"ok": True}

@app.get("/users")
def get_users():
    return [
        {"id": 1, "name": "Ana"},
        {"id": 2, "name": "Luis"}
    ]