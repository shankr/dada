const axios = require('axios');
const ATSCacheDB = require('../storage/ats-cache-db');

// Ensure ReadableStream exists early for transformers in Node.
if (typeof globalThis.ReadableStream !== 'function') {
  try {
    // eslint-disable-next-line global-require
    const { ReadableStream } = require('web-streams-polyfill/ponyfill');
    if (ReadableStream) {
      globalThis.ReadableStream = ReadableStream;
    }
  } catch (_) {
    // Best effort; ensureFetchGlobals will try again.
  }
}

class ATSScorer {
  constructor(config) {
    this.globalConfig = config;
    this.config = config.llm;
    this.provider = config.llm.provider;
    this.cacheDb = new ATSCacheDB(
      config.ats_cache_db_path || './output/ats-cache.sqlite'
    );
    this.embeddingCache = new Map();
  }

  async scoreJob(resumeText, job) {
    const prompt = this.buildPrompt(resumeText, job);
    
    try {
      let score, reasoning;
      
      switch (this.provider) {
        case 'local-hybrid':
          ({ score, reasoning } = await this.scoreJobLocal(resumeText, job));
          break;
        case 'openrouter':
          ({ score, reasoning } = await this.callOpenRouter(prompt));
          break;
        default:
          throw new Error(`Unsupported provider: ${this.provider}`);
      }
      
      return {
        score: Math.min(100, Math.max(0, score)),
        reasoning: reasoning,
        timestamp: new Date().toISOString()
      };
    } catch (error) {
      const formattedError = this.formatProviderError(error);
      console.error(`Error scoring job "${job.title}": ${formattedError}`);
      return {
        score: 0,
        reasoning: `Error: ${formattedError}`,
        timestamp: new Date().toISOString()
      };
    }
  }

  buildPrompt(resumeText, job) {
    return `You are an expert ATS (Applicant Tracking System) evaluator. Compare the following resume with the job description and provide a match score.

RESUME:
${resumeText.substring(0, 2000)}

JOB TITLE: ${job.title}
JOB LOCATION: ${job.location}
COMPANY: ${job.company}
JOB DESCRIPTION:
${job.description ? job.description.substring(0, 2000) : 'Not available'}

Analyze the match based on:
1. Skills alignment (technical skills, soft skills, tools)
2. Experience level match
3. Education requirements
4. Industry/domain knowledge
5. Keyword relevance

Respond in this exact format:
SCORE: [number between 0-100]
REASONING: [brief explanation of 2-3 sentences explaining the key matches and gaps]`;
  }

  async callOpenRouter(prompt) {
    const response = await axios.post(
      'https://openrouter.ai/api/v1/chat/completions',
      {
        model: this.config.model || 'mistralai/mistral-7b-instruct:free',
        messages: [
          { role: 'system', content: 'You are an ATS evaluation system. Be concise and accurate.' },
          { role: 'user', content: prompt }
        ],
        temperature: 0.3,
        max_tokens: 500
      },
      {
        headers: {
          'Authorization': `Bearer ${this.config.api_key}`,
          'Content-Type': 'application/json',
          'HTTP-Referer': 'https://job-scraper.local',
          'X-Title': 'Job Scraper ATS'
        }
      }
    );

    return this.parseResponse(response.data.choices[0].message.content);
  }

  parseResponse(text) {
    // Extract score
    const scoreMatch = text.match(/SCORE:\s*(\d+)/i);
    const score = scoreMatch ? parseInt(scoreMatch[1], 10) : 50;

    // Extract reasoning
    const reasoningMatch = text.match(/REASONING:\s*([\s\S]+)/i);
    let reasoning = reasoningMatch ? reasoningMatch[1].trim() : text;
    
    // Clean up reasoning
    reasoning = reasoning.replace(/SCORE:\s*\d+/i, '').trim();
    
    return { score, reasoning };
  }

  async scoreJobsBatch(resumeText, jobs, onProgress = null) {
    this.validateProviderConfig();
    this.cacheDb.initialize();
    const scoringCfg = this.getScoringConfig();

    const results = [];
    const total = jobs.length;
    let cacheHits = 0;
    let llmCalls = 0;

    console.log(`\nScoring ${total} jobs with ${this.provider}...`);

    for (let i = 0; i < jobs.length; i++) {
      const job = jobs[i];
      
      if (onProgress) {
        onProgress(i + 1, total, job.title);
      } else {
        process.stdout.write(`\r  Progress: ${i + 1}/${total} - ${job.title.substring(0, 50)}...`);
      }

      try {
        if (job.url && !scoringCfg.forceRecompute) {
          const cached = this.cacheDb.getByUrl(job.url);
          if (cached) {
            this.cacheDb.upsert(
              job,
              { score: cached.score, reasoning: cached.reasoning, timestamp: cached.scoredAt },
              this.provider,
              this.config.model
            );
            cacheHits++;
            results.push({
              ...job,
              atsScore: cached.score,
              atsReasoning: cached.reasoning,
              scoredAt: cached.scoredAt
            });
            continue;
          }
        }

        if (this.provider !== 'local-hybrid') {
          llmCalls++;
        }
        const atsResult = await this.scoreJob(resumeText, job);

        const isErrorResult =
          typeof atsResult.reasoning === 'string' &&
          atsResult.reasoning.startsWith('Error:');
        if (job.url && !isErrorResult) {
          this.cacheDb.upsert(job, atsResult, this.provider, this.config.model);
        }

        results.push({
          ...job,
          atsScore: atsResult.score,
          atsReasoning: atsResult.reasoning,
          scoredAt: atsResult.timestamp
        });
      } catch (e) {
        console.error(`\nError scoring job ${job.title}: ${e.message}`);
        results.push({
          ...job,
          atsScore: 0,
          atsReasoning: 'Error during scoring',
          scoredAt: new Date().toISOString()
        });
      }

      // Add small delay to respect rate limits
      await new Promise(resolve => setTimeout(resolve, 500));
    }

    console.log('\n');
    console.log(`Cache hits: ${cacheHits}, LLM calls: ${llmCalls}`);
    return results.sort((a, b) => b.atsScore - a.atsScore);
  }

  validateProviderConfig() {
    if (this.provider === 'local-hybrid') return;

    const apiKey = (this.config.api_key || '').trim();
    if (!apiKey) {
      throw new Error(`Missing API key for provider "${this.provider}". Set it in .env and reference it from config/jobs.yaml.`);
    }

    if (apiKey.includes('${') || apiKey.includes('your_') || apiKey.includes('_here')) {
      throw new Error(
        `Invalid API key value for provider "${this.provider}". The current value looks like a placeholder; update your .env with a real key.`
      );
    }
  }

  formatProviderError(error) {
    if (!error) return 'Unknown scoring error';

    const status = error.response?.status;
    if (status === 401) {
      const providerName = this.provider.toUpperCase();
      return `${providerName} authentication failed (401 Unauthorized). Check your API key in .env and config/jobs.yaml.`;
    }

    const providerMessage =
      error.response?.data?.error?.message ||
      error.response?.data?.message ||
      error.message;

    if (this.provider === 'openrouter' && /No endpoints found/i.test(providerMessage || '')) {
      return 'OpenRouter has no active endpoints for the configured model. Use "openrouter/auto" or switch to another currently available model.';
    }

    return providerMessage || 'Unknown scoring error';
  }

  getScoringConfig() {
    const defaults = {
      mode: 'hybrid_local',
      weights: {
        lexical: 0.40,
        embedding: 0.30,
        rules: 0.20,
        recency: 0.10
      },
      min_skill_overlap: 2,
      recency_half_life_days: 30,
      force_recompute: false,
      max_resume_chars: 4000,
      max_job_chars: 4000
    };

    const cfg = this.globalConfig.scoring || {};
    const weights = { ...defaults.weights, ...(cfg.weights || {}) };

    return {
      mode: cfg.mode || defaults.mode,
      weights,
      minSkillOverlap: Number.isFinite(cfg.min_skill_overlap) ? cfg.min_skill_overlap : defaults.min_skill_overlap,
      recencyHalfLifeDays: Number.isFinite(cfg.recency_half_life_days) ? cfg.recency_half_life_days : defaults.recency_half_life_days,
      forceRecompute: typeof cfg.force_recompute === 'boolean' ? cfg.force_recompute : defaults.force_recompute,
      maxResumeChars: Number.isFinite(cfg.max_resume_chars) ? cfg.max_resume_chars : defaults.max_resume_chars,
      maxJobChars: Number.isFinite(cfg.max_job_chars) ? cfg.max_job_chars : defaults.max_job_chars
    };
  }

  async scoreJobLocal(resumeText, job) {
    const cfg = this.getScoringConfig();
    const resume = (resumeText || '').slice(0, cfg.maxResumeChars);
    const jobText = `${job.title || ''}\n${job.description || ''}`.slice(0, cfg.maxJobChars);

    const resumeTokens = this.tokenize(resume);
    const jobTokens = this.tokenize(jobText);

    const lexical = this.lexicalScore(resumeTokens, jobTokens);
    const embedding = await this.embeddingScore(resume, jobText, job.url || job.title || '');
    const rules = this.rulesScore(resume, job.title || '', resumeTokens, jobTokens, cfg.minSkillOverlap);
    const extractedDate = this.extractPostedDateFromText(job.description || '');
    if (extractedDate && job.postedDate !== extractedDate) {
      job.postedDate = extractedDate;
    }
    const recency = this.recencyScore(
      extractedDate || job.postedDate || '',
      cfg.recencyHalfLifeDays
    );

    const weighted =
      cfg.weights.lexical * lexical +
      cfg.weights.embedding * embedding +
      cfg.weights.rules * rules +
      cfg.weights.recency * recency;

    const score = Math.round(weighted * 100);
    const reasoning = this.buildLocalReasoning({
      lexical,
      embedding,
      rules,
      recency,
      skillOverlap: this.skillOverlapCount(resumeTokens, jobTokens)
    });

    return { score, reasoning };
  }

  buildLocalReasoning({ lexical, embedding, rules, recency, skillOverlap }) {
    return `Lexical overlap: ${(lexical * 100).toFixed(0)}%. ` +
      `Embedding similarity: ${(embedding * 100).toFixed(0)}%. ` +
      `Rule score: ${(rules * 100).toFixed(0)}%. ` +
      `Recency score: ${(recency * 100).toFixed(0)}%. ` +
      `Skill overlap count: ${skillOverlap}.`;
  }

  tokenize(text) {
    const stopwords = this.getStopwords();
    return (text || '')
      .toLowerCase()
      .replace(/[^a-z0-9+.#-]+/g, ' ')
      .split(/\s+/)
      .filter(t => t.length >= 2 && !stopwords.has(t));
  }

  lexicalScore(resumeTokens, jobTokens) {
    if (resumeTokens.length === 0 || jobTokens.length === 0) return 0;
    const resumeSet = new Set(resumeTokens);
    const jobUnique = new Set(jobTokens);
    let overlap = 0;
    for (const token of jobUnique) {
      if (resumeSet.has(token)) overlap++;
    }
    return overlap / jobUnique.size;
  }

  skillOverlapCount(resumeTokens, jobTokens) {
    const resumeSet = new Set(resumeTokens);
    const jobSet = new Set(jobTokens);
    let overlap = 0;
    for (const skill of this.getTechKeywords()) {
      if (resumeSet.has(skill) && jobSet.has(skill)) overlap++;
    }
    return overlap;
  }

  rulesScore(resumeText, jobTitle, resumeTokens, jobTokens, minSkillOverlap) {
    let score = 1.0;

    const overlap = this.skillOverlapCount(resumeTokens, jobTokens);
    if (overlap < minSkillOverlap) {
      score -= 0.4;
    }

    const jobSeniority = this.detectSeniority(jobTitle);
    const resumeSeniority = this.detectSeniority(resumeText);
    if (jobSeniority && !resumeSeniority) {
      score -= 0.2;
    }

    if (!jobSeniority && resumeSeniority) {
      score -= 0.1;
    }

    return Math.max(0, Math.min(1, score));
  }

  detectSeniority(text) {
    const t = (text || '').toLowerCase();
    return /(principal|staff|lead|senior|sr\\b|manager|director|intern|entry)/.test(t);
  }

  recencyScore(postedDate, halfLifeDays) {
    if (!postedDate) return 0.5;
    const date = this.parsePostedDate(postedDate);
    if (!date) return 0.5;

    const now = Date.now();
    const ageDays = Math.max(0, (now - date.getTime()) / (1000 * 60 * 60 * 24));
    const halfLife = Math.max(1, halfLifeDays || 30);
    const decay = Math.exp(-Math.log(2) * (ageDays / halfLife));
    return Math.max(0, Math.min(1, decay));
  }

  parsePostedDate(value) {
    if (!value) return null;
    const cleaned = value
      .replace(/\./g, '')
      .replace(/\s+/g, ' ')
      .trim();

    const parsed = Date.parse(cleaned);
    if (!Number.isNaN(parsed)) {
      return new Date(parsed);
    }
    return null;
  }

  extractPostedDateFromText(text) {
    if (!text) return '';
    const match = text.match(
      /\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\s+\d{1,2},\s+\d{4}\b/i
    );
    return match ? match[0] : '';
  }

  async embeddingScore(resumeText, jobText, cacheKey) {
    if (!resumeText || !jobText) return 0;

    const resumeKey = 'resume:global';
    const jobKey = `job:${cacheKey}`;

    const resumeEmbedding = await this.getEmbedding(resumeText, resumeKey);
    const jobEmbedding = await this.getEmbedding(jobText, jobKey);

    if (!resumeEmbedding || !jobEmbedding) return 0;
    return this.cosineSimilarity(resumeEmbedding, jobEmbedding);
  }


  async getEmbedding(text, cacheKey) {
    if (this.embeddingCache.has(cacheKey)) {
      return this.embeddingCache.get(cacheKey);
    }

    const model = await this.getEmbeddingModel();
    const output = await model(text, { pooling: 'mean', normalize: true });

    const vector = Array.from(output.data || output);
    this.embeddingCache.set(cacheKey, vector);
    return vector;
  }

  async getEmbeddingModel() {
    if (ATSScorer.embeddingModel) return ATSScorer.embeddingModel;
    if (!ATSScorer.embeddingModelPromise) {
      ATSScorer.embeddingModelPromise = (async () => {
        await this.ensureFetchGlobals();
        const { pipeline } = await import('@xenova/transformers');
        return pipeline('feature-extraction', 'Xenova/all-MiniLM-L6-v2', { quantized: true });
      })();
    }
    ATSScorer.embeddingModel = await ATSScorer.embeddingModelPromise;
    return ATSScorer.embeddingModel;
  }

  async ensureFetchGlobals() {
    if (typeof globalThis.fetch === 'function' && typeof globalThis.Headers === 'function') {
      return;
    }

    // Use node-fetch v2 for Node 17 compatibility.
    // eslint-disable-next-line global-require
    const fetch = require('node-fetch');
    globalThis.fetch = fetch;
    globalThis.Headers = fetch.Headers;
    globalThis.Request = fetch.Request;
    globalThis.Response = fetch.Response;

    if (!globalThis.ReadableStream) {
      // eslint-disable-next-line global-require
      const { ReadableStream: PolyfillReadableStream } = require('web-streams-polyfill/ponyfill');
      globalThis.ReadableStream = PolyfillReadableStream;
    }
  }

  cosineSimilarity(a, b) {
    if (!a || !b || a.length !== b.length) return 0;
    let dot = 0;
    let normA = 0;
    let normB = 0;
    for (let i = 0; i < a.length; i++) {
      dot += a[i] * b[i];
      normA += a[i] * a[i];
      normB += b[i] * b[i];
    }
    if (normA === 0 || normB === 0) return 0;
    return Math.max(0, Math.min(1, dot / (Math.sqrt(normA) * Math.sqrt(normB))));
  }

  getStopwords() {
    if (ATSScorer.stopwords) return ATSScorer.stopwords;
    ATSScorer.stopwords = new Set([
      'a','an','and','are','as','at','be','by','for','from','has','he','in','is','it','its','of','on','that','the','to','was','were','will','with',
      'you','your','we','our','they','their','i','me','my','this','these','those','or','but','if','then','than','also','not','no','yes','so','such',
      'about','across','after','before','between','both','during','each','few','more','most','other','over','under','up','down','out','into','through',
      'using','use','used','uses','based','within','per','etc','etc.'
    ]);
    return ATSScorer.stopwords;
  }

  getTechKeywords() {
    if (ATSScorer.techKeywords) return ATSScorer.techKeywords;
    ATSScorer.techKeywords = new Set([
      'java','python','javascript','typescript','golang','go','rust','c','c++','c#','kotlin','swift','scala','ruby','php',
      'react','angular','vue','node','nodejs','express','spring','django','flask','rails','laravel','.net','dotnet',
      'aws','gcp','azure','kubernetes','docker','terraform','ansible','linux','sql','postgres','mysql','mongodb','redis',
      'spark','hadoop','kafka','grpc','rest','graphql','api','microservices','ml','ai','nlp','cv','llm','pytorch','tensorflow',
      'ci','cd','git','github','gitlab','bitbucket','jenkins','circleci','datadog','prometheus','grafana','elasticsearch'
    ]);
    return ATSScorer.techKeywords;
  }
}

module.exports = ATSScorer;
