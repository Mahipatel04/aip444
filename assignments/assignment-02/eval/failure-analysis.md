# Failure Analysis & Overall Observations

## Failure 1: Posting Age Calculation

**What happened:** For Job Posting 2 (InfoTrack Canada), the posting_age_days field was set to null even though the PDF showed "Posted 3 days ago" text. The extractor missed this relative date indicator.

**Why it happened:** The system prompt told the LLM to look for explicit dates, but the relative date format "Posted X days ago" was in a part of the PDF that PyMuPDF extracted with inconsistent formatting, making it hard for the LLM to detect.

**What I would change:** Add explicit instructions in the extraction prompt to look for relative date phrases like "Posted X days ago" or "X days ago" and calculate from those. Also add a post-processing step to clean up PDF text before sending to the LLM.

---

## Failure 2: Company Research Depth

**What happened:** For smaller companies like Accuenergy, the company research section returned very generic information ("fast-growing company") rather than specific useful details like employee count, recent funding, or Glassdoor ratings.

**Why it happened:** The web search queries were too generic ("Accuenergy company info"). Smaller companies have less web presence so broad searches don't return detailed results.

**What I would change:** Make the search queries more targeted — search specifically for "[company] Glassdoor reviews", "[company] LinkedIn employees", "[company] Crunchbase" to get more structured data from specific sources.

---

## Overall Summary

**What the system does well:**
- Structured extraction is very reliable for well-formatted job postings
- Salary ranges and required skills are captured accurately
- The legitimacy agent is good at identifying obvious red flags and green flags
- The HTML report is clear and visually well-organized
- The fit scoring is encouraging rather than discouraging

**Where it falls short:**
- Relative date extraction is inconsistent
- Company research quality varies significantly based on company size/web presence
- Phase 3 can be slow (2-3 minutes) due to multiple LLM and search API calls
- The gap analysis triage could be more specific for candidates with limited experience