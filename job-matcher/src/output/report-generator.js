const fs = require('fs');
const path = require('path');

class ReportGenerator {
  constructor(outputPath) {
    this.outputPath = outputPath;
  }

  generate(results, resumeInfo) {
    const timestamp = new Date().toLocaleString();
    const totalJobs = results.length;
    const highMatches = results.filter(r => r.atsScore >= 70).length;
    const mediumMatches = results.filter(r => r.atsScore >= 40 && r.atsScore < 70).length;
    const lowMatches = results.filter(r => r.atsScore < 40).length;

    let report = `
================================================================================
                    JOB MATCH REPORT - ATS SCORING RESULTS
================================================================================

Generated: ${timestamp}
Resume: ${resumeInfo.filePath}
Resume Pages: ${resumeInfo.numPages}

================================================================================
                              SUMMARY
================================================================================

Total Jobs Analyzed: ${totalJobs}
High Matches (70-100): ${highMatches}
Medium Matches (40-69): ${mediumMatches}
Low Matches (0-39): ${lowMatches}

================================================================================
                           RANKED JOB LISTINGS
================================================================================

`;

    // Group jobs by score ranges
    const highMatchJobs = results.filter(r => r.atsScore >= 70);
    const mediumMatchJobs = results.filter(r => r.atsScore >= 40 && r.atsScore < 70);
    const lowMatchJobs = results.filter(r => r.atsScore < 40);

    if (highMatchJobs.length > 0) {
      report += `\n${'='.repeat(80)}\n                     HIGH MATCH JOBS (Score: 70-100)\n${'='.repeat(80)}\n\n`;
      highMatchJobs.forEach((job, index) => {
        report += this.formatJobEntry(job, index + 1);
      });
    }

    if (mediumMatchJobs.length > 0) {
      report += `\n${'='.repeat(80)}\n                   MEDIUM MATCH JOBS (Score: 40-69)\n${'='.repeat(80)}\n\n`;
      mediumMatchJobs.forEach((job, index) => {
        report += this.formatJobEntry(job, highMatchJobs.length + index + 1);
      });
    }

    if (lowMatchJobs.length > 0) {
      report += `\n${'='.repeat(80)}\n                      LOW MATCH JOBS (Score: 0-39)\n${'='.repeat(80)}\n\n`;
      lowMatchJobs.forEach((job, index) => {
        report += this.formatJobEntry(job, highMatchJobs.length + mediumMatchJobs.length + index + 1);
      });
    }

    report += `
================================================================================
                               END OF REPORT
================================================================================

Notes:
- ATS scores are generated using AI and should be used as a guide, not definitive
- Always review job descriptions personally before applying
- Scores consider skills, experience, education, and keyword matching
- Job listings are sorted by match score (highest first)

`;

    // Ensure output directory exists
    const outputDir = path.dirname(this.outputPath);
    if (!fs.existsSync(outputDir)) {
      fs.mkdirSync(outputDir, { recursive: true });
    }

    // Write report
    fs.writeFileSync(this.outputPath, report);
    console.log(`\n✓ Report saved to: ${this.outputPath}`);
    
    return report;
  }

  formatJobEntry(job, rank) {
    const scoreBar = this.getScoreBar(job.atsScore);
    
    return `
--------------------------------------------------------------------------------
 Rank #${rank} | ATS Score: ${job.atsScore}/100 ${scoreBar}
--------------------------------------------------------------------------------

Company:    ${job.company}
Title:      ${job.title}
Location:   ${job.location}
Source:     ${job.source}${job.team ? `\nTeam:       ${job.team}` : ''}
URL:        ${job.url}

MATCH ANALYSIS:
${job.atsReasoning}

${job.description ? `DESCRIPTION PREVIEW:\n${job.description.substring(0, 500)}${job.description.length > 500 ? '...' : ''}\n` : ''}
`;
  }

  getScoreBar(score) {
    const filled = Math.round(score / 10);
    const empty = 10 - filled;
    const bar = '█'.repeat(filled) + '░'.repeat(empty);
    
    if (score >= 70) return `[${bar}] 🟢`;
    if (score >= 40) return `[${bar}] 🟡`;
    return `[${bar}] 🔴`;
  }

  generateJSON(results, resumeInfo) {
    const jsonPath = this.outputPath.replace('.txt', '.json');
    
    const data = {
      generatedAt: new Date().toISOString(),
      resume: {
        filePath: resumeInfo.filePath,
        numPages: resumeInfo.numPages
      },
      summary: {
        totalJobs: results.length,
        highMatches: results.filter(r => r.atsScore >= 70).length,
        mediumMatches: results.filter(r => r.atsScore >= 40 && r.atsScore < 70).length,
        lowMatches: results.filter(r => r.atsScore < 40).length
      },
      jobs: results.map((job, index) => ({
        rank: index + 1,
        company: job.company,
        title: job.title,
        location: job.location,
        url: job.url,
        source: job.source,
        atsScore: job.atsScore,
        atsReasoning: job.atsReasoning,
        description: job.description ? job.description.substring(0, 1000) : '',
        team: job.team || null,
        scoredAt: job.scoredAt
      }))
    };

    fs.writeFileSync(jsonPath, JSON.stringify(data, null, 2));
    console.log(`✓ JSON data saved to: ${jsonPath}`);
    
    return data;
  }
}

module.exports = ReportGenerator;