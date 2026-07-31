# agent.py - Source Credibility Analyzer Agent
# Uses OpenAI Agents SDK with OpenRouter to evaluate source credibility
# Usage: python agent.py <url>

import asyncio
import os
import sys
import json
import requests
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
from tavily import TavilyClient

from agents import Agent, Runner, function_tool, ModelSettings
from agents.models.openai_provider import OpenAIProvider
from openai import AsyncOpenAI

# ─────────────────────────────────────────────
# LOAD ENV
# ─────────────────────────────────────────────

def load_env():
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    with open(env_path, "r", encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ[key.strip()] = value.strip()

load_env()

tavily_client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])

# ─────────────────────────────────────────────
# CUSTOM MODEL PROVIDER FOR OPENROUTER
# ─────────────────────────────────────────────

openrouter_client = AsyncOpenAI(
    api_key=os.environ["OPENROUTER_API_KEY"],
    base_url="https://openrouter.ai/api/v1",
)

provider = OpenAIProvider(openai_client=openrouter_client)
MODEL = "openai/gpt-4o-mini"


# ─────────────────────────────────────────────
# TOOL 1: READ URL
# Fetches a webpage as clean markdown using Jina Reader
# ─────────────────────────────────────────────

@function_tool
def read_url(url: str) -> str:
    """
    Reads a webpage and returns its content as Markdown.
    Use this to read the source being evaluated, About pages,
    author bios, editorial policies, and corroborating articles.
    """
    try:
        response = requests.get(
            f"https://r.jina.ai/{url}",
            headers={"Accept": "text/markdown"},
            timeout=15,
        )
        if response.status_code != 200:
            return f"❌ Error reading URL: HTTP {response.status_code}"
        return response.text[:10000]
    except Exception as e:
        return f"❌ Error reading URL: {str(e)}"


# ─────────────────────────────────────────────
# TOOL 2: WEB SEARCH
# Searches the web using Tavily
# ─────────────────────────────────────────────

@function_tool
def web_search(query: str) -> str:
    """
    Searches the web for information about authors, publications,
    claims, fact-checks, and corroborating sources.
    Use this to investigate the author's credentials, the publication's
    reputation, and whether claims are supported by other sources.
    """
    try:
        results = tavily_client.search(query=query, max_results=5)
        formatted = f"Search results for '{query}':\n\n"
        for i, r in enumerate(results.get("results", []), 1):
            formatted += f"{i}. {r['title']}\n"
            formatted += f"   URL: {r['url']}\n"
            formatted += f"   {r['content'][:300]}\n\n"
        return formatted
    except Exception as e:
        return f"❌ Search error: {str(e)}"


# ─────────────────────────────────────────────
# TOOL 3: ASSESS CREDIBILITY (The "Think" Tool)
# Forces the agent to structure its thinking before writing the report
# ─────────────────────────────────────────────

class AuthorInfo(BaseModel):
    name: str = Field(description="Author name. Write 'Unknown' if not found after investigation")
    credentials: str = Field(description="Author qualifications and expertise. If not found, describe what you searched for")
    credibility_assessment: str = Field(description="Your assessment of the author's credibility based on your research")

class PublicationInfo(BaseModel):
    name: str = Field(description="Publication or website name")
    reputation: str = Field(description="What your research revealed about this publication's reputation")
    editorial_process: str = Field(description="One of: peer_reviewed, editor_reviewed, self_published, unknown")

class ContentAnalysis(BaseModel):
    claims_supported_by_evidence: bool = Field(description="Are main claims backed by data, citations, or primary sources?")
    sources_cited: bool = Field(description="Does the article cite its sources?")
    corroborated_by_other_sources: bool = Field(description="Did you find other credible sources reporting the same claims?")
    contradicted_by_other_sources: bool = Field(description="Did you find credible sources that contradict the claims?")
    primary_vs_secondary: str = Field(description="One of: primary_source, secondary_source, tertiary_source")
    funding_or_sponsorship: str = Field(description="Evidence of who funds the publication or research")
    date_published: str = Field(description="When was this published? Is it current?")

class CredibilityEvaluation(BaseModel):
    source_url: str = Field(description="The URL being evaluated")
    source_type: str = Field(description="One of: peer_reviewed_journal, news_organization, government_agency, nonprofit_organization, corporate_blog, personal_blog, social_media, wiki, unknown")
    author: AuthorInfo
    publication: PublicationInfo
    content_analysis: ContentAnalysis
    transparency_score: int = Field(description="1-5 rating of how transparent the source is. 1=very opaque, 5=very transparent", ge=1, le=5)
    overall_credibility: str = Field(description="One of: high, medium, low, very_low")
    reasoning: str = Field(description="Explain your overall credibility rating, citing specific evidence from your research")

@function_tool
def assess_credibility(evaluation: CredibilityEvaluation) -> dict:
    """
    Use this tool to formally record your structured credibility assessment
    BEFORE writing the final report. This forces you to organize all your
    findings into a complete, structured evaluation. Every field must be
    based on evidence you actually found — do not guess or make up information.
    Fill out every field carefully.
    """
    return {
        "status": "evaluation_recorded",
        "evaluation": evaluation.model_dump()
    }


# ─────────────────────────────────────────────
# TOOL 4: SAVE REPORT
# Writes the final markdown report to disk
# ─────────────────────────────────────────────

@function_tool
def save_report(filename: str, content: str) -> str:
    """
    Saves the final credibility report as a Markdown file.
    Use this as the LAST step after completing your assessment.
    The filename should be descriptive (e.g., 'reuters-article-report.md').
    """
    try:
        os.makedirs("reports", exist_ok=True)
        filepath = os.path.join("reports", filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        return f"✅ Report saved to: {filepath}"
    except Exception as e:
        return f"❌ Error saving report: {str(e)}"


# ─────────────────────────────────────────────
# SYSTEM PROMPT
# ─────────────────────────────────────────────

SYSTEM_PROMPT = """
You are a Research Source Credibility Analyzer. Your job is to thoroughly investigate
a given URL and produce a detailed, evidence-based credibility report.

## Your Investigation Process

Follow these steps in order:

1. READ THE SOURCE
   - Use read_url to fetch and read the article or page being evaluated
   - Identify: main claims, author name, publication, date published
   - Note the tone: is it neutral and informational, or emotional and persuasive?

2. INVESTIGATE THE AUTHOR
   - Use web_search to search for the author's full name and credentials
   - Look for their other published work, affiliations, and expertise
   - Search: "[author name] credentials", "[author name] journalist/researcher"
   - Use read_url to read their bio page if you find one

3. INVESTIGATE THE PUBLICATION
   - Use web_search to research the publication's reputation
   - Use read_url to read the "About" page on the same domain
   - Search: "[publication name] editorial standards", "[publication name] bias"
   - Determine if it has an editorial review process

4. VERIFY THE CLAIMS
   - Pick 2-3 key claims from the article
   - Use web_search to find other sources reporting the same claims
   - Search for fact-checks or contradicting evidence
   - Note whether claims are corroborated or contradicted

5. CHECK FOR BIAS
   - Is the language neutral or emotionally charged?
   - Does it present multiple perspectives or only one side?
   - Who funds or sponsors this publication?

6. ASSESS
   - Use the assess_credibility tool to formally record your structured evaluation
   - Fill out EVERY field based on actual evidence you found
   - NEVER guess or make up information — if unknown, say what you searched for

7. WRITE AND SAVE THE REPORT
   - Use save_report to write a complete Markdown credibility report
   - Include: summary, author analysis, publication analysis, claim verification,
     bias indicators, structured evaluation, and final verdict with reasoning
   - Cite specific URLs and evidence for your conclusions

## Handling Missing Information
- If author is unknown: Check About/Team/Contact pages on the same domain.
  Search for the article title in quotes. Record anonymous authorship as a credibility concern.
- If publication is unknown: Read its About page. Search for the domain name.
  Note this as a concern but don't automatically dismiss the content.
- If claims can't be verified: Distinguish between "found contradicting evidence"
  vs "found no evidence either way" — these are very different situations.
- If URL fails to load: Note the error and search for cached versions or descriptions
- NEVER fabricate information to fill gaps. "I could not determine..." is always better than a guess.

## Important Rules
- You must use assess_credibility before save_report
- Base every judgment on evidence from your actual research
- Be thorough — do at least 4-6 searches before making your assessment
- If something looks credible on the surface, dig deeper
""".strip()


# ─────────────────────────────────────────────
# MAIN - ASSEMBLE AND RUN THE AGENT
# ─────────────────────────────────────────────

async def main():
    if len(sys.argv) < 2:
        print("Usage: python agent.py <url>")
        print("Example: python agent.py https://www.reuters.com/article/...")
        sys.exit(1)

    url = sys.argv[1]
    print(f"\n🔍 Analyzing source credibility: {url}")
    print("=" * 60)

    # Create the agent
    agent = Agent(
        name="CredibilityAnalyzer",
        instructions=SYSTEM_PROMPT,
        tools=[read_url, web_search, assess_credibility, save_report],
        model=MODEL,
        model_settings=ModelSettings(temperature=0.2),
    )

    # Run the agent
    result = await Runner.run(
        agent,
        input=f"Evaluate the credibility of this source: {url}",
        max_turns=25,
        run_config={"model_provider": provider},
    )

    print("\n" + "=" * 60)
    print("✅ Agent completed!")
    print(f"Final response: {result.final_output}")


if __name__ == "__main__":
    asyncio.run(main())