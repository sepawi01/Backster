import os
from langchain_openai import AzureChatOpenAI
from langgraph.prebuilt import ToolNode
from datetime import datetime
from typing import Annotated
from typing_extensions import TypedDict
from langgraph.graph.message import AnyMessage, add_messages
from langchain_core.runnables import Runnable, RunnableConfig
from langchain_core.prompts import ChatPromptTemplate
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph, START
from langgraph.prebuilt import tools_condition
from dotenv import load_dotenv
from agent_tools import lookup_faq, get_daily_park_data, handle_resignation

load_dotenv()

azure_openai_api_version: str = "2023-05-15"
azure_deployment = "gpt-4o-mini"


llm = AzureChatOpenAI(
    azure_deployment=azure_deployment,
    temperature=0.2,
    max_tokens=4000,
    api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
    model="gpt-4o-mini"
)


class State(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]


class Assistant:
    def __init__(self, runnable):
        self.runnable = runnable

    def __call__(self, state, config):
        configuration = config.get("configurable", {})
        state["park"] = configuration.get("park", None)

        while True:
            result = self.runnable.invoke(state)
            if not result.tool_calls and not result.content:
                state["messages"].append(("user", "Respond with a real output."))
            else:
                break

        return {"messages": result}


def create_primary_prompt():
    return ChatPromptTemplate.from_messages([
        ("system", """
        Du är en hjälpsam och vänlig AI-assistent för medarbetare på {park}. Dagens datum är {current_date}.
        Använd de verktyg som du har tillgång till, så som handle_resignation, lookup_FAQ och get_daily_park_data för att hjälpa medarbetaren.
        När du skickar query till lookup_faq, formulera en fråga som är semantiskt lik den fråga användaren ställer.
        Svara detaljerat och steg-för-steg, och inkludera alla relevanta instruktioner eller detaljer.
        Om information saknas, informera användaren och föreslå att de kontaktar Artistservice. 
        Om du inte anropar ett verktyg eller om svaret på användarens frågor in finns i de svar du får från verktygen,
        så måste du svara att du inte kan svara på frågan och föreslå att användaren kontaktar Artistservice.
        
        Instruktioner: Svara aldrig på frågor som är utanför din kompetensområde. Om du inte kan svara på en fråga, föreslå att användaren kontaktar Artistservice.
        
        """),
        ("placeholder", "{messages}")
    ]).partial(current_date=datetime.today().strftime("%Y-%m-%d"))



def create_assistant_runnable(llm, tools):
    primary_prompt = create_primary_prompt()
    return primary_prompt | llm.bind_tools(tools)

tools = [lookup_faq, get_daily_park_data, handle_resignation]
assistant_runnable = create_assistant_runnable(llm, tools)

builder = StateGraph(State)

builder.add_node("assistant", Assistant(assistant_runnable))
builder.add_node("tools", ToolNode(tools))
builder.add_edge(START, "assistant")
builder.add_conditional_edges(
    "assistant",
    tools_condition
)
builder.add_edge("tools", "assistant")
memory = MemorySaver()

graph = builder.compile(checkpointer=memory)