#!/usr/bin/env node

const fs = require('fs');
const path = require('path');

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

const attachmentName = path.basename(reportPath);
const attachmentContent = fs.readFileSync(reportPath);
const boundary = `job-matcher-${Date.now()}`;
const CRLF = '\r\n';

const lines = [
  `From: ${from}`,
  `To: ${to}`,
  `Subject: ${subject}`,
  `Date: ${new Date().toUTCString()}`,
  'MIME-Version: 1.0',
  `Content-Type: multipart/mixed; boundary="${boundary}"`,
  '',
  `--${boundary}`,
  'Content-Type: text/plain; charset="UTF-8"',
  'Content-Transfer-Encoding: 7bit',
  '',
  'Attached is the latest job matcher report.',
  '',
  `--${boundary}`,
  `Content-Type: text/plain; name="${attachmentName}"`,
  `Content-Disposition: attachment; filename="${attachmentName}"`,
  'Content-Transfer-Encoding: base64',
  '',
  attachmentContent.toString('base64').replace(/(.{76})/g, '$1\n'),
  '',
  `--${boundary}--`,
  ''
];

const message = lines.join('\n').replace(/\n/g, CRLF);
const payload = {
  Data: message
};
fs.writeFileSync(outputPath, JSON.stringify(payload), 'utf8');
