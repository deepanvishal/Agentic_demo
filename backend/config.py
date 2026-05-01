import os
import logging
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
GMAIL_ADDRESS: str = os.getenv("GMAIL_ADDRESS", "")
GMAIL_APP_PASSWORD: str = os.getenv("GMAIL_APP_PASSWORD", "")
LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "claude")
CHROMA_PERSIST_PATH: str = os.getenv("CHROMA_PERSIST_PATH", "./chroma_db")
SQLITE_PATH: str = os.getenv("SQLITE_PATH", "./db/contracts.db")

CLAUDE_MODEL = "claude-sonnet-4-20250514"
CLAUDE_MAX_TOKENS = 1000
OLLAMA_MODEL = "llama3:8b-instruct"
OLLAMA_BASE_URL = "http://localhost:11434"

CORPUS_COLLECTION = "corpus"
NEW_CONTRACTS_COLLECTION = "new_contracts"


def get_llm_client():
    """Return the underlying LLM client based on LLM_PROVIDER."""
    if LLM_PROVIDER == "claude":
        import anthropic
        return anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    else:
        from langchain_community.llms import Ollama
        return Ollama(model=OLLAMA_MODEL, base_url=OLLAMA_BASE_URL)


def call_llm(prompt: str, max_tokens: int = CLAUDE_MAX_TOKENS) -> str:
    """Unified LLM call that routes to Claude or Ollama based on LLM_PROVIDER."""
    if LLM_PROVIDER == "claude":
        import anthropic
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text
    else:
        from langchain_community.llms import Ollama
        llm = Ollama(model=OLLAMA_MODEL, base_url=OLLAMA_BASE_URL)
        return llm.invoke(prompt)


def extract_json_str(text: str) -> str:
    """Extract a JSON object string from an LLM response that may include markdown or prose."""
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]
    return text
