from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel
from dotenv import load_dotenv
from fastapi.staticfiles import StaticFiles
import os
from jose import JWTError, jwt
from datetime import datetime, timedelta

load_dotenv()

from ai_backend import agent

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["127.0.0.1*", "localhost*", "https://backstage.prs.se/*"],
    allow_credentials=True,
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)


KEY = os.getenv("BACKEND_KEY")
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
app.mount("/static", StaticFiles(directory="frontend/dist"), name="static")
app.mount("/assets", StaticFiles(directory="frontend/dist/assets"), name="assets")


class MessageRequest(BaseModel):
    session_id: str
    query: str
    park: str

def get_key(key: str = Query(...)):
    if key != KEY:
        raise HTTPException(status_code=403, detail="Not authenticated")
    return key

def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now() + expires_delta
    else:
        expire = datetime.now() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def validate_token(token: str = Query(...)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(status_code=403, detail="Invalid or expired token")
@app.get("/")
async def serve_frontend(key: str = Depends(get_key)):
    return FileResponse("frontend/dist/index.html")

@app.get("/token")
async def get_token(key: str = Depends(get_key)):
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    token = create_access_token(data={"sub": "frontend_user"}, expires_delta=access_token_expires)
    return {"token": token}

@app.post("/chat")
async def chat_with_agent(request: MessageRequest, token: str = Depends(validate_token)):
    config = {"configurable": {"park": request.park, "thread_id": request.session_id}}
    state = {"messages": [("user", request.query)]}

    response = agent.graph.invoke(state, config)
    answer = response['messages'][-1].content

    return {'fromBot': True, "text": answer}
