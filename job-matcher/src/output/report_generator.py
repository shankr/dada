import json
import os
from datetime import datetime


class ReportGenerator:
    def __init__(self, output_path):
        self.output_path = output_path

    def generate(self, results, resume_info):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        total_jobs = len(results)
        new_jobs = self._get_new_jobs(results)
        high_matches = sum(1 for r in results if r.get("atsScore", 0) >= 70)
        medium_matches = sum(1 for r in results if 40 <= r.get("atsScore", 0) < 70)
        low_matches = sum(1 for r in results if r.get("atsScore", 0) < 40)

        lines = [
            "=" * 80,
            "                    JOB MATCH REPORT - ATS SCORING RESULTS",
            "=" * 80,
            "",
            f"Generated: {timestamp}",
            f"Resume: {resume_info.get('filePath', '')}",
            f"Resume Pages: {resume_info.get('numPages', 0)}",
            "",
            "=" * 80,
            "                              SUMMARY",
            "=" * 80,
            "",
            f"Total Jobs Analyzed: {total_jobs}",
            f"New Jobs Since Last Run: {len(new_jobs)}",
            f"High Matches (70-100): {high_matches}",
            f"Medium Matches (40-69): {medium_matches}",
            f"Low Matches (0-39): {low_matches}",
            "",
        ]

        resume_section = self._format_normalized_resume_section(results)
        if resume_section:
            lines.extend(resume_section)

        new_jobs_section = self._format_new_jobs_section(new_jobs)
        if new_jobs_section:
            lines.extend(new_jobs_section)

        lines.extend([
            "=" * 80,
            "                           RANKED JOB LISTINGS",
            "=" * 80,
            "",
        ])

        high = [r for r in results if r.get("atsScore", 0) >= 70]
        medium = [r for r in results if 40 <= r.get("atsScore", 0) < 70]
        low = [r for r in results if r.get("atsScore", 0) < 40]

        rank = 1
        if high:
            lines.extend([
                "",
                "=" * 80,
                "                     HIGH MATCH JOBS (Score: 70-100)",
                "=" * 80,
                "",
            ])
            for job in high:
                lines.append(self._format_job_entry(job, rank))
                rank += 1

        if medium:
            lines.extend([
                "",
                "=" * 80,
                "                   MEDIUM MATCH JOBS (Score: 40-69)",
                "=" * 80,
                "",
            ])
            for job in medium:
                lines.append(self._format_job_entry(job, rank))
                rank += 1

        if low:
            lines.extend([
                "",
                "=" * 80,
                "                      LOW MATCH JOBS (Score: 0-39)",
                "=" * 80,
                "",
            ])
            for job in low:
                lines.append(self._format_job_entry(job, rank))
                rank += 1

        lines.extend([
            "",
            "=" * 80,
            "                                END OF REPORT",
            "=" * 80,
            "",
            "Notes:",
            "- ATS scores are generated using AI and should be used as a guide, not definitive",
            "- Always review job descriptions personally before applying",
            "- Scores combine normalized skills, management/seniority alignment, recency, and qualification-gap penalties",
            "- Job listings are sorted by match score (highest first)",
            "",
        ])

        report = "\n".join(lines)

        os.makedirs(os.path.dirname(self.output_path), exist_ok=True)
        with open(self.output_path, "w") as f:
            f.write(report)

        return report

    def _format_job_entry(self, job, rank):
        score = job.get("atsScore", 0)
        score_bar = self._get_score_bar(score)

        lines = [
            "-" * 80,
            f" Rank #{rank} | ATS Score: {score}/100 {score_bar}",
            "-" * 80,
            "",
            f"Company:    {job.get('company', '')}",
            f"Title:      {job.get('title', '')}",
            f"Location:   {job.get('location', '')}",
            f"Source:     {job.get('source', '')}",
        ]

        team = job.get("team")
        if team:
            lines.append(f"Team:       {team}")

        lines.append(f"URL:        {job.get('url', '')}")

        posted = job.get("postedDate")
        if posted:
            lines.append(f"Posted:     {posted}")
        first_seen = job.get("firstSeenAt")
        if first_seen:
            lines.append(f"First Seen: {first_seen}")

        normalized = job.get("normalizedJob")
        if normalized:
            parts = []
            if normalized.get("role_family"):
                parts.append(f"Role Family: {normalized['role_family']}")
            if normalized.get("seniority"):
                parts.append(f"Seniority: {normalized['seniority']}")
            if normalized.get("management_type"):
                parts.append(f"Management: {normalized['management_type']}")
            required = normalized.get("required_skills", [])
            if required:
                parts.append(f"Required Skills: {', '.join(required[:8])}")
            if parts:
                lines.append("")
                lines.extend(parts)

        breakdown = job.get("scoreBreakdown")
        if breakdown:
            def pct(v):
                return f"{round((v or 0) * 100)}%"
            lines.append("")
            lines.append(
                f"Score Breakdown: required {pct(breakdown.get('requiredSkillsRatio'))}, "
                f"preferred {pct(breakdown.get('preferredSkillsRatio'))}, "
                f"role {pct(breakdown.get('roleMatch'))}, "
                f"management {pct(breakdown.get('managementMatch'))}, "
                f"seniority {pct(breakdown.get('seniorityMatch'))}, "
                f"domain {pct(breakdown.get('domainMatch'))}, "
                f"explicit {pct(breakdown.get('explicitMatchRatio'))}"
            )
            matched = breakdown.get("matchedRequired", [])
            if matched:
                lines.append(f"Matched Required: {', '.join(matched)}")
            missing = breakdown.get("missingRequired", [])
            if missing:
                lines.append(f"Missing Required: {', '.join(missing)}")
            matched_preferred = breakdown.get("matchedPreferred", [])
            if matched_preferred:
                lines.append(f"Matched Preferred: {', '.join(matched_preferred)}")
            missing_preferred = breakdown.get("missingPreferred", [])
            if missing_preferred:
                lines.append(f"Missing Preferred: {', '.join(missing_preferred)}")

        reasoning = job.get("atsReasoning", "")
        if reasoning:
            lines.extend(["", "MATCH ANALYSIS:", reasoning])

        desc = job.get("description", "")
        if desc:
            preview = desc[:500]
            if len(desc) > 500:
                preview += "..."
            lines.extend(["", "DESCRIPTION PREVIEW:", preview])

        return "\n".join(lines)

    @staticmethod
    def _get_score_bar(score):
        filled = round(score / 10)
        empty = 10 - filled
        bar = "█" * filled + "░" * empty
        if score >= 70:
            return f"[{bar}] [green]"
        if score >= 40:
            return f"[{bar}] [yellow]"
        return f"[{bar}] [red]"

    @staticmethod
    def _get_new_jobs(results):
        return [j for j in results if j.get("isNewThisRun") is True]

    @staticmethod
    def _format_new_jobs_section(new_jobs):
        lines = [
            "=" * 80,
            "                         NEW JOBS SINCE LAST RUN",
            "=" * 80,
            "",
        ]
        if not new_jobs:
            lines.append("No new jobs were detected since the previous run.\n")
            return lines

        for idx, job in enumerate(new_jobs, 1):
            lines.append(f"{idx}. {job.get('title', '')} | {job.get('company', '')} | {job.get('location', '')}")
            lines.append(f"   URL: {job.get('url', '')}")
            posted = job.get("postedDate")
            if posted:
                lines.append(f"   Posted: {posted}")
            first_seen = job.get("firstSeenAt")
            if first_seen:
                lines.append(f"   First Seen: {first_seen}")
            lines.append(f"   Score: {job.get('atsScore', 0)}\n")

        return lines

    @staticmethod
    def _format_normalized_resume_section(results):
        profile = None
        for job in results:
            p = job.get("normalizedResumeProfile")
            if p:
                profile = p
                break
        if not profile:
            return []

        lines = [
            "=" * 80,
            "                     NORMALIZED RESUME PROFILE",
            "=" * 80,
            "",
        ]
        if profile.get("candidate_seniority"):
            lines.append(f"Candidate Seniority: {profile['candidate_seniority']}")
        if profile.get("management_type"):
            lines.append(f"Management Type: {profile['management_type']}")
        families = profile.get("role_families", [])
        if families:
            lines.append(f"Role Families: {', '.join(families)}")
        skills = profile.get("skills", [])
        if skills:
            lines.append(f"Skills: {', '.join(skills[:20])}")
        domains = profile.get("domains", [])
        if domains:
            lines.append(f"Domains: {', '.join(domains)}")
        signals = profile.get("leadership_signals", [])
        if signals:
            lines.append(f"Leadership Signals: {', '.join(signals[:8])}")
        lines.append("")

        return lines

    def generate_json(self, results, resume_info):
        json_path = self.output_path.replace(".txt", ".json")
        new_jobs = self._get_new_jobs(results)

        profile = None
        for job in results:
            p = job.get("normalizedResumeProfile")
            if p:
                profile = p
                break

        data = {
            "generatedAt": datetime.now().isoformat(),
            "resume": {
                "filePath": resume_info.get("filePath", ""),
                "numPages": resume_info.get("numPages", 0),
                "normalizedProfile": profile or None,
            },
            "summary": {
                "totalJobs": len(results),
                "newJobsSinceLastRun": len(new_jobs),
                "highMatches": sum(1 for r in results if r.get("atsScore", 0) >= 70),
                "mediumMatches": sum(1 for r in results if 40 <= r.get("atsScore", 0) < 70),
                "lowMatches": sum(1 for r in results if r.get("atsScore", 0) < 40),
            },
            "newJobs": [
                {
                    "rank": idx + 1,
                    "company": j.get("company", ""),
                    "title": j.get("title", ""),
                    "location": j.get("location", ""),
                    "url": j.get("url", ""),
                    "postedDate": j.get("postedDate"),
                    "firstSeenAt": j.get("firstSeenAt"),
                    "isNewThisRun": True,
                    "atsScore": j.get("atsScore", 0),
                }
                for idx, j in enumerate(new_jobs)
            ],
            "jobs": [
                {
                    "rank": idx + 1,
                    "company": j.get("company", ""),
                    "title": j.get("title", ""),
                    "location": j.get("location", ""),
                    "url": j.get("url", ""),
                    "source": j.get("source", ""),
                    "postedDate": j.get("postedDate"),
                    "atsScore": j.get("atsScore", 0),
                    "atsReasoning": j.get("atsReasoning", ""),
                    "description": (j.get("description") or "")[:1000],
                    "normalizedJob": j.get("normalizedJob"),
                    "scoreBreakdown": j.get("scoreBreakdown"),
                    "team": j.get("team"),
                    "firstSeenAt": j.get("firstSeenAt"),
                    "lastSeenAt": j.get("lastSeenAt"),
                    "isNewThisRun": j.get("isNewThisRun", False),
                    "scoredAt": j.get("scoredAt"),
                }
                for idx, j in enumerate(results)
            ],
        }

        with open(json_path, "w") as f:
            json.dump(data, f, indent=2)

        return data
