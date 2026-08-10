# Assignment 2: Job Search Assistant

An AI-powered job search assistant that analyzes job postings, evaluates your resume, and produces comprehensive application reports.

## Setup

### 1. Install dependencies
```bash
pip install openai pydantic requests tavily-python pymupdf python-docx
```

### 2. Configure environment variables
Copy `.env.example` to `.env` and fill in your keys:
```bash
cp .env.example .env
```

Required keys:
OPENROUTER_API_KEY=your-openrouter-key
TAVILY_API_KEY=your-tavily-key

### 3. Add your files
- Drop job posting PDFs into `input/jobs/`
- Drop your resume PDF into `input/` as `resume.pdf`

---

## How to Run

### Phase 1: Job Market Analysis
Processes all job posting PDFs and produces a market analysis report.
```bash
python src/phase1.py
```
- Skips postings already processed (safe to re-run)
- Output: `data/jobs/*.json`, `data/analysis/market-analysis.json`, `reports/market-analysis.md`

### Phase 2: Resume Gap Analysis
Parses your resume and compares it against the market analysis.
```bash
python src/phase2.py input/resume.pdf
```
- Requires Phase 1 to be completed first
- Output: `data/resume/resume.json`, `data/analysis/gap-analysis.json`, `reports/gap-analysis.md`

### Phase 3: Application Advisor
Takes a new job posting and produces a full application report.
```bash
python src/phase3.py input/jobs/new-posting.pdf
```
- Requires Phase 1 and 2 to be completed first
- Output: `reports/application-report.html`

### Debug Mode
Add `DEBUG=true` to see detailed logs:
```bash
DEBUG=true python src/phase1.py
```

---

## Evaluation
Evaluation files are in `eval/`:
- `eval/extraction-spot-check.md` — Extraction accuracy check
- `eval/scoring-check.md` — Fit scoring evaluation
- `eval/legitimacy-check.md` — Legitimacy agent evaluation
- `eval/failure-analysis.md` — Failure analysis

## Reflection
See `docs/reflection.md` for full written reflection.