import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()


def get_api_keys():
    """Returns list of configured API keys (primary + fallback)."""
    keys = []
    primary = os.getenv("GOOGLE_API_KEY")
    fallback = os.getenv("FALLBACK_GOOGLE_API_KEY")
    if primary:
        keys.append(primary.strip())
    if fallback and fallback.strip() not in keys:
        keys.append(fallback.strip())
    return keys


def get_llm(api_key: str = None, model_name: str = None):
    """Initialize and return the Gemini LLM."""
    if not api_key:
        keys = get_api_keys()
        if not keys:
            raise ValueError("No GOOGLE_API_KEY or FALLBACK_GOOGLE_API_KEY found in environment.")
        api_key = keys[0]

    model = model_name or os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    return ChatGoogleGenerativeAI(
        model=model,
        google_api_key=api_key,
        temperature=0.7,
    )


def invoke_llm_with_fallback(llm_invoker_fn):
    """
    Executes an LLM call; if primary key fails with quota or rate limit,
    automatically retries with the fallback API key.
    """
    keys = get_api_keys()
    last_err = None
    for key in keys:
        try:
            return llm_invoker_fn(key)
        except Exception as err:
            last_err = err
            err_str = str(err).lower()
            if "429" in err_str or "quota" in err_str or "resource_exhausted" in err_str:
                print(f"[LLM] Primary key quota limit hit. Trying fallback API key...")
                continue
            raise err
    raise last_err
