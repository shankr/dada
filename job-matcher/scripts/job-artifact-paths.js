#!/usr/bin/env node

require('dotenv').config();

const path = require('path');
const ConfigLoader = require('../src/config/config-loader');

const config = ConfigLoader.load();
const outputTxt = config.output_path;
const outputJson = outputTxt.replace(/\.txt$/i, '.json');

function emit(name, value) {
  process.stdout.write(`${name}=${value}\n`);
}

emit('JOB_MATCHER_RESUME_PATH', path.resolve(config.resume_path));
emit('JOB_MATCHER_OUTPUT_TXT', path.resolve(outputTxt));
emit('JOB_MATCHER_OUTPUT_JSON', path.resolve(outputJson));
emit('JOB_MATCHER_CACHE_DB', path.resolve(config.ats_cache_db_path));
