import os
from dotenv import load_dotenv
from google import genai

# Load environment variables from .env
load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    print("ERROR: GEMINI_API_KEY not found in .env file!")
    exit(1)

print("Found API Key. Connecting to Gemini...")

client = genai.Client(api_key=api_key)

try:
    response = client.models.generate_content(
        model="gemini-3.5-flash",
        contents="Say 'Gemini connection is working!' in exactly 5 words."
    )
    print("\nSUCCESS! Gemini Response:")
    print(response.text)
except Exception as e:
    print(f"\nError connecting to Gemini: {e}")
