# schemas.py - Pydantic schemas for structured outputs
# Used by all three phases to validate LLM responses

from pydantic import BaseModel, Field
from typing import Optional, List


# ─────────────────────────────────────────────
# PHASE 1: JOB POSTING SCHEMA
# ─────────────────────────────────────────────

class CompanyResearch(BaseModel):
    company_size: str = Field(description="Company size e.g. startup, SME, enterprise, unknown")
    industry: str = Field(description="Industry sector")
    recent_news: str = Field(description="Recent news or developments about the company")
    culture_signals: str = Field(description="Culture signals from reviews, blogs, social media")
    founded_year: Optional[str] = Field(description="Year company was founded if found")

class JobPosting(BaseModel):
    job_title: str = Field(description="Exact job title from the posting")
    company_name: str = Field(description="Company name")
    location: str = Field(description="Location or remote status")
    posting_age_days: Optional[int] = Field(description="How many days old the posting is. null if date not found")
    required_skills: List[str] = Field(description="Required hard skills and technologies")
    preferred_skills: List[str] = Field(description="Nice-to-have or preferred skills")
    experience_level: str = Field(description="Years of experience and seniority level required")
    education_requirements: str = Field(description="Education requirements. 'not listed' if not mentioned")
    salary_range: Optional[str] = Field(description="Salary range if listed. null if not mentioned")
    key_responsibilities: List[str] = Field(description="Main job responsibilities")
    company_research: Optional[CompanyResearch] = Field(description="Research findings about the company")
    slug: str = Field(description="URL-friendly identifier e.g. senior-dev-acme-corp")


# ─────────────────────────────────────────────
# PHASE 1: MARKET ANALYSIS SCHEMA
# ─────────────────────────────────────────────

class SkillFrequency(BaseModel):
    skill: str
    count: int
    percentage: float

class MarketAnalysis(BaseModel):
    total_postings_analyzed: int
    top_required_skills: List[SkillFrequency] = Field(description="Most common required skills across all postings")
    top_preferred_skills: List[SkillFrequency] = Field(description="Most common preferred skills")
    common_experience_levels: List[str] = Field(description="Most common experience levels required")
    salary_insights: str = Field(description="Summary of salary ranges found across postings")
    common_responsibilities: List[str] = Field(description="Most common job responsibilities")
    education_trends: str = Field(description="Common education requirements")
    industry_trends: str = Field(description="Notable trends and observations across all postings")
    culture_insights: str = Field(description="Common culture signals and expectations")


# ─────────────────────────────────────────────
# PHASE 2: RESUME SCHEMA
# ─────────────────────────────────────────────

class WorkExperience(BaseModel):
    role: str
    company: str
    duration: str
    responsibilities: List[str]

class ResumeData(BaseModel):
    full_name: str
    hard_skills: List[str] = Field(description="Programming languages, frameworks, tools, platforms")
    soft_skills: List[str] = Field(description="Communication, leadership, collaboration skills")
    work_experience: List[WorkExperience]
    education: List[str] = Field(description="Degrees, institutions, relevant coursework")
    certifications: List[str] = Field(description="Professional certifications and completed courses")
    projects: List[str] = Field(description="Notable projects and accomplishments")
    keywords: List[str] = Field(description="Industry-specific terminology and methodologies")
    total_years_experience: Optional[float] = Field(description="Estimated total years of work experience")


# ─────────────────────────────────────────────
# PHASE 2: GAP ANALYSIS SCHEMA
# ─────────────────────────────────────────────

class Gap(BaseModel):
    skill_or_area: str
    level: str = Field(description="One of: quick_win, short_term, medium_term, long_term")
    description: str = Field(description="Specific actionable advice to address this gap")
    effort_estimate: str = Field(description="Realistic time/effort estimate")

class GapAnalysis(BaseModel):
    strengths: List[str] = Field(description="Skills and qualifications you have that are commonly requested")
    gaps: List[Gap] = Field(description="Skills missing from resume but common in market")
    unique_value: List[str] = Field(description="Things you bring that differentiate you")
    overall_market_readiness: str = Field(description="Overall assessment of readiness for this market")


# ─────────────────────────────────────────────
# PHASE 3: APPLICATION REPORT SCHEMA
# ─────────────────────────────────────────────

class LegitimacySignal(BaseModel):
    signal: str
    type: str = Field(description="red_flag or green_flag")
    evidence: str

class LegitimacyAssessment(BaseModel):
    verdict: str = Field(description="One of: legitimate, caution, suspicious, fraudulent")
    confidence: str = Field(description="high, medium, or low")
    signals: List[LegitimacySignal]
    recommendation: str = Field(description="Clear recommendation to the user")

class FitScore(BaseModel):
    overall_percentage: float = Field(description="Overall fit percentage 0-100")
    recommendation: str = Field(description="Should apply, stretch, growth target etc")
    matched_requirements: List[str]
    gaps: List[str]
    reasoning: str

class ApplicationReport(BaseModel):
    legitimacy: LegitimacyAssessment
    fit_score: FitScore
    resume_adaptations: List[str] = Field(description="Specific resume changes to make")
    cover_letter_points: List[str] = Field(description="Key points to hit in cover letter")
    interview_questions: List[str] = Field(description="Likely interview questions")
    skills_to_brush_up: List[str] = Field(description="Things to review before interview")
    company_research_points: List[str] = Field(description="Things to research about the company")