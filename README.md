# Job Matcher

A resume-driven job scraping and ranking pipeline for software roles. It scrapes multiple career sites, skips previously seen job URLs, scores only new postings by default, and publishes dated reports for local runs and GitHub Actions.

## Why another Resume Job Matcher?
There are a bunch of resume to job matchers in Github, but I am yet to find one which has a set of job urls with filters that I want that can be configured so that the tool can scrape those.

### But why not just use Indeed/Ziprecruiter or the scores of job search engine?
 - I find stale jobs from these sites occassionally. The career page of each company is perhaps the closest to the truth compared to these job search engine. This tool scrapes from all the career pages that you want to specify.
 - I want to find specifc search terms or absence of those. For example - one may want to find jobs that do not say "US citizen or GC holders only" or "visa sponsorship is not available". Or another one may only want to look at jobs that have such restrictions (perhaps to improve their chances).
 - Semantic searches with one's resume is still poor among many of these job search engines. Some parts of a job description are important to have a good match vs others (like Minimal qualifications vs Preferred qualifications). And parts of a job description perhaps are better for a lexical match rather than semantic.

## What It Does

- Scrapes multiple job board types: `workday`, `greenhouse`, `lever`, `custom`, and `custom-api`. You most likely are going to use custom or custom-api as this helps you configure for each company's careers website.
- Parses a PDF resume
- Uses an LLM to normalize resumes and job descriptions into structured fields such as required qualifications, preferred qualifications, named technologies, role family, seniority, and management expectations
- Scores the normalized fields deterministically using lexical overlap, local semantic similarity, qualification-gap penalties, and recency
- Stores results in SQLite so repeated runs avoid re-scraping and re-scoring known URLs
- Generates:
  - `job-matches.txt`
  - `job-matches.json`
- In GitHub Actions:
  - restores the resume and ATS cache from S3
  - writes output into a timestamped folder
  - uploads the latest artifacts back to S3
  - can optionally email the text report via Gmail SMTP

## Matcher Workflow

```mermaid
flowchart TD
    A[Resume Text] --> B[LLM Normalizer]
    C[Job Description] --> B
    B --> D[Structured Resume Profile]
    B --> E[Structured Job Profile]
    D --> F[Deterministic Matcher]
    E --> F
    F --> G[Lexical Score]
    F --> H[Semantic Score]
    F --> I[Qualification Gap Penalties]
    F --> J[Recency Score]
    G --> K[Weighted Final Score]
    H --> K
    I --> K
    J --> K
    K --> L[Ranked Jobs Report]
```

The LLM is used for extraction and normalization, not for the final score itself.

It converts noisy resume/job text into structured fields such as:
- required qualifications
- preferred qualifications
- named technologies
- role family
- seniority
- management expectations

The deterministic matcher then combines:
- lexical overlap on normalized skills
- semantic similarity from local embeddings
- qualification-gap penalties
- management and seniority alignment
- recency weighting

The final ATS score is a weighted combination of those deterministic signals.

## Automation Flow

```mermaid
flowchart TD
    A[GitHub Actions schedule or manual run] --> B[Restore resume and ATS cache from S3]
    B --> C[Run matcher]
    C --> D[Generate dated reports]
    D --> E[Upload reports and cache to S3]
    D --> F[Optional Gmail SMTP email with job-matches.txt]
```

## Processing Flow

1. Load config and apply environment overrides.
2. Open the SQLite cache DB and load known job URLs.
3. Parse the resume PDF.
4. Scrape configured job boards.
5. Skip URLs already known in the DB unless recompute logic requires a fresh scrape path.
6. Normalize the resume and each job description into structured fields.
7. Score jobs deterministically from those normalized fields.
8. Persist results back to SQLite.
9. Generate text and JSON reports.

## Repository Layout

```text
job-matcher/
├── config/jobs.yaml
├── requirements.txt
├── scripts/
│   ├── job_artifact_paths.py
│   └── send_report_email.py
├── src/
│   ├── main.py
│   ├── ats/
│   ├── config/
│   ├── output/
│   ├── parsers/
│   ├── scrapers/
│   └── storage/
└── output/
```

## Supported Job Boards

- `workday`
- `greenhouse`
- `lever`
- `custom`
- `custom-api`

## LLM Usage

The LLM is used to identify sections in the resume and job description and normalize them into structured fields.

Typical extracted fields include:
- required qualifications
- preferred qualifications
- required and preferred technologies
- role family
- seniority
- management type
- people-management requirements

This is intentionally different from asking the LLM to produce the final ATS score.

## Current Scoring Design

The scorer then operates on those normalized fields and combines:
- lexical score from normalized skills
- semantic score from local embeddings
- management and seniority alignment
- recency score
- penalties for weak or unsupported required qualifications
- lighter penalties for unsupported preferred qualifications

The built-in technology lexicon remains local and editable so concrete stack terms can be tuned over time.

## Caching Behavior

SQLite cache path:
- `job-matcher/output/ats-cache.sqlite`

Cache behavior:
- known job URL: skip re-scoring by default
- new job URL: scrape, score, and store
- `force_recompute: true`: rescore all jobs

"New jobs since last run" in reports means:
- the URL was not already present in the DB when the run started

## Configuration

Primary config file:
- [config/jobs.yaml](/Users/shankr/src/dada/job-matcher/config/jobs.yaml)

Key fields:

```yaml
resume_path: "./resume.pdf"
output_path: "./output/job-matches.txt"
ats_cache_db_path: "./output/ats-cache.sqlite"

llm:
  provider: "openrouter"
  api_key: "${OPENROUTER_KEY}"
  model: "deepseek/deepseek-v3.2"

scoring:
  force_recompute: false
  embedding_model: "BAAI/bge-small-en-v1.5"
```

### Environment Overrides

The app supports runtime overrides via environment variables:
- `JOB_MATCHER_FORCE_RECOMPUTE`
- `JOB_MATCHER_OUTPUT_PATH`

These are used by the GitHub Actions workflow so you do not need to commit YAML changes for one-off runs.

## Local Usage

From `job-matcher/`:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
python3 src/main.py
```

If you use OpenRouter for normalization, provide the key in the environment or `.env`:

```bash
OPENROUTER_KEY=your_key_here
```

## Output

Local default output path in config:
- `job-matcher/output/job-matches.txt`

In GitHub Actions, this is overridden to a dated folder like:
- `job-matcher/output/2026-04-07-1433/job-matches.txt`
- `job-matcher/output/2026-04-07-1433/job-matches.json`

The text report includes:
- summary counts
- new jobs since last run
- ranked listings
- ATS reasoning
- posted date and first-seen timestamps when available

## GitHub Actions

Workflow:
- [job-matcher.yml](/Users/shankr/src/dada/.github/workflows/job-matcher.yml)

It supports:
- scheduled daily runs
- manual runs via `workflow_dispatch`
- manual `force_recompute` input

### Action Inputs

Manual dispatch input:
- `force_recompute` (boolean, default `false`)

### AWS / GitHub Setup

Required GitHub secret:
- `AWS_ROLE_ARN`

Required GitHub variable:
- `JOB_MATCHER_RESUME_S3_KEY`

Optional GitHub variables for email delivery:
- `JOB_MATCHER_EMAIL_TO`
- `JOB_MATCHER_EMAIL_FROM`

Required GitHub secrets for Gmail SMTP:
- `JOB_MATCHER_SMTP_USERNAME`
- `JOB_MATCHER_SMTP_PASSWORD`

### S3 Behavior

The workflow:
- downloads resume PDF from S3
- restores `ats-cache.sqlite` from S3 if present
- runs the matcher
- uploads latest text report, JSON report, and cache DB back to S3

## Email Delivery

The workflow can email `job-matches.txt` through Gmail SMTP.

Requirements:
- set `JOB_MATCHER_EMAIL_TO`
- set `JOB_MATCHER_EMAIL_FROM`
- set `JOB_MATCHER_SMTP_USERNAME`
- set `JOB_MATCHER_SMTP_PASSWORD`
- use a Gmail app password, not the normal Gmail account password
- enable 2-step verification on the Gmail account first

## Custom Board Notes

### `custom`
Use for HTML pages scraped through Puppeteer selectors.

### `custom-api`
Use for JSON-backed career endpoints.

This is useful when a site renders listings from an API and the browser UI is not the real data source.

## Troubleshooting

### Jobs not found
- selector is stale
- page needs a "show more" interaction
- site is using an API rather than static HTML
- Workday DOM variant differs from your existing selectors

### Scores look too generous
- inspect the normalized required and preferred qualifications in the report
- increase qualification penalties when concrete stack gaps are underweighted
- expand the local tech lexicon when a concrete stack term is being missed
- run with `force_recompute` after changing scoring config

### Local embedding issues
- the first run downloads the embedding model
- model size affects first-run latency and local scoring speed

### GitHub Actions recompute
Use the manual action input instead of editing YAML:
- trigger workflow manually
- set `force_recompute=true`

## Recommended Next Documentation Updates

If this project keeps growing, the next useful split would be:
1. move workflow deployment details into `docs/deployment.md`
2. move custom-board recipes into `docs/boards.md`
3. keep this README as the top-level operational overview
