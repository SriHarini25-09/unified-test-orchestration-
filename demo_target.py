"""Small target application used by the API and UI demo tests."""

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse

app = FastAPI(title="Demo Target App")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/items/{item_id}")
async def get_item(item_id: int) -> dict[str, object]:
    return {"id": item_id, "name": "Demo Item"}


@app.post("/login")
async def login(payload: dict[str, str]) -> dict[str, str]:
    if payload.get("username") == "admin" and payload.get("password") == "secret":
        return {"token": "demo-token"}
    raise HTTPException(status_code=401, detail="invalid credentials")


@app.get("/", response_class=HTMLResponse)
async def index() -> str:
    return """<!doctype html>
<html>
  <head><title>Demo App</title></head>
  <body>
    <h1>Demo App</h1>
    <form id="login">
      <label for="u">Username</label>
      <input id="u" name="u" />
      <button type="button">Sign in</button>
    </form>
  </body>
</html>"""


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8001)
