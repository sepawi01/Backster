import os
from datetime import datetime, timedelta
from typing import Literal

import httpx
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents._generated.models import VectorizedQuery
from langchain_core.messages import ToolMessage
from langchain_core.tools import tool
from langchain_openai import AzureOpenAIEmbeddings
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

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
        select=["title", "content", "park", "source", "id", "original_content", "message_id"],
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


@tool(response_format="content_and_artifact")
def lookup_faq(query: str, park: str, employment_type: Literal['Tillsvidare', 'Säsong/Visstid']):
    """
    Searches the company's internal knowledge base to find answers for user questions.
    This tool should always be used before answering a user's question as it provides the
    most relevant information regarding the employee's query.

    Args:
        query (str): The question or query provided by the user.
        park (str): The name of the park for context. Must match the park data in the knowledge base.
        employment_type (Literal): The type of employment, either 'Tillsvidare' or 'Säsong/Visstid'.

    Returns:
        tuple: A tuple containing:
            - context (str): The relevant information found in the knowledge base.
            - dict: A dictionary with additional information:
                - sources (list[str]): A list of source paths used in the context.
                - original_contents (list[str]): A list of original content pieces retrieved during the search.
    """
    rag_results = hybrid_search(query,
                                park,
                                annual_employee=employment_type == "Tillsvidare",
                                seasonal_employee=employment_type == "Säsong/Visstid"
                                )
    sources = [result["source"] for result in rag_results]
    original_contents = [content["original_content"] for content in rag_results]
    context = "\n".join([content["content"] for content in rag_results])
    return context, {"sources": sources, "original_contents": original_contents}


@tool
def get_daily_park_data(park: Literal["Gröna Lund", "Furuvik", "Kolmården", "Skara Sommarland"], date: str) -> dict:
    """
    Fetches daily information for a specific date regarding the parks.

    This tool should be used if the user asks for information related to the park's opening hours
    or questions about expected, budgeted, or actual number of guests on a specific date.

    Args:
        park (Literal): The name of the park. Must be one of "Gröna Lund", "Furuvik", "Kolmården", or "Skara Sommarland".
        date (str): The date for which the information is requested, formatted as YYYY-MM-DD.

    Returns:
        dict: A dictionary containing the park's daily information. If the park name is invalid or
        data retrieval fails, the dictionary will contain an "error" key with an appropriate message.
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
def handle_resignation(employee_name: str = None, email_adress: str = None, resignation_date: str = None,
                       reason: str = None):
    """
    Handles the resignation process for an employee by asking for the full name, resignation date, email adress and reason.
    When the employee is asking for resignation, it's important to inform the employee that it has a minimum notice period
    of 14 days.

    Args:
        employee_name (str): The full name of the employee. If not provided, the function will prompt for it.
        email_adress (str): The email address of the employee. If not provided, the function will prompt for it.
        resignation_date (str): The date on which the resignation should take effect, format = %Y-%m-%d. If not provided, the function will prompt for it.
        reason (str): The reason for resignation. If not provided, the function will prompt for it.

    Returns:
        str: A message confirming the resignation registration if all necessary information is provided,
        or a prompt for the missing information.
    """
    if not employee_name:
        return "Vad är ditt fullständiga namn?"

    if not email_adress:
        return "Vad är din mailadress?"

    if not resignation_date:
        return "Vilket datum vill du att uppsägningen ska gälla från?"

    if not reason:
        return "Vad är anledningen till att du vill säga upp dig?"

    try:
        resignation_date = datetime.strptime(resignation_date, "%Y-%m-%d")
    except ValueError:
        return "Datumet måste vara i formatet YYYY-MM-DD."

    if resignation_date <= datetime.now() + timedelta(days=14):
        return "Uppsägningen kan inte göras tidigare än 14 dagar från idag."

    message = Mail(
        from_email="backster@parksandresorts.com",
        to_emails=os.getenv("SEND_TO_EMAIL"),
        subject=f"Backster: Uppsägning från {employee_name}",
        html_content=f"""

        <h1>Backster: Uppsägning av anställning</h1>
        <p>Hej!</p>
        <p>Jag har mottagit en anmälan om uppsägning från <span class="highlight">{employee_name}</span> med kontaktuppgifter: 
        <span class="highlight">{email_adress}</span>.</p>
        <p>{employee_name} önskar att säga upp sig och har angett att sista arbetsdagen ska vara <span class="highlight">{resignation_date.strftime("%Y-%m-%d")}</span>.</p>
        <p>Angiven anledning till uppsägningen är: <span class="highlight">{reason}</span>.</p>
        <p>Vänligen kontakta {employee_name} för ytterligare frågor eller för att bekräfta uppsägningen.</p>
        <p>Med vänliga hälsningar,</p>
        <p>Backster</p>
        """)

    try:
        sg = SendGridAPIClient(os.getenv("SENDGRID_API_KEY"))
        response = sg.send(message)

        if response.status_code != 202:
            raise Exception("Failed to send email")
    except Exception as e:
        return f"""Jag kunde tyvärr inte skicka informationen till Artistservice. Vänligen försök igen senare eller kontakta Artistservice direkt."""

    return "Jag har nu skickat informationen till Artistservice. Dom kommer återkoppla till dig inom kort."


@tool
def handle_lost_backstagepass(full_name: str = None, email_address: str = None):
    """
    Handles the situation when an employee has lost their Backstage pass.
    The tool will guide the employee through the process of putting together the correct information to Artistservice.
    The information will be used to send an email to Aristservice with the necessary information.

    Args:
        full_name (str): The full name of the employee.
        email_address (str): The email address of the employee.

    Returns:
        str: A message informing if the message was sent successfully or not.
    """
    if not full_name:
        return "För att skicka informationen till Artistservice behöver jag ditt fullständiga namn."
    if not email_address:
        return "För att skicka informationen till Artistservice behöver jag din mailadress."

    message = Mail(
        from_email="backster@parksandresorts.com",
        to_emails=os.getenv("SEND_TO_EMAIL"),
        subject=f"Backster: {full_name} önskar spärra sitt Backstagepass",
        html_content=f"""
        <body>
        <div class="email-container">
            <h1>Backster: Spärr av Backstagepass</h1>
            <p>Hej!</p>
            <p>{full_name} har tappat sitt Backstagepass och önskar att spärra det. Jag har informerat {full_name} att komma till Artistservice för att få ett nytt pass.
             Om ni vill kontakta {full_name} så har hen uppgett följande mailadress:</p>
            <p>{email_address}</p>
            <div class="footer">
                <p>Med vänliga hälsningar, Backster</p>
            </div>
        </div>
    </body>""")

    try:
        sg = SendGridAPIClient(os.getenv("SENDGRID_API_KEY"))
        response = sg.send(message)

        if response.status_code != 202:
            raise Exception("Failed to send email")

    except Exception as e:
        return f"""Jag kunde tyvärr inte skicka informationen till Artistservice. 
        Försök igen senare eller kontakta Aristservice direkt."""

    return f"""Jag har nu skickat informationen till Artistservice. Kom in till Artistservice för att hämta ett nytt Backstagepass."""
