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

artistservice_mail_park_map = {
        "Gröna Lund": 'artistservice@gronalund.com',
        "Furuvik": 'artistservice@furuvik.com',
        "Kolmården": 'artistservice@kolmarden.com',
        "Skara Sommarland": 'artistservice@sommarland.se'
    }

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
def handle_resignation(employee_name: str, email_adress: str, resignation_date: str,
                       reason: str, park: Literal["Gröna Lund", "Furuvik", "Kolmården", "Skara Sommarland"]):
    """
    Handles the resignation process for a Gröna Lund employee by asking for the full name, resignation date, email adress and reason.
    When the employee is asking for resignation, inform the employee that it has a minimum notice period
    of 14 days. There is only Gröna Lund employees that can use this tool.

    Args:
        employee_name (str): The full name of the employee. If not provided, the function will prompt for it.
        email_adress (str): The email address of the employee. If not provided, the function will prompt for it.
        resignation_date (str): The date on which the resignation should take effect, format = %Y-%m-%d. If not provided, the function will prompt for it.
        reason (str): The reason for resignation. If not provided, the function will prompt for it.
        park (Literal): The name of the park where the employee works. Must be one of "Gröna Lund", "Furuvik", "Kolmården", or "Skara Sommarland".

    Returns:
        str: A message informing if the message was sent successfully or not.
    """

    if park != "Gröna Lund":
        return "Tyvärr kan jag inte hjälpa dig med uppsägning. Vänligen kontakta Artistservice."

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
        from_email=os.getenv("SEND_FROM_EMAIL"),
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
        <p>TEST RAD! Jag kommer skicka till {artistservice_mail_park_map.get(park, "error")} när vi går live</p>
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
def handle_lost_backstagepass(full_name: str, email_address: str,
                              park: Literal["Gröna Lund", "Furuvik", "Kolmården", "Skara Sommarland"]):
    """
    Handles the situation when an employee has lost their Backstage pass.
    The tool will guide the employee through the process of putting together the correct information to Artistservice.

    Args:
        full_name (str): The full name of the employee.
        email_address (str): The email address of the employee.
        park (Literal): The name of the park where the employee works. Must be one of "Gröna Lund", "Furuvik", "Kolmården", or "Skara Sommarland".

    Returns:
        str: A message informing if the message was sent successfully or not.
    """
    if not full_name:
        return "För att skicka informationen till Artistservice behöver jag ditt fullständiga namn."
    if not email_address:
        return "För att skicka informationen till Artistservice behöver jag din mailadress."

    message = Mail(
        from_email=os.getenv("SEND_FROM_EMAIL"),
        to_emails=os.getenv("SEND_TO_EMAIL"),
        subject=f"Backster: {full_name} önskar spärra sitt Backstagepass",
        html_content=f"""
            <h1>Backster: Spärr av Backstagepass</h1>
            <p>Hej!</p>
            <p>{full_name} har tappat sitt Backstagepass och önskar att spärra det. Jag har informerat {full_name} att 
            komma till Artistservice för att få ett nytt pass.
             Om ni vill kontakta {full_name} så har hen uppgett följande mailadress:</p>
            <p>{email_address}</p>
            <p>Med vänliga hälsningar, Backster</p>
            
            <p>TEST RAD! Jag kommer skicka till {artistservice_mail_park_map.get(park, "error")} när vi går live</p>
            """)

    try:
        sg = SendGridAPIClient(os.getenv("SENDGRID_API_KEY"))
        response = sg.send(message)

        if response.status_code != 202:
            raise Exception("Failed to send email")

    except Exception as e:
        return f"""Jag kunde tyvärr inte skicka informationen till Artistservice. 
        Försök igen senare eller kontakta Aristservice direkt."""

    return f"""Jag har nu skickat informationen till Artistservice. Kom in till Artistservice för att hämta ett nytt Backstagepass."""


@tool
def handle_work_certificate_request(certificate_type: Literal['arbetsintyg', 'arbetsbetyg'],
                                    full_name: str,
                                    email_address: str,
                                    park: Literal["Gröna Lund", "Furuvik", "Kolmården", "Skara Sommarland"]):
    """
    Handles the situation when an employee requests a work certificate.
    The tool will guide the employee through the process of putting together the correct information to Artistservice.

    Args:
        certificate_type (Literal): The type of certificate requested, either 'arbetsintyg' or 'arbetsbetyg'.
        full_name (str): The full name of the employee.
        email_address (str): The email address of the employee.
        park (Literal): The name of the park where the employee works. Must be one of "Gröna Lund", "Furuvik", "Kolmården", or "Skara Sommarland".

    Returns:
        str: A message informing if the message was sent successfully or not.
    """

    if not full_name:
        return "För att skicka informationen till Artistservice behöver jag ditt fullständiga namn."
    if not email_address:
        return "För att skicka informationen till Artistservice behöver jag din mailadress."
    if certificate_type not in ['arbetsintyg', 'arbetsbetyg']:
        return "Vänligen ange vilken typ av intyg du önskar, antingen 'arbetsintyg' eller 'arbetsbetyg'."

    message = Mail(
        from_email=os.getenv("SEND_FROM_EMAIL"),
        to_emails=os.getenv("SEND_TO_EMAIL"),
        subject=f"Backster: Begäran om {certificate_type}",
        html_content=
        f"""
    <h1>Begäran om {certificate_type}</h1>
        <p>Hej!</p>
        <p><span class="highlight">{full_name}</span> önskar att få ett <span class="highlight">{certificate_type}</span> vid avslutad säsong.</p>
        <p>Personens mail-adress är: <span class="highlight">{email_address}</span>.</p>
            <p>Med vänliga hälsningar, Backster</p>

    <p>TEST RAD! Jag kommer skicka till {artistservice_mail_park_map.get(park, "error")} när vi går live</p>
    """)
    try:
        sg = SendGridAPIClient(os.getenv("SENDGRID_API_KEY"))
        response = sg.send(message)

        if response.status_code != 202:
            raise Exception("Failed to send email")

    except Exception as e:
        return f"""Jag kunde tyvärr inte skicka informationen till Artistservice. 
        Försök igen senare eller kontakta Artistservice direkt."""

    return f"""Jag har nu skickat informationen till Artistservice. Dom kommer återkoppla till dig inom kort."""


@tool
def handle_give_away_shift(full_name: str, email_address: str,
                           shift_date: str,
                           shift_receiver_full_name: str,
                           shift_receiver_email: str,
                           park: Literal["Gröna Lund", "Furuvik", "Kolmården", "Skara Sommarland"]):
    """
    Handles the situation when an employee wants to give away a shift to another employee.
    The tool will guide the employee through the process of putting together the correct information to Artistservice.
    The information will be used to send an email to the employee that should take the shift.

    Args:
        full_name (str): The full name of the employee that want to give away shift.
        email_address (str): The email address of the employee that want to give away shift.
        shift_date (str): The date of the shift to be given away.
        shift_receiver_full_name (str): The full name of the employee who will receive the shift.
        shift_receiver_email (str): The email address of the employee who will receive the shift.

    Returns:
        str: A message confirming if the message was sent successfully or not.
    """

    if not full_name:
        return "För att skicka informationen till mottagaren behöver jag ditt fullständiga namn."
    if not email_address:
        return "För att skicka informationen till mottagaren behöver jag din mailadress."
    if not shift_date:
        return "Vilket datum är det för skiftet du vill ge bort?"
    if not shift_receiver_full_name:
        return "För att skicka informationen till mottagaren behöver jag mottagarens fullständiga namn."
    if not shift_receiver_email:
        return "För att skicka informationen till mottagaren behöver jag mottagarens mailadress."

    message = Mail(
        from_email=os.getenv("SEND_FROM_EMAIL"),
        to_emails=shift_receiver_email,
        subject=f"Backster: {full_name} önskar ge bort ett pass",
        html_content=f"""
    <h1>Övertagande av arbetspass</h1>
    <p>Hej <span class="highlight">{shift_receiver_full_name}</span>!</p>
    <p>Din kollega <span class="highlight">{full_name}</span> har ett pass den <span class="highlight">{shift_date}</span> som hen önskar att du tar över.</p>
    <p>För att bekräfta övertagandet, vänligen vidarebefordra detta e-postmeddelande till <span class="highlight">{artistservice_mail_park_map.get(park, "error")}</span>.</p>
    <p>Om du har några frågor, tveka inte att kontakta Artistservice.</p>
    <p>Med vänliga hälsningar,</p>
    <p>Backster</p>""")

    try:
        sg = SendGridAPIClient(os.getenv("SENDGRID_API_KEY"))
        response = sg.send(message)

        if response.status_code != 202:
            raise Exception("Failed to send email")
    except Exception as e:
        return f"""Jag kunde tyvärr inte skicka informationen till mottagaren. 
        Försök igen senare eller kontakta Artistservice"""

    return f"""Jag har nu skickat din förfrågan till mottagaren."""


@tool
def handle_illness_insurance(full_name: str,
                             email_address: str,
                             sick_leave_dates: list[str],
                             park: Literal["Gröna Lund", "Furuvik", "Kolmården", "Skara Sommarland"]):
    """
    Handles the situation when an employee want to register a illness insurance.
    The tool will guide the employee through the process of putting together the correct information to Artistservice.
    The information will be used to send an email to Artistservice with the necessary information.

    Args:
        full_name (str): The full name of the employee.
        email_address (str): The email address of the employee.
        sick_leave_dates (list[str]): The date or dates of the sick leave.
        park (Literal): The name of the park where the employee works. Must be one of "Gröna Lund", "Furuvik", "Kolmården", or "Skara Sommarland".

    Returns:
        str: A message confirming if the message was sent successfully or not.
    """

    if park != "Gröna Lund":
        return "Tyvärr kan jag inte hjälpa dig med sjukdomsförsäkring."

    if not full_name:
        return "För att skicka informationen till Artistservice behöver jag ditt fullständiga namn."
    if not email_address:
        return "För att skicka informationen till Artistservice behöver jag din mailadress."
    if not sick_leave_dates:
        return "Vilket/vilka datum var du hemma sjuk?"

    sick_leave_dates = ", ".join(sick_leave_dates)

    message = Mail(
        from_email=os.getenv("SEND_FROM_EMAIL"),
        to_emails=os.getenv("SEND_TO_EMAIL"),
        subject=f"Backster: Sjukförsäkran från {full_name}",
        html_content=f"""<p>{full_name} har varit hemma sjuk under följande datum: {sick_leave_dates}. Och önskar
        att registrera en sjukdomsförsäkran. Kontakta {full_name} på {email_address} för ytterligare information.
        </p>
        <p>Med vänliga hälsningar, Backster</p>
        
        <p>TEST RAD! Jag kommer skicka till {artistservice_mail_park_map.get(park, "error")} när vi går live</p>
        """)

    try:
        sg = SendGridAPIClient(os.getenv("SENDGRID_API_KEY"))
        response = sg.send(message)

        if response.status_code != 202:
            raise Exception("Failed to send email")

    except Exception as e:
        return f"""Jag kunde tyvärr inte skicka informationen till Artistservice. 
        Försök igen senare eller kontakta Artistservice direkt."""

    return f"""Jag har nu skickat informationen till Artistservice."""
