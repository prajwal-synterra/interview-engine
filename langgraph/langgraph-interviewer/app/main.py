"""
Module 0 - Proof of Concept: Verify Gemini works via LangChain.
No FastAPI yet. Just a direct call to the LLM.
"""

import sys
import io
from dotenv import load_dotenv
from app.llm import get_llm

# Force UTF-8 output for Windows console compatibility
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

load_dotenv()

def main():
    print("[*] Testing Gemini connection via LangChain...")

    llm = get_llm()

    response = llm.invoke("Say 'Gemini is connected and ready!' and nothing else.")

    print("\n[OK] Gemini Response:")
    print(response.content)
    print("\n[DONE] Setup complete! Gemini is working correctly.")

if __name__ == "__main__":
    main()
