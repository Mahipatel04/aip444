# tools.py - Shared tools used across all phases
# Includes: PDF reading, web search, WHOIS lookup, env loading

import os
import sys
import json
import requests
from datetime import datetime
from typing import Optional
from tavily import TavilyClient
from openai import OpenAI

# ─────────────────────────────────────────────
# LOAD ENV
# ─────────────────────────────────────────────

def load_env():
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    with open(env_path, "r", encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ[key.strip()] = value.strip()

load_env()

# Set up clients
client = OpenAI(
    api_key=os.environ["OPENROUTER_API_KEY"],
    base_url="https://openrouter.ai/api/v1",
)
tavily = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])

MODEL = "openai/gpt-4o-mini"
DEBUG = os.environ.get("DEBUG", "false").lower() == "true"


def log(msg: str):
    """Print debug message to stderr if debug mode is on."""
    if DEBUG:
        print(f"[DEBUG] {msg}", file=sys.stderr)


# ─────────────────────────────────────────────
# PDF READING
# ─────────────────────────────────────────────

def read_pdf(path: str) -> str:
    """Reads a PDF file and returns its text content."""
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(path)
        text = ""
        for page in doc:
            text += page.get_text()
        doc.close()
        log(f"Read PDF: {path} ({len(text)} chars)")
        return text
    except Exception as e:
        log(f"Error reading PDF {path}: {e}")
        return f"Error reading PDF: {str(e)}"


def read_docx(path: str) -> str:
    """Reads a Word document and returns its text content."""
    try:
        from docx import Document
        doc = Document(path)
        text = "\n".join([para.text for para in doc.paragraphs])
        log(f"Read DOCX: {path} ({len(text)} chars)")
        return text
    except Exception as e:
        log(f"Error reading DOCX {path}: {e}")
        return f"Error reading DOCX: {str(e)}"


def read_file(path: str) -> str:
    """Reads a PDF or Word file and returns text."""
    if path.lower().endswith(".pdf"):
        return read_pdf(path)
    elif path.lower().endswith(".docx"):
        return read_docx(path)
    else:
        return f"Unsupported file type: {path}"


# ─────────────────────────────────────────────
# WEB SEARCH
# ─────────────────────────────────────────────

def web_search(query: str, max_results: int = 5) -> str:
    """Searches the web using Tavily and returns formatted results."""
    try:
        log(f"Tool call: web_search('{query}')")
        results = tavily.search(query=query, max_results=max_results)
        formatted = f"Search results for '{query}':\n\n"
        for i, r in enumerate(results.get("results", []), 1):
            formatted += f"{i}. {r['title']}\n"
            formatted += f"   URL: {r['url']}\n"
            formatted += f"   {r['content'][:300]}\n\n"
        log(f"Search returned {len(results.get('results', []))} results")
        return formatted
    except Exception as e:
        log(f"Search error: {e}")
        return f"Search error: {str(e)}"


# ─────────────────────────────────────────────
# WHOIS LOOKUP
# ─────────────────────────────────────────────

def whois_lookup(domain: str) -> str:
    """
    Looks up WHOIS registration data for a domain.
    Returns registration date, registrar, and other info.
    """
    try:
        log(f"Tool call: whois_lookup('{domain}')")
        # Use WHOIS API
        response = requests.get(
            f"https://www.whoisxmlapi.com/whoisserver/WhoisService",
            params={
                "apiKey": os.environ.get("WHOIS_API_KEY", "at_demo"),
                "domainName": domain,
                "outputFormat": "JSON",
            },
            timeout=10,
        )

        if response.status_code != 200:
            # Fallback: use a free WHOIS lookup
            return whois_fallback(domain)

        data = response.json()
        registry = data.get("WhoisRecord", {})
        created = registry.get("createdDate", "unknown")
        expires = registry.get("expiresDate", "unknown")
        registrar = registry.get("registrarName", "unknown")
        registrant = registry.get("registrant", {}).get("organization", "unknown")

        result = f"WHOIS data for {domain}:\n"
        result += f"  Registered: {created}\n"
        result += f"  Expires: {expires}\n"
        result += f"  Registrar: {registrar}\n"
        result += f"  Registrant: {registrant}\n"

        log(f"WHOIS: domain {domain} registered {created}")
        return result

    except Exception as e:
        return whois_fallback(domain)


def whois_fallback(domain: str) -> str:
    """Fallback WHOIS using a free API."""
    try:
        response = requests.get(
            f"https://rdap.org/domain/{domain}",
            timeout=10,
        )
        if response.status_code == 200:
            data = response.json()
            events = data.get("events", [])
            dates = {}
            for event in events:
                action = event.get("eventAction", "")
                date = event.get("eventDate", "")
                if action in ["registration", "expiration", "last changed"]:
                    dates[action] = date

            result = f"WHOIS data for {domain}:\n"
            for action, date in dates.items():
                result += f"  {action}: {date}\n"

            entities = data.get("entities", [])
            for entity in entities:
                roles = entity.get("roles", [])
                if "registrar" in roles:
                    vcard = entity.get("vcardArray", [])
                    result += f"  Registrar info available\n"

            log(f"WHOIS fallback succeeded for {domain}")
            return result
        else:
            return f"WHOIS lookup failed for {domain}: HTTP {response.status_code}"
    except Exception as e:
        return f"WHOIS lookup failed for {domain}: {str(e)}"


# ─────────────────────────────────────────────
# LLM CALL WITH STRUCTURED OUTPUT
# ─────────────────────────────────────────────

def call_llm_structured(
    system_prompt: str,
    user_message: str,
    response_schema,
    model: str = MODEL,
):
    """
    Calls the LLM and returns a validated Pydantic object.
    Uses structured outputs to guarantee valid JSON.
    """
    try:
        log(f"LLM call: {model}")
        response = client.beta.chat.completions.parse(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            response_format=response_schema,
            temperature=0.2,
        )
        result = response.choices[0].message.parsed
        log(f"Structured output validation: passed")
        return result
    except Exception as e:
        log(f"LLM error: {e}")
        raise


def call_llm_text(
    system_prompt: str,
    user_message: str,
    model: str = MODEL,
) -> str:
    """Calls the LLM and returns plain text response."""
    try:
        log(f"LLM call (text): {model}")
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=0.3,
        )
        return response.choices[0].message.content
    except Exception as e:
        log(f"LLM error: {e}")
        raise


# ─────────────────────────────────────────────
# TOOL DEFINITIONS FOR LLM TOOL CALLING
# ─────────────────────────────────────────────

SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": "Search the web for information about companies, job market trends, skills, and salaries",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query"
                }
            },
            "required": ["query"]
        }
    }
}

WHOIS_TOOL = {
    "type": "function",
    "function": {
        "name": "whois_lookup",
        "description": "Look up WHOIS domain registration data to check how old a company domain is",
        "parameters": {
            "type": "object",
            "properties": {
                "domain": {
                    "type": "string",
                    "description": "Domain name to look up e.g. acmecorp.com"
                }
            },
            "required": ["domain"]
        }
    }
}


def execute_tool(name: str, args: dict) -> str:
    """Executes a tool by name and returns the result."""
    if name == "web_search":
        return web_search(args["query"])
    elif name == "whois_lookup":
        return whois_lookup(args["domain"])
    else:
        return f"Unknown tool: {name}"