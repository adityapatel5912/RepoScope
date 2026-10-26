"""Fixture: a backend with routes, a client that calls them, and classes."""
from fastapi import FastAPI

app = FastAPI()


@app.get("/api/health")
def health():
    return {"ok": True}


@app.post("/api/items/{item_id}")
def create_item(item_id: str):
    return {"id": item_id}


@app.websocket("/ws/live")
async def live_socket(websocket):
    return websocket
