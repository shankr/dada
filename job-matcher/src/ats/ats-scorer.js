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
    await this.cacheDb.initialize();
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
            const storedJob = this.cacheDb.getJobByUrl(job.url);
            cacheHits++;
            results.push({
              ...job,
              firstSeenAt: storedJob?.firstSeenAt || '',
              lastSeenAt: storedJob?.lastSeenAt || '',
              isNewThisRun: job.isNewThisRun === true,
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

        const storedJob = job.url ? this.cacheDb.getJobByUrl(job.url) : null;

        results.push({
          ...job,
          firstSeenAt: storedJob?.firstSeenAt || '',
          lastSeenAt: storedJob?.lastSeenAt || '',
          isNewThisRun: job.isNewThisRun === true,
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
      embedding_model: 'BAAI/bge-small-en-v1.5',
      weights: {
        lexical: 0.20,
        embedding: 0.45,
        rules: 0.20,
        recency: 0.15
      },
      min_skill_overlap: 2,
      required_qualifications_threshold: 0.45,
      required_qualifications_penalty_max: 0.30,
      required_qualifications_bullet_penalty_threshold: 0.35,
      required_qualifications_penalty_per_bullet: 0.06,
      named_required_tech_match_threshold: 0.58,
      named_required_tech_penalty_per_term: 0.08,
      named_required_tech_penalty_max: 0.24,
      recency_half_life_days: 30,
      force_recompute: false,
      max_resume_chars: 4000,
      max_job_chars: 4000
    };

    const cfg = this.globalConfig.scoring || {};
    const weights = { ...defaults.weights, ...(cfg.weights || {}) };

    return {
      mode: cfg.mode || defaults.mode,
      embeddingModel: cfg.embedding_model || defaults.embedding_model,
      weights,
      minSkillOverlap: Number.isFinite(cfg.min_skill_overlap) ? cfg.min_skill_overlap : defaults.min_skill_overlap,
      requiredQualificationsThreshold: Number.isFinite(cfg.required_qualifications_threshold)
        ? cfg.required_qualifications_threshold
        : defaults.required_qualifications_threshold,
      requiredQualificationsPenaltyMax: Number.isFinite(cfg.required_qualifications_penalty_max)
        ? cfg.required_qualifications_penalty_max
        : defaults.required_qualifications_penalty_max,
      requiredQualificationsBulletPenaltyThreshold: Number.isFinite(cfg.required_qualifications_bullet_penalty_threshold)
        ? cfg.required_qualifications_bullet_penalty_threshold
        : defaults.required_qualifications_bullet_penalty_threshold,
      requiredQualificationsPenaltyPerBullet: Number.isFinite(cfg.required_qualifications_penalty_per_bullet)
        ? cfg.required_qualifications_penalty_per_bullet
        : defaults.required_qualifications_penalty_per_bullet,
      namedRequiredTechMatchThreshold: Number.isFinite(cfg.named_required_tech_match_threshold)
        ? cfg.named_required_tech_match_threshold
        : defaults.named_required_tech_match_threshold,
      namedRequiredTechPenaltyPerTerm: Number.isFinite(cfg.named_required_tech_penalty_per_term)
        ? cfg.named_required_tech_penalty_per_term
        : defaults.named_required_tech_penalty_per_term,
      namedRequiredTechPenaltyMax: Number.isFinite(cfg.named_required_tech_penalty_max)
        ? cfg.named_required_tech_penalty_max
        : defaults.named_required_tech_penalty_max,
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
    const baseEmbedding = await this.embeddingScore(resume, jobText, job.url || job.title || '');
    const requiredMatch = await this.requiredQualificationsSemanticMatch(
      resume,
      job.description || '',
      job.url || job.title || '',
      cfg
    );
    const embedding = Math.max(0, baseEmbedding - requiredMatch.penalty);
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
      baseEmbedding,
      embedding,
      rules,
      recency,
      skillOverlap: this.skillOverlapCount(resumeTokens, jobTokens),
      requiredMatch
    });

    return { score, reasoning };
  }

  buildLocalReasoning({ lexical, baseEmbedding, embedding, rules, recency, skillOverlap, requiredMatch }) {
    const lines = [
      `Lexical overlap: ${(lexical * 100).toFixed(0)}%.`,
      `Embedding similarity: ${(embedding * 100).toFixed(0)}% (base ${(baseEmbedding * 100).toFixed(0)}%, total penalty ${((requiredMatch?.penalty || 0) * 100).toFixed(0)}%).`,
      `Rule score: ${(rules * 100).toFixed(0)}%.`,
      `Recency score: ${(recency * 100).toFixed(0)}%.`,
      `Skill overlap count: ${skillOverlap}.`
    ];

    if (!requiredMatch?.sectionFound) {
      lines.push('Required qualifications match: n/a.');
      return lines.join('\n');
    }

    lines.push(
      `Required qualifications match: ${(requiredMatch.score * 100).toFixed(0)}% across ${requiredMatch.bulletCount} bullets.`,
      `Penalty breakdown: total ${(requiredMatch.penalty * 100).toFixed(0)}% = threshold ${(requiredMatch.thresholdPenalty * 100).toFixed(0)}% + weak bullets ${(requiredMatch.weakBulletPenalty * 100).toFixed(0)}% + named required tech ${(requiredMatch.namedTechPenalty * 100).toFixed(0)}%.`
    );

    if (requiredMatch.topMatches?.length) {
      lines.push(`Best semantic matches: ${requiredMatch.topMatches.map(match => `${(match.score * 100).toFixed(0)}%: ${match.bullet}`).join(' | ')}`);
    }

    if (requiredMatch.weakMatches?.length) {
      lines.push(`Weak required matches: ${requiredMatch.weakMatches.map(match => `${(match.score * 100).toFixed(0)}%: ${match.bullet}`).join(' | ')}`);
    }

    if (requiredMatch.namedTechMissingTerms?.length) {
      lines.push(`Unsupported named required tech: ${requiredMatch.namedTechMissingTerms.join(', ')}.`);
    } else if (requiredMatch.namedTechCount > 0) {
      lines.push(`Unsupported named required tech: none (${requiredMatch.namedTechCount} checked).`);
    }

    return lines.join('\n');
  }

  tokenize(text) {
    const stopwords = this.getStopwords();
    return this.normalizeTechPhrases(text || '')
      .toLowerCase()
      .replace(/[^a-z0-9+.#-]+/g, ' ')
      .split(/\s+/)
      .map(t => this.normalizeTechAlias(t))
      .filter(t => t.length >= 2 && !stopwords.has(t));
  }

  normalizeTechPhrases(text) {
    return String(text || '')
      .replace(/\bhugging\s+face\b/gi, 'huggingface')
      .replace(/\bsentence\s+transformers\b/gi, 'sentencetransformers')
      .replace(/\bmodel\s+context\s+protocol\b/gi, 'modelcontextprotocol')
      .replace(/\bvector\s+database\b/gi, 'vectordb')
      .replace(/\bvector\s+db\b/gi, 'vectordb')
      .replace(/\bmachine\s+learning\b/gi, 'machinelearning');
  }

  normalizeTechAlias(token) {
    const aliases = this.getTechAliases();
    return aliases.get(token) || token;
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

  async requiredQualificationsSemanticMatch(resumeText, descriptionText, cacheKey, cfg) {
    const section = this.extractRequiredQualificationsSection(descriptionText);
    if (!section) {
      return {
        sectionFound: false,
        score: 0,
        penalty: 0,
        bulletCount: 0
      };
    }

    const bullets = this.extractSectionBullets(section).slice(0, 12);
    if (bullets.length === 0) {
      return {
        sectionFound: true,
        score: 0,
        penalty: 0,
        bulletCount: 0
      };
    }

    const bulletScores = [];
    for (let i = 0; i < bullets.length; i++) {
      const bullet = bullets[i];
      const score = await this.embeddingScore(
        resumeText,
        bullet,
        `${cacheKey}:required:${i}`
      );
      bulletScores.push({ bullet, score });
    }

    const similarities = bulletScores.map(item => item.score);
    const average = similarities.reduce((sum, value) => sum + value, 0) / similarities.length;
    const weakMatches = bulletScores.filter(
      item => item.score < cfg.requiredQualificationsBulletPenaltyThreshold
    );

    let penalty = 0;
    let thresholdPenalty = 0;
    let weakBulletPenalty = 0;
    if (average < cfg.requiredQualificationsThreshold) {
      const deficit = cfg.requiredQualificationsThreshold - average;
      const threshold = Math.max(0.01, cfg.requiredQualificationsThreshold);
      thresholdPenalty = (deficit / threshold) * cfg.requiredQualificationsPenaltyMax * 0.4;
      penalty += thresholdPenalty;
    }
    if (weakMatches.length > 0) {
      weakBulletPenalty = weakMatches.length * cfg.requiredQualificationsPenaltyPerBullet;
      penalty += weakBulletPenalty;
    }

    const namedTechPenaltyResult = await this.computeNamedRequiredTechPenalty(
      resumeText,
      bullets,
      `${cacheKey}:named-tech`,
      cfg
    );
    penalty += namedTechPenaltyResult.penalty;

    const totalPenalty = Math.max(0, Math.min(cfg.requiredQualificationsPenaltyMax, penalty));
    const appliedThresholdPenalty = Math.min(totalPenalty, thresholdPenalty);
    const remainingAfterThreshold = Math.max(0, totalPenalty - appliedThresholdPenalty);
    const appliedWeakBulletPenalty = Math.min(remainingAfterThreshold, weakBulletPenalty);
    const remainingAfterWeak = Math.max(0, remainingAfterThreshold - appliedWeakBulletPenalty);
    const appliedNamedTechPenalty = Math.min(remainingAfterWeak, namedTechPenaltyResult.penalty);
    return {
      sectionFound: true,
      score: Math.max(0, Math.min(1, average)),
      penalty: totalPenalty,
      thresholdPenalty: appliedThresholdPenalty,
      weakBulletPenalty: appliedWeakBulletPenalty,
      bulletCount: bullets.length,
      namedTechPenalty: appliedNamedTechPenalty,
      namedTechCount: namedTechPenaltyResult.techCount,
      namedTechMissingCount: namedTechPenaltyResult.missingCount,
      namedTechMissingTerms: namedTechPenaltyResult.missingTerms,
      namedTechSupportedTerms: namedTechPenaltyResult.supportedTerms,
      topMatches: bulletScores.slice().sort((a, b) => b.score - a.score).slice(0, 3),
      weakMatches: weakMatches.slice().sort((a, b) => a.score - b.score).slice(0, 3)
    };
  }

  async computeNamedRequiredTechPenalty(resumeText, bullets, cacheKey, cfg) {
    const requiredTerms = this.extractNamedRequiredTechTerms(bullets);
    if (requiredTerms.length === 0) {
      return {
        penalty: 0,
        techCount: 0,
        missingCount: 0,
        missingTerms: [],
        supportedTerms: []
      };
    }

    const resumeUnits = this.splitTextIntoSemanticUnits(resumeText).slice(0, 40);
    if (resumeUnits.length === 0) {
      return {
        penalty: Math.min(cfg.namedRequiredTechPenaltyMax, requiredTerms.length * cfg.namedRequiredTechPenaltyPerTerm),
        techCount: requiredTerms.length,
        missingCount: requiredTerms.length,
        missingTerms: requiredTerms.slice(),
        supportedTerms: []
      };
    }

    let missingCount = 0;
    const missingTerms = [];
    const supportedTerms = [];
    for (const term of requiredTerms) {
      const supported = await this.resumeSemanticallySupportsTerm(
        resumeUnits,
        term,
        `${cacheKey}:${term}`,
        cfg.namedRequiredTechMatchThreshold
      );
      if (!supported) {
        missingCount++;
        missingTerms.push(term);
      } else {
        supportedTerms.push(term);
      }
    }

    return {
      penalty: Math.min(
        cfg.namedRequiredTechPenaltyMax,
        missingCount * cfg.namedRequiredTechPenaltyPerTerm
      ),
      techCount: requiredTerms.length,
      missingCount,
      missingTerms,
      supportedTerms
    };
  }

  async resumeSemanticallySupportsTerm(resumeUnits, term, cacheKey, threshold) {
    const profile = this.getNamedTechSemanticProfile(term);
    const supportPhrases = profile.supportPhrases;
    const effectiveThreshold = Math.max(threshold, profile.threshold || 0);
    let maxSimilarity = 0;
    for (let i = 0; i < resumeUnits.length; i++) {
      const unit = resumeUnits[i];
      for (let j = 0; j < supportPhrases.length; j++) {
        const phrase = supportPhrases[j];
        const similarity = await this.embeddingScore(
          unit,
          phrase,
          `${cacheKey}:${j}:${i}`
        );
        if (similarity > maxSimilarity) {
          maxSimilarity = similarity;
        }
      }
      if (maxSimilarity >= effectiveThreshold) {
        return true;
      }
    }
    return false;
  }

  getNamedTechSemanticProfile(term) {
    const normalized = this.normalizeTechAlias(String(term || '').toLowerCase());
    const defaultProfile = {
      threshold: 0,
      supportPhrases: [
        `Hands-on production experience with ${normalized}`,
        `Deep practical experience with ${normalized}`
      ]
    };

    const profiles = {
      llm: {
        threshold: 0.7,
        supportPhrases: [
          'Hands-on production experience with large language models (LLMs)',
          'Designing and deploying LLM-powered systems in production',
          'Building applications with large language models (LLMs)'
        ]
      },
      rag: {
        threshold: 0.72,
        supportPhrases: [
          'Hands-on experience building retrieval augmented generation (RAG) systems',
          'Implementing retrieval augmented generation pipelines for production AI systems',
          'Designing document retrieval and generation workflows for LLM applications'
        ]
      },
      agentic: {
        threshold: 0.72,
        supportPhrases: [
          'Hands-on experience building agentic workflows and AI agents',
          'Designing autonomous or multi-step AI agent systems in production',
          'Building orchestration and decision flows for agentic AI systems'
        ]
      },
      agents: {
        threshold: 0.72,
        supportPhrases: [
          'Hands-on experience building AI agents and agent orchestration systems',
          'Designing autonomous AI agent workflows in production',
          'Building multi-agent systems for real-world applications'
        ]
      },
      transformers: {
        threshold: 0.68,
        supportPhrases: [
          'Hands-on experience with transformer models and transformer-based NLP systems',
          'Building applications using transformer architectures in production'
        ]
      },
      langchain: {
        threshold: 0.72,
        supportPhrases: [
          'Hands-on experience building LLM applications with LangChain',
          'Production use of LangChain for retrieval or agent workflows'
        ]
      },
      langgraph: {
        threshold: 0.72,
        supportPhrases: [
          'Hands-on experience building stateful agent workflows with LangGraph',
          'Production use of LangGraph for AI orchestration'
        ]
      },
      mcp: {
        threshold: 0.72,
        supportPhrases: [
          'Hands-on experience with Model Context Protocol (MCP)',
          'Building tools or agents that integrate using Model Context Protocol'
        ]
      },
      modelcontextprotocol: {
        threshold: 0.72,
        supportPhrases: [
          'Hands-on experience with Model Context Protocol (MCP)',
          'Building tools or agents that integrate using Model Context Protocol'
        ]
      }
    };

    return profiles[normalized] || defaultProfile;
  }

  splitTextIntoSemanticUnits(text) {
    if (!text) return [];
    return String(text)
      .replace(/\r/g, '\n')
      .split(/\n+/)
      .flatMap(line => line.split(/(?<=[.;])\s+/))
      .map(part => part.trim())
      .filter(part => part.length >= 20);
  }

  extractNamedRequiredTechTerms(bullets) {
    const techKeywords = this.getTechKeywords();
    const foundTerms = new Set();
    for (const bullet of bullets) {
      const tokens = this.tokenize(bullet);
      for (const token of tokens) {
        if (techKeywords.has(token)) {
          foundTerms.add(token);
        }
      }
    }
    return Array.from(foundTerms);
  }

  extractRequiredQualificationsSection(descriptionText) {
    const sections = this.extractTitledSections(descriptionText);
    const requiredSection = sections.find(section => this.isRequiredQualificationsHeading(section.heading));
    return requiredSection ? requiredSection.body : '';
  }

  extractTitledSections(text) {
    if (!text) return [];

    const normalized = String(text)
      .replace(/\r/g, '\n')
      .replace(/\u2022/g, '- ')
      .replace(/\t/g, ' ')
      .split('\n')
      .map(line => line.trim())
      .filter(Boolean);

    const sections = [];
    let currentHeading = '';
    let currentBody = [];

    for (const line of normalized) {
      if (this.looksLikeSectionHeading(line)) {
        if (currentHeading || currentBody.length > 0) {
          sections.push({ heading: currentHeading, body: currentBody.join('\n').trim() });
        }
        currentHeading = line;
        currentBody = [];
      } else {
        currentBody.push(line);
      }
    }

    if (currentHeading || currentBody.length > 0) {
      sections.push({ heading: currentHeading, body: currentBody.join('\n').trim() });
    }

    return sections;
  }

  looksLikeSectionHeading(line) {
    const trimmed = (line || '').trim();
    if (!trimmed) return false;
    if (trimmed.length > 80) return false;
    if (/[:\-]$/.test(trimmed)) return true;
    return this.isRequiredQualificationsHeading(trimmed) || this.isPreferredQualificationsHeading(trimmed);
  }

  isRequiredQualificationsHeading(line) {
    const normalized = this.normalizeHeading(line);
    return [
      'minimum qualifications',
      'minimum qualification',
      'basic qualifications',
      'basic qualification',
      'required qualifications',
      'required qualification',
      'requirements',
      'what youll need',
      'what you will need',
      'must have',
      'must haves',
      'qualification'
    ].some(pattern => normalized.includes(pattern)) && !this.isPreferredQualificationsHeading(normalized);
  }

  isPreferredQualificationsHeading(line) {
    const normalized = this.normalizeHeading(line);
    return [
      'preferred qualifications',
      'preferred qualification',
      'nice to have',
      'nice to haves',
      'desired qualifications',
      'desired qualification',
      'bonus points',
      'preferred skills',
      'pluses'
    ].some(pattern => normalized.includes(pattern));
  }

  normalizeHeading(line) {
    return String(line || '')
      .toLowerCase()
      .replace(/[^a-z0-9\s]/g, '')
      .replace(/\s+/g, ' ')
      .trim();
  }

  extractSectionBullets(sectionText) {
    if (!sectionText) return [];

    const lines = sectionText
      .split('\n')
      .map(line => line.trim())
      .filter(Boolean);

    const bullets = [];
    for (const line of lines) {
      if (this.looksLikeSectionHeading(line)) {
        break;
      }
      const cleaned = line.replace(/^[-*•]+\s*/, '').trim();
      if (cleaned.length < 8) {
        continue;
      }
      bullets.push(cleaned);
    }

    if (bullets.length > 0) {
      return bullets;
    }

    return sectionText
      .split(/(?<=[.;])\s+/)
      .map(part => part.trim())
      .filter(part => part.length >= 20)
      .slice(0, 8);
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
    const scoringCfg = this.getScoringConfig();
    const modelId = scoringCfg.embeddingModel;

    if (ATSScorer.embeddingModels?.has(modelId)) {
      return ATSScorer.embeddingModels.get(modelId);
    }

    if (!ATSScorer.embeddingModelPromises) {
      ATSScorer.embeddingModelPromises = new Map();
    }

    if (!ATSScorer.embeddingModelPromises.has(modelId)) {
      const embeddingModelPromise = (async () => {
        await this.ensureFetchGlobals();
        const { pipeline } = await import('@xenova/transformers');
        try {
          return await pipeline('feature-extraction', modelId, { quantized: true });
        } catch (error) {
          const message = error && error.message ? error.message : String(error);
          if (!message.includes('model_quantized.onnx')) {
            throw error;
          }
          return pipeline('feature-extraction', modelId, { quantized: false });
        }
      })();
      ATSScorer.embeddingModelPromises.set(modelId, embeddingModelPromise);
    }

    const model = await ATSScorer.embeddingModelPromises.get(modelId);
    if (!ATSScorer.embeddingModels) {
      ATSScorer.embeddingModels = new Map();
    }
    ATSScorer.embeddingModels.set(modelId, model);
    return model;
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
      'java','python','javascript','typescript','golang','go','rust','c','c++','c#','kotlin','swift','scala','ruby','php','bash',
      'react','reactjs','angular','vue','node','nodejs','express','spring','springboot','django','flask','rails','laravel','.net','dotnet',
      'html','css','sass','less','tailwind','bootstrap',
      'aws','gcp','azure','kubernetes','docker','terraform','ansible','linux','unix','helm','istio','argo','airflow',
      'sql','postgres','postgresql','mysql','mongodb','redis','cassandra','dynamodb','snowflake','bigquery','redshift','elasticsearch','opensearch',
      'spark','hadoop','kafka','flink','hive','presto','trino','databricks','dbt',
      'grpc','rest','graphql','api','microservices','eventdriven','soa',
      'ml','ai','nlp','cv','llm','rag','pytorch','tensorflow','keras','scikitlearn','xgboost',
      'transformers','huggingface','sentencetransformers','langchain','langgraph','llamaindex','autogen','crewai','mcp','modelcontextprotocol',
      'vectorsearch','vectordb','embedding','embeddings','finetuning','inference','promptengineering','agents','agentic',
      'ci','cd','git','github','gitlab','bitbucket','jenkins','circleci','githubactions','travisci',
      'datadog','prometheus','grafana','splunk','newrelic',
      'selenium','playwright','pytest','jest','cypress','junit',
      'rabbitmq','sqs','sns','pubsub',
      'openai','openrouter'
    ]);
    return ATSScorer.techKeywords;
  }

  getTechAliases() {
    if (ATSScorer.techAliases) return ATSScorer.techAliases;
    ATSScorer.techAliases = new Map([
      ['js', 'javascript'],
      ['ts', 'typescript'],
      ['py', 'python'],
      ['golang', 'go'],
      ['react.js', 'react'],
      ['reactjs', 'react'],
      ['node.js', 'node'],
      ['nodejs', 'node'],
      ['spring-boot', 'springboot'],
      ['k8s', 'kubernetes'],
      ['postgresql', 'postgres'],
      ['postgres', 'postgres'],
      ['mongo', 'mongodb'],
      ['mongodb', 'mongodb'],
      ['elastic', 'elasticsearch'],
      ['github-actions', 'githubactions'],
      ['githubactions', 'githubactions'],
      ['ci/cd', 'ci'],
      ['machinelearning', 'ml'],
      ['machine-learning', 'ml'],
      ['genai', 'ai'],
      ['llms', 'llm'],
      ['llmops', 'llm'],
      ['scikit-learn', 'scikitlearn'],
      ['sklearn', 'scikitlearn'],
      ['tf', 'tensorflow'],
      ['tensor-flow', 'tensorflow'],
      ['hugging-face', 'huggingface'],
      ['sentence-transformers', 'sentencetransformers'],
      ['lang-chain', 'langchain'],
      ['lang-graph', 'langgraph'],
      ['llama-index', 'llamaindex'],
      ['model-context-protocol', 'modelcontextprotocol'],
      ['mcp', 'mcp'],
      ['vector-db', 'vectordb'],
      ['vector-database', 'vectordb'],
      ['vectorstore', 'vectordb'],
      ['openaiapis', 'openai']
    ]);
    return ATSScorer.techAliases;
  }
}

module.exports = ATSScorer;
