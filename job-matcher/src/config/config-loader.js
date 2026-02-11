const fs = require('fs');
const path = require('path');
const yaml = require('js-yaml');

class ConfigLoader {
  static load(configPath = './config/jobs.yaml') {
    try {
      const fullPath = path.resolve(configPath);
      
      if (!fs.existsSync(fullPath)) {
        throw new Error(`Configuration file not found: ${fullPath}`);
      }
      
      const fileContent = fs.readFileSync(fullPath, 'utf8');
      let config = yaml.load(fileContent);
      
      // Process environment variables in config
      config = this.processEnvVariables(config);
      
      // Validate required fields
      this.validateConfig(config);
      
      // Resolve relative paths
      config.resume_path = path.resolve(config.resume_path);
      config.output_path = path.resolve(config.output_path);
      
      return config;
    } catch (error) {
      console.error('Error loading configuration:', error.message);
      process.exit(1);
    }
  }
  
  static processEnvVariables(obj) {
    if (typeof obj === 'string') {
      return obj.replace(/\$\{([^}]+)\}/g, (match, envVar) => {
        const value = process.env[envVar];
        if (value === undefined) {
          console.warn(`Warning: Environment variable ${envVar} is not set`);
          return match;
        }
        return value;
      });
    }
    
    if (Array.isArray(obj)) {
      return obj.map(item => this.processEnvVariables(item));
    }
    
    if (typeof obj === 'object' && obj !== null) {
      const result = {};
      for (const [key, value] of Object.entries(obj)) {
        result[key] = this.processEnvVariables(value);
      }
      return result;
    }
    
    return obj;
  }
  
  static validateConfig(config) {
    const required = ['resume_path', 'output_path', 'llm', 'job_boards'];
    
    for (const field of required) {
      if (!config[field]) {
        throw new Error(`Missing required configuration field: ${field}`);
      }
    }
    
    if (!Array.isArray(config.job_boards) || config.job_boards.length === 0) {
      throw new Error('Configuration must include at least one job_board');
    }
    
    if (!config.llm.provider) {
      throw new Error('LLM provider must be specified');
    }
    
    const validProviders = ['groq', 'ollama', 'openrouter', 'gemini'];
    if (!validProviders.includes(config.llm.provider)) {
      throw new Error(`Invalid LLM provider: ${config.llm.provider}`);
    }
    
    for (const board of config.job_boards) {
      if (!board.name || !board.type || !board.url) {
        throw new Error('Each job board must have name, type, and url');
      }
    }
  }
}

module.exports = ConfigLoader;