#!/usr/bin/env node

require('dotenv').config();

const path = require('path');
const ConfigLoader = require('../src/config/config-loader');

const config = ConfigLoader.load();
const runLabel = buildRunLabel(process.env.JOB_MATCHER_TIMEZONE || 'America/Los_Angeles');
const baseOutputDir = path.dirname(config.output_path);
const baseOutputName = path.basename(config.output_path);
const outputDir = path.join(baseOutputDir, runLabel);
const outputTxt = path.join(outputDir, baseOutputName);
const outputJson = outputTxt.replace(/\.txt$/i, '.json');

function buildRunLabel(timeZone) {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false
  }).formatToParts(new Date());

  const map = Object.fromEntries(parts.map(part => [part.type, part.value]));
  return `${map.year}-${map.month}-${map.day}-${map.hour}${map.minute}`;
}

function emit(name, value) {
  process.stdout.write(`${name}=${value}\n`);
}

emit('JOB_MATCHER_RUN_LABEL', runLabel);
emit('JOB_MATCHER_RESUME_PATH', path.resolve(config.resume_path));
emit('JOB_MATCHER_OUTPUT_TXT', path.resolve(outputTxt));
emit('JOB_MATCHER_OUTPUT_JSON', path.resolve(outputJson));
emit('JOB_MATCHER_CACHE_DB', path.resolve(config.ats_cache_db_path));
