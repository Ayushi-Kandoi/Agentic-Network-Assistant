import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()

def _base_llm(temperature: float) -> ChatOpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    langchain_api_key = os.getenv("LANGCHAIN_API_KEY")

    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. "
            "Add it to your .env file before starting the server."
        )

    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_PROJECT"] = "Agentic_Network_Assistance"

    if not langchain_api_key:
        os.environ["LANGCHAIN_TRACING_V2"] = "false"
        print("LangSmith tracing disabled — LANGCHAIN_API_KEY not set")
    else:
        print(f"LangSmith tracing enabled. Project: {os.environ['LANGCHAIN_PROJECT']}")

    return ChatOpenAI(
        model="gpt-4o-mini",
        temperature=temperature,
        api_key=api_key,
    )


def get_llm() -> ChatOpenAI:
    """Agent LLM — slight creativity for reasoning (temp=0.3)"""
    return _base_llm(temperature=0.3)


def get_rag_llm() -> ChatOpenAI:
    """RAG LLM — deterministic for factual retrieval (temp=0)"""
    return _base_llm(temperature=0)