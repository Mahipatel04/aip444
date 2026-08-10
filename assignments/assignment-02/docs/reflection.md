# Reflection — Assignment 2: Job Search Assistant

## 1. Did you structure your phases as workflows, agents, or a hybrid?

I used a hybrid approach. Phases 1 and 2 are deterministic pipelines with tool calling loops embedded inside — the LLM can call web_search when it needs company info or gap advice, but the overall flow is scripted step by step. Phase 3 is more agentic — the legitimacy agent runs in a loop deciding what to search and when to use WHOIS, without me scripting exactly which searches to do. I chose this because Phases 1 and 2 have clear predictable steps while legitimacy assessment genuinely needs autonomous investigation since every company is different.

## 2. Which prompt engineering choices most improved extraction consistency?

The biggest improvement came from being very explicit about null handling — telling the LLM to use null or "not listed" instead of guessing. Before adding that instruction, the model would invent salary ranges and education requirements that weren't in the posting. I also added few-shot examples for the slug format which made that field consistent across all 11 postings. Using structured outputs with Pydantic was the most impactful overall since it completely eliminated JSON formatting errors.

## 3. How did you design the legitimacy agent? What signals did you prioritize?

I prioritized WHOIS domain age as the most reliable signal since it's objective and hard to fake. A company with a domain registered in 1995 is almost certainly real. I also prioritized contact email domain matching since scammers almost always use Gmail or generic emails. The main limitation is that WHOIS privacy services hide registrant info for many legitimate companies too, so the agent sometimes can't determine much beyond the registration date. I would improve it by adding a Google Safe Browsing API check and a LinkedIn company page verification.

## 4. What models did you use and how did cost influence your choices?

I used openai/gpt-4o-mini for all phases. It's cheap, fast, and very good at following structured output schemas. Each Phase 1 run costs roughly $0.02-0.05 per posting depending on how much company research it does. A full Phase 3 run costs about $0.10-0.15 including legitimacy research. Total development cost was under $2.00 which is well within budget. I considered using a cheaper model like gemini-flash-lite for the market analysis report but gpt-4o-mini produced noticeably better structured extraction so I kept it consistent.

## 5. Coding agent process for Phase 3

I built Phase 3 primarily using Claude as my coding assistant. My initial instruction was to build an application advisor that takes a job posting PDF and produces an HTML report with five sections matching the assignment spec. The agent produced a working first version in about 3 iterations. What it got right: the overall structure, the HTML template, and the tool calling loop pattern. What it got wrong: it used the old dict-style message appending for tool calls which caused the ChatCompletionMessage attribute errors I had to fix manually. I also had to manually add the WHOIS fallback logic since the agent's first version assumed a paid WHOIS API key was available.

## 6. What other AI tools did you use?

I used Claude throughout the entire assignment for code generation, debugging, and writing. One specific instance where it helped: when I got the ChatCompletionMessage attribute error in phase1.py, Claude immediately identified that the OpenAI SDK returns Pydantic objects not dicts and gave me the exact fix. One instance where I had to significantly correct it: Claude initially generated the phase2.py gap analysis using a for loop that called the LLM once per gap to do web searches, which would have been extremely slow and expensive. I rewrote it to batch all the gap research into a single tool calling session instead.