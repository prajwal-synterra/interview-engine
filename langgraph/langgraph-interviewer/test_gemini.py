"""
Module 1 - Direct Gemini API test.
No LangGraph. Just: Python -> Gemini -> Response
"""

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()

llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash"
)

response = llm.invoke(
    "Give me one Java interview question"
)

print(response.content)
