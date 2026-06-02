import sys
import sqlite3
import json
from datetime import datetime, timezone

sys.path.insert(0, ".")

from src.config.config_loader import ConfigLoader
from src.storage.ats_cache_db import ATSCacheDB
from src.parsers.pdf_parser import PDFParser
from src.output.report_generator import ReportGenerator
from src.ats.ats_scorer import ATSScorer


def main():
    config = ConfigLoader.load()
    resume_path = config["resume_path"]
    output_path = config["output_path"]
    cache_db_path = config["ats_cache_db_path"]
    llm_cfg = config.get("llm", {})
    llm_version = int(llm_cfg.get("extraction_version", 1))

    parser = PDFParser(resume_path)
    resume_data = parser.extract_resume_data()
    resume_text = resume_data["cleanText"]

    cache_db = ATSCacheDB(cache_db_path)
    cache_db.initialize()
    resume_key = cache_db.compute_resume_key(resume_text)
    resume_profile = cache_db.get_resume_profile(resume_key, llm_version)
    if not resume_profile:
        print("No resume profile in cache")
        sys.exit(1)

    scorer = ATSScorer(config, cache_db)

    db = sqlite3.connect(cache_db_path)
    db.row_factory = sqlite3.Row

    rows = db.execute(
        "SELECT * FROM job_results WHERE normalized_job_json IS NOT NULL AND normalized_job_json != ''"
    ).fetchall()
    print(f"Rescoring {len(rows)} jobs...")

    updated = []
    for i, row in enumerate(rows):
        job = {
            "url": row["job_url"],
            "title": row["title"],
            "company": row["company"],
            "location": row["location"],
            "description": row["description"],
            "postedDate": row["posted_date"],
            "source": row["source"],
        }
        job_profile = json.loads(row["normalized_job_json"])
        score_data = scorer._compute_score(resume_profile, job_profile, job, resume_text)
        reasoning = scorer._build_reasoning(job_profile, score_data)
        score = round(score_data["score"])

        breakdown = {
            "requiredSkillsRatio": score_data["required_skills_ratio"],
            "preferredSkillsRatio": score_data["preferred_skills_ratio"],
            "domainMatch": score_data["domain_ratio"],
            "roleMatch": score_data["role_match"],
            "skillStrengthFactor": score_data.get("skill_strength_factor", 1.0),
            "managementMatch": score_data["management_match"],
            "seniorityMatch": score_data["seniority_match"],
            "matchedRequired": score_data["matched_required"],
            "matchedPreferred": score_data["matched_preferred"],
            "matchedDomains": score_data["matched_domains"],
            "missingRequired": score_data["missing_required"],
            "missingPreferred": score_data["missing_preferred"],
            "managementNotes": score_data.get("management_notes", []),
            "qualificationAnalysis": score_data.get("qualification_analysis"),
        }

        now = datetime.now(timezone.utc).isoformat()
        db.execute(
            "UPDATE job_results SET ats_score=?, ats_reasoning=?, score_breakdown_json=?, scored_at=? WHERE job_url=?",
            (score, reasoning, json.dumps(breakdown), now, job["url"]),
        )

        updated.append({
            "title": job["title"],
            "company": job["company"],
            "location": job["location"],
            "url": job["url"],
            "description": job["description"],
            "postedDate": job.get("postedDate", ""),
            "source": job.get("source", ""),
            "normalizedJob": job_profile,
            "normalizedResumeProfile": resume_profile,
            "scoreBreakdown": breakdown,
            "atsScore": score,
            "atsReasoning": reasoning,
            "scoredAt": now,
            "provider": "extract:local-hybrid",
            "model": llm_cfg.get("model", ""),
        })

        if (i + 1) % 30 == 0:
            db.commit()
            print(f"  {i+1}/{len(rows)}")

    db.commit()
    db.close()
    print(f"DB updated: {len(updated)} jobs")

    updated.sort(key=lambda j: j["atsScore"], reverse=True)

    resume_info = {
        "filePath": resume_path,
        "numPages": resume_data["numPages"],
    }
    report_gen = ReportGenerator(output_path)
    report_gen.generate(updated, resume_info)
    report_gen.generate_json(updated, resume_info)
    print(f"Reports written to {output_path}")


if __name__ == "__main__":
    main()