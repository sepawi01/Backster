import uuid

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
load_dotenv()

import agent
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Tillåt alla domäner
    allow_credentials=True,
    allow_methods=["*"],  # Tillåt alla HTTP-metoder
    allow_headers=["*"],  # Tillåt alla headers
)

sessions_memory = {}
class MessageRequest(BaseModel):
    session_id: str
    query: str
    park: str

@app.get("/")
async def root():
    return {"message": "Hello World"}


@app.post("/chat")
async def chat_with_agent(request: MessageRequest):
    config = {"configurable": {"park": request.park, "thread_id": request.session_id}}
    state = {"messages": [("user", request.query)]}

    response = agent.graph.invoke(state, config)
    answer = response['messages'][-1].content

    return {'fromBot': True, "text": answer}

@app.get("/new_session")
async def new_session():
    session_id = str(uuid.uuid4())
    return {"session_id": session_id}
