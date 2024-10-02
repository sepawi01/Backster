import os
from typing import Literal

import httpx
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents._generated.models import VectorizedQuery
from langchain_core.messages import ToolMessage
from langchain_core.tools import tool
from langchain_openai import AzureOpenAIEmbeddings

embeddings_model = AzureOpenAIEmbeddings(
    model="text-embedding-ada-002",
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    openai_api_key=os.getenv("AZURE_OPENAI_API_KEY")
)

search_client = SearchClient(os.getenv("AZURE_AI_SEARCH_ENDPOINT"), "backster-first",
                             AzureKeyCredential(os.getenv("AZURE_AI_SEARCH_API_KEY")))


def hybrid_search(query: str, park: str, annual_employee: bool, seasonal_employee: bool):
    embedded_query = embeddings_model.embed_query(query)
    content_vector_query = VectorizedQuery(vector=embedded_query, k_nearest_neighbors=3, fields="contentVector")

    # Construct filter
    combined_filter = f"park eq '{park}'"
    # Add conditions for employee type
    employee_filters = []
    if annual_employee:
        employee_filters.append("annual_employee eq true")
    if seasonal_employee:
        employee_filters.append("seasonal_employee eq true")

    # Add combined filter if any employee filters are present
    if employee_filters:
        combined_filter += f" and ({' or '.join(employee_filters)})"

    results = search_client.search(
        search_text=query,
        vector_queries=[content_vector_query],
        select=["title", "content", "park", "source", "id", "message_id"],
        top=3,
        filter=combined_filter
    )
    results = list(results)
    return results


def handle_tool_error(state) -> dict:
    error = state.get("error")
    tool_calls = state["messages"][-1].tool_calls
    return {
        "messages": [
            ToolMessage(
                content=f"Error: {repr(error)}\n please fix your mistakes.",
                tool_call_id=tc["id"],
            )
            for tc in tool_calls
        ]
    }


# def create_tool_node_with_fallback(tools: list) -> dict:
#     return ToolNode(tools).with_fallbacks(
#         [RunnableLambda(handle_tool_error)], exception_key="error"
#     )

def _print_event(event: dict, _printed: set, max_length=1500):
    current_state = event.get("dialog_state")
    if current_state:
        print("Currently in: ", current_state[-1])
    message = event.get("messages")
    if message:
        if isinstance(message, list):
            message = message[-1]
        if message.id not in _printed:
            msg_repr = message.pretty_repr(html=True)
            if len(msg_repr) > max_length:
                msg_repr = msg_repr[:max_length] + " ... (truncated)"
            print(msg_repr)
            _printed.add(message.id)


@tool
def lookup_faq(query: str, park: str, employment_type: Literal['Tillsvidare', 'Säsong/Visstid']) -> str:
    """Searches the companys internal knowledge base to find answers for users questions.
    Always use this tool before answering a users question. It will give you the most relevant information you
    have access to in regard to the employees question."""
    rag_results = hybrid_search(query,
                                park,
                                annual_employee=employment_type == "Tillsvidare",
                                seasonal_employee=employment_type == "Säsong/Visstid"
                                )
    sources = [result["source"] for result in rag_results]
    context = "\n".join([content["content"] for content in rag_results])
    return context


@tool
def get_daily_park_data(park: Literal["Gröna Lund", "Furuvik", "Kolmården", "Skara Sommarland"], date: str) -> dict:
    """Fetches daily information for a specific date regarding the parks.

    Use this if the user asks for information regarding the opening hours for the park
    or questions about expected, budgeted or actual number of guests on a specific date.

    Args:
        park (Literal): The name of the park. Must be one of "Gröna Lund", "Furuvik", "Kolmården", or "Skara Sommarland".
        date (str): The date for which the information is requested, formatted as YYYY-MM-DD.

    Returns:
        dict: A dictionary containing the park's daily information.
        If the park name is invalid or data retrieval fails, returns a dictionary with an "error" key.
    """
    park_map = {
        "Gröna Lund": '03',
        "Furuvik": '13',
        "Kolmården": '02',
        "Skara Sommarland": '05'
    }
    park_code = park_map.get(park)
    if not park_code:
        return {"error": "Invalid park name"}

    url = f"https://backstageinfo.azurewebsites.net/{park_code}/{date}"
    response = httpx.get(url)

    if response.status_code == 404:
        return {"info": "Parken är inte öppen denna dag"}
    if response.status_code != 200:
        return {"error": "Failed to retrieve data"}

    return response.json()


@tool
def handle_resignation(employee_name: str = None, resignation_date: str = None, reason: str = None):
    """
    Hanterar uppsägningsprocessen för en anställd.
    Frågar efter fullständigt namn, uppsägningsdatum, och genomför en kort intervju för orsaken.
    När all information är samlad, skrivs den ut (för nu) i konsolen.
    """

    if not employee_name:
        return "Vad är ditt fullständiga namn?"

    if not resignation_date:
        return "Vilket datum vill du att uppsägningen ska gälla från?"

    if not reason:
        return "Kan du kort förklara varför du vill säga upp dig?"

    print(f"Anställd: {employee_name} vill säga upp sig från och med {resignation_date}.")
    print(f"Anledning till uppsägningen: {reason}")

    # Returnera ett bekräftelsemeddelande
    return "Din uppsägning har registrerats. Tack för att du delade denna information."
