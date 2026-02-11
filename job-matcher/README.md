# Job Scraper with ATS Matching

An automated job scraping application that searches multiple job boards, extracts job listings, and uses AI-powered ATS (Applicant Tracking System) scoring to rank jobs based on how well they match your resume.

## Features

- 🤖 **Browser Automation**: Uses Puppeteer to scrape job listings from multiple sources
- 📄 **PDF Resume Parsing**: Extracts text from your resume PDF
- 🎯 **ATS Scoring**: AI-powered matching using LLMs (Groq, Gemini, OpenRouter, or Ollama)
- 📊 **Ranked Results**: Jobs sorted by match score with detailed analysis
- 🔄 **Pagination Support**: Automatically navigates through multiple pages of results
- 📱 **Multiple Job Boards**: Supports Workday, Greenhouse, Lever, and custom job boards

## Supported Job Boards

- **Workday**: Common enterprise job board (e.g., `company.wd101.myworkdayjobs.com`)
- **Greenhouse**: Popular startup/SaaS job board (e.g., `boards.greenhouse.io`)
- **Lever**: Another popular startup job board (e.g., `jobs.lever.co`)
- **Custom**: Configure for any job site with custom selectors

## LLM Providers (Free Options)

1. **Groq** (Recommended - Free Tier)
   - Sign up: https://console.groq.com
   - Free tier: 14,400 tokens/min, 1,440 requests/day
   - Models: llama-3.1-8b-instant, llama-3.1-70b-versatile, mixtral-8x7b-32768

2. **Gemini** (Free Tier)
   - Sign up: https://ai.google.dev
   - Free tier: 1,500 requests/day
   - Model: gemini-pro

3. **OpenRouter** (Free Tier)
   - Sign up: https://openrouter.ai
   - Access to multiple free models
   - Model: mistralai/mistral-7b-instruct:free

4. **Ollama** (Completely Free - Local)
   - Install: https://ollama.ai
   - Runs locally, no API key needed
   - Models: llama2, mistral, codellama, etc.

## Installation

```bash
# Clone or navigate to the project
cd job-scraper

# Install dependencies
npm install

# Copy environment template
cp .env.example .env

# Edit .env with your API keys
```

## Configuration

Edit `config/jobs.yaml` to set up your job search:

```yaml
# Path to your resume
resume_path: "./resume.pdf"

# Where to save results
output_path: "./output/job-matches.txt"

# Maximum jobs per board (0 = unlimited)
max_jobs_per_board: 50

# LLM Configuration
llm:
  provider: "groq"  # groq, gemini, openrouter, or ollama
  api_key: "${GROQ_API_KEY}"  # From .env file
  model: "llama-3.1-8b-instant"

# Job boards to search
job_boards:
  - name: "Example Company"
    type: "greenhouse"
    url: "https://boards.greenhouse.io/company/jobs?query=software+engineer"
    selectors:
      job_list_container: ".main"
      job_card: ".opening"
      title: "a"
      location: ".location"
      description: ".description"
      next_button: ".next"
      job_url_attribute: "href"
```

## Usage

```bash
# Run the scraper
npm start

# Or directly
node src/index.js
```

## Output

The application generates two files:

1. **Text Report** (`job-matches.txt`): Human-readable ranked list with:
   - ATS scores (0-100)
   - Match analysis and reasoning
   - Job details and URLs
   - Visual score indicators

2. **JSON Data** (`job-matches.json`): Machine-readable data for further processing

## Finding Job Board URLs

### Greenhouse
Format: `https://boards.greenhouse.io/{company}/jobs?query={search}`

Examples:
- `https://boards.greenhouse.io/stripe/jobs?query=software+engineer`
- `https://boards.greenhouse.io/airbnb/jobs?query=product+manager`

### Workday
Format: `https://{company}.wd101.myworkdayjobs.com/en-US/{site}?q={search}`

Examples:
- `https://amazon.wd1.myworkdayjobs.com/en-US/amazon_external?q=software+engineer`
- `https://salesforce.wd1.myworkdayjobs.com/en-US/External_Career_Site?q=data+scientist`

### Lever
Format: `https://jobs.lever.co/{company}?search={search}`

Examples:
- `https://jobs.lever.co/figma?search=software%20engineer`
- `https://jobs.lever.co/notion?search=designer`

## Custom Selectors Guide

When adding custom job boards, you need to identify CSS selectors:

1. Open the job board in Chrome/Firefox
2. Right-click on a job listing and select "Inspect"
3. Look for:
   - Container that holds the job list
   - Individual job cards/items
   - Job title element
   - Location element
   - Description element
   - Next page button

Example for a hypothetical custom site:
```yaml
- name: "Custom Company"
  type: "custom"
  url: "https://company.com/careers"
  selectors:
    job_list_container: ".jobs-container"
    job_card: ".job-item"
    title: ".job-title h3"
    location: ".job-location"
    description: ".job-details"
    next_button: ".pagination .next"
    job_url_attribute: "href"
```

## Troubleshooting

### Puppeteer Issues
```bash
# If Puppeteer fails to launch, install Chrome dependencies:
npx puppeteer browsers install chrome
```

### Rate Limiting
If you hit rate limits:
- Increase `request_delay_ms` in config (default: 2000ms)
- Reduce `max_jobs_per_board`
- Use multiple API keys and rotate them

### Selector Issues
If jobs aren't being found:
1. Open the job board in a browser
2. Check if the site uses JavaScript frameworks (React, Vue, etc.)
3. Try increasing wait times in the scraper
4. Verify selectors match the current site structure

## Tips for Best Results

1. **Resume Optimization**: Ensure your PDF resume is text-based (not scanned images)
2. **Specific Searches**: Use specific job titles in URLs for better matches
3. **Rate Limits**: Be respectful - don't scrape too aggressively
4. **Multiple Boards**: Configure several job boards to cast a wider net
5. **Review Results**: Always review job descriptions personally before applying

## Environment Variables

Create a `.env` file:

```bash
GROQ_API_KEY=your_groq_key_here
GEMINI_API_KEY=your_gemini_key_here
OPENROUTER_API_KEY=your_openrouter_key_here
```

## License

MIT