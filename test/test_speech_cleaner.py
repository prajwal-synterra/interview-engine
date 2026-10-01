import re
from typing import Dict

TECHNICAL_HOMOPHONES: Dict[str, str] = {
    # Competitions & Clubs
    r"\b(?:hack\s*account|hacks\s*account|wants\s*account|won\s*hack\s*account|won\s*many\s*hack\s*account|one\s*many\s*hack\s*account)\b": "hackathons",
    r"\b(?:hack\s*accounts|hacks\s*accounts)\b": "hackathons",
    r"\b(?:tickler\s*called|tickler)\b": "technical club",

    # Databases & Caching
    r"\b(?:post\s*grasis(?:\s*12)?|post\s*grace|post\s*gray|post\s*gre|postgress)\b": "PostgreSQL",
    r"\b(?:casing\s*memories|casing\s*memory|case\s*memory|against\s*memory)\b": "cache memory",
    r"\b(?:casing)\b": "caching",
    r"\b(?:red\s*is|rediss)\b": "Redis",
    r"\b(?:no\s*sequel|no\s*sql)\b": "NoSQL",
    r"\b(?:sequel\s*database|sequel\s*server|sequel\s*db)\b": "SQL database",
    r"\b(?:sequel)\b": "SQL",

    # Containers & Cloud
    r"\b(?:doctor|docter)\b": "Docker",
    r"\b(?:cubernetis|coobernetes|koobernetes|k8s)\b": "Kubernetes",
    r"\b(?:a\s*w\s*s|a\s*w\s*switches)\b": "AWS",
    r"\b(?:engine\s*x|n\s*jinx)\b": "Nginx",

    # AI, ML & Math Models
    r"\b(?:the\s*lumps|the\s*llms|l\s*l\s*m\s*s|llm's|llm)\b": "LLMs",
    r"\b(?:rag\s*ways|rag\s*based|rag\s*base)\b": "RAG-based",
    r"\b(?:rag)\b": "RAG",
    r"\b(?:b\s*k\s*d|b\s*k\s*t)\b": "BKT",
    r"\b(?:d\s*k\s*t|h\s*h\s*t\s*k)\b": "DKT",
    r"\b(?:m\s*i\s*r\s*t)\b": "MIRT",
    r"\b(?:pie\s*torch|py\s*torch)\b": "PyTorch",
    r"\b(?:ten\s*sir\s*flow|tens\s*of\s*flow)\b": "TensorFlow",

    # Networking, Frameworks & Concurrency
    r"\b(?:net\s*tea|neddy)\b": "Netty",
    r"\b(?:rabbit\s*m\s*q)\b": "RabbitMQ",
    r"\b(?:graph\s*q\s*l)\b": "GraphQL",
    r"\b(?:web\s*socket|web\s*sockets)\b": "WebSockets",
    r"\b(?:fast\s*a\s*p\s*i)\b": "FastAPI",
    r"\b(?:rest\s*a\s*p\s*i|rest\s*apis|rest\s*api)\b": "REST API",
    r"\b(?:t\s*t\s*l)\b": "TTL",
    r"\b(?:c\s*i\s*c\s*d|c\s*i\s*/\s*c\s*d)\b": "CI/CD",

    # Common Speech-to-Text Acoustic Glitches
    r"\b(?:you\s*driving\s*data|u\s*driving\s*data)\b": "retrieving data",
    r"\b(?:red\s*and\s*n\s*c|red\s*and\s*nc|red\s*and\s*c)\b": "redundancy",
    r"\b(?:soil\s*using)\b": "so I'll use",
    r"\b(?:free\s*define|free\s*defined)\b": "predefined",
    r"\b(?:order\s*to\s*order)\b": "audio-to-audio",
    r"\b(?:seril)\b": "several",
    r"\b(?:germany\s*the\s*people|germany\s*people)\b": "concurrency of people",
}


def deduplicate_transcript(text: str) -> str:
    """Removes accidental duplications from STT buffers or repeated clauses."""
    if not text:
        return ""
    text = text.strip()

    # Pattern 1: Double spaces separating identical halves (e.g. "Sentence A  Sentence A")
    parts = [p.strip() for p in re.split(r'\s{2,}', text) if p.strip()]
    if len(parts) == 2 and parts[0].lower() == parts[1].lower():
        return parts[0]

    # Pattern 2: Word-based identical halves
    words = text.split()
    n = len(words)
    if n >= 6:
        half = n // 2
        first_half = " ".join(words[:half]).lower()
        second_half = " ".join(words[half:half*2]).lower()
        if first_half == second_half:
            remainder = (" " + " ".join(words[half*2:])) if n > half*2 else ""
            # If remainder is just "and text" or filler, drop it
            if remainder.strip().lower() in ["and text", "and", ""]:
                return " ".join(words[:half])
            return " ".join(words[:half]) + remainder

    # Pattern 3: Repeated consecutive duplicate phrases (3+ words repeated)
    # e.g., "can you please repeat the question can you please repeat the question"
    cleaned = re.sub(r'(\b[\w\s]{12,}\b)\s+\1\b', r'\1', text, flags=re.IGNORECASE)
    return cleaned.strip()


def clean_candidate_transcript(text: str) -> str:
    """Applies deduplication and domain terminology corrections."""
    if not text or not text.strip():
        return ""

    text = deduplicate_transcript(text)

    # Apply technical homophone normalization
    for pattern, replacement in TECHNICAL_HOMOPHONES.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

    # Clean multiple spaces
    text = re.sub(r'\s+', ' ', text).strip()
    return text


if __name__ == "__main__":
    # Test cases from interview_engine.log
    test_cases = [
        (
            "can you please repeat the question  can you please repeat the question",
            "can you please repeat the question"
        ),
        (
            "my name is Prajwal and I have also one many hack Account right now I doing a major project",
            "hackathons"
        ),
        (
            "Sabhi will be having a primary data centre with the help of database or any post grasis 12 but when it comes to the casing memories that means what a we are doing data which are needed primarily for us for the 24 hour for the next 24 hours were storing it in the case memory",
            "PostgreSQL"
        ),
        (
            "kahan per handing consists and data what has been Centre will be using red is or Storage for the against memory which is also provided by the AWS and also we are replying to do containerisation of all the things using doctor and using a w switches",
            "Docker"
        ),
        (
            "currently we are using directly the Gemini is API key that is audio based model live model using which we will be taking order to order translation and using seril algorithms like a b k d h h t k",
            "BKT"
        ),
        (
            "using that Rag ways data questions we will be answering or a Sporting in front of the questions and evaluation happens completely without the lumps so there is no need of LLM",
            "RAG-based"
        ),
        (
            "you driving data",
            "retrieving data"
        )
    ]

    for raw, expected_token in test_cases:
        res = clean_candidate_transcript(raw)
        print(f"RAW:      {raw}")
        print(f"CLEANED:  {res}")
        assert expected_token.lower() in res.lower(), f"Expected '{expected_token}' in '{res}'"
        print("PASS\n")

    print("All speech cleaning tests passed successfully!")
