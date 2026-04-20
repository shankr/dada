#!/usr/bin/env node

const fs = require('fs');

const reportPath = process.argv[2];
const outputPath = process.argv[3];

if (!reportPath || !outputPath) {
  console.error('Usage: node scripts/build-report-email.js <reportPath> <outputPath>');
  process.exit(1);
}

const to = process.env.JOB_MATCHER_EMAIL_TO;
const from = process.env.JOB_MATCHER_EMAIL_FROM;
const subject = process.env.JOB_MATCHER_EMAIL_SUBJECT || 'Job Matcher Report';

if (!to || !from) {
  console.error('Missing JOB_MATCHER_EMAIL_TO or JOB_MATCHER_EMAIL_FROM');
  process.exit(1);
}

const reportText = fs.readFileSync(reportPath, 'utf8');

function wrapLongLines(text, width = 900) {
  return text
    .split(/\r?\n/)
    .flatMap(line => {
      if (line.length <= width) return [line];
      const chunks = [];
      for (let i = 0; i < line.length; i += width) {
        chunks.push(line.slice(i, i + width));
      }
      return chunks;
    })
    .join('\n');
}

const payload = {
  FromEmailAddress: from,
  Destination: {
    ToAddresses: [to]
  },
  Content: {
    Simple: {
      Subject: {
        Data: subject,
        Charset: 'UTF-8'
      },
      Body: {
        Text: {
          Data: wrapLongLines(reportText),
          Charset: 'UTF-8'
        }
      }
    }
  }
};

fs.writeFileSync(outputPath, JSON.stringify(payload), 'utf8');
