const axios = require('axios');

class ATSScorer {
  constructor(config) {
    this.config = config.llm;
    this.provider = config.llm.provider;
  }

  async scoreJob(resumeText, job) {
    const prompt = this.buildPrompt(resumeText, job);
    
    try {
      let score, reasoning;
      
      switch (this.provider) {
        case 'groq':
          ({ score, reasoning } = await this.callGroq(prompt));
          break;
        case 'gemini':
          ({ score, reasoning } = await this.callGemini(prompt));
          break;
        case 'openrouter':
          ({ score, reasoning } = await this.callOpenRouter(prompt));
          break;
        case 'ollama':
          ({ score, reasoning } = await this.callOllama(prompt));
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
      console.error(`Error scoring job "${job.title}": ${error.message}`);
      return {
        score: 0,
        reasoning: `Error: ${error.message}`,
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

  async callGroq(prompt) {
    const response = await axios.post(
      'https://api.groq.com/openai/v1/chat/completions',
      {
        model: this.config.model || 'llama-3.1-8b-instant',
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
          'Content-Type': 'application/json'
        }
      }
    );

    return this.parseResponse(response.data.choices[0].message.content);
  }

  async callGemini(prompt) {
    const response = await axios.post(
      `https://generativelanguage.googleapis.com/v1beta/models/${this.config.model || 'gemini-pro'}:generateContent?key=${this.config.api_key}`,
      {
        contents: [{
          parts: [{ text: prompt }]
        }],
        generationConfig: {
          temperature: 0.3,
          maxOutputTokens: 500
        }
      },
      {
        headers: { 'Content-Type': 'application/json' }
      }
    );

    return this.parseResponse(response.data.candidates[0].content.parts[0].text);
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

  async callOllama(prompt) {
    const baseUrl = this.config.ollama_base_url || 'http://localhost:11434';
    const response = await axios.post(
      `${baseUrl}/api/generate`,
      {
        model: this.config.model || 'llama2',
        prompt: prompt,
        stream: false,
        options: {
          temperature: 0.3
        }
      },
      {
        headers: { 'Content-Type': 'application/json' }
      }
    );

    return this.parseResponse(response.data.response);
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
    const results = [];
    const total = jobs.length;

    console.log(`\nScoring ${total} jobs with ${this.provider}...`);

    for (let i = 0; i < jobs.length; i++) {
      const job = jobs[i];
      
      if (onProgress) {
        onProgress(i + 1, total, job.title);
      } else {
        process.stdout.write(`\r  Progress: ${i + 1}/${total} - ${job.title.substring(0, 50)}...`);
      }

      try {
        const atsResult = await this.scoreJob(resumeText, job);
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
    return results.sort((a, b) => b.atsScore - a.atsScore);
  }
}

module.exports = ATSScorer;