import os
from langchain_openai import AzureChatOpenAI
from langgraph.prebuilt import ToolNode
from datetime import datetime
from typing import Annotated
from typing_extensions import TypedDict
from langgraph.graph.message import AnyMessage, add_messages
from langchain_core.prompts import ChatPromptTemplate
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph, START
from langgraph.prebuilt import tools_condition
from dotenv import load_dotenv
from ai_backend.agent_tools import lookup_faq, get_daily_park_data, handle_resignation

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
        state["employmentType"] = configuration.get("employmentType", None)

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
        Den medarbetare som du hjälper är har anställningsformen {employmentType}, vilket är viktigt att du tar hänsyn 
        till i ditt svar, så att du svarar med rätt information. Om anställningsformen är relevant för svaret så börja 
        ditt svar med 'Som (anställningsform)anställd...' Men gör bara det om det framgår av kontexten.
        Använd de verktyg som du har tillgång till, så som handle_resignation, lookup_fag och get_daily_park_data för 
        att hjälpa medarbetaren. Svara detaljerat och steg-för-steg, och inkludera alla relevanta instruktioner eller
        detaljer som du har tillgång till i kontexten. Om frågan inte uppenbart är en get_daily_park_data eller 
        handle_resignation-fråga, så använd ALLTID lookup_faq för att se om det finns en matchande fråga i kunskaps-
        databasen. Säkerställ ocskå att query till lookup_faq är så semantiskt korrekt som möjligt utifrån de personen
        frågar. Om du inte kan hitta ett svar med hjälp av information från verktygen, så uppge det tydligt för 
        användaren och föreslå vänligt att personen kan kontakta Artistservice för hjälp med frågan.
        
        Viktiga instruktioner: Svara aldrig på frågor som bygger på information som ligger utanför den du kan hämta från
        verktygen. 
        Var alltid vänlig och professionell i din kommunikation.
        Svara alltid med text i markdown-format.
        
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
