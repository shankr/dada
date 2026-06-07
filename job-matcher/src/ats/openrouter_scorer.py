#!/usr/bin/env python3

import logging
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

log = logging.getLogger(__name__)

STRENGTH_WEIGHTS = {"expert": 1.0, "strong": 0.8, "proficient": 0.6, "familiar": 0.4}


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def normalize_text(text):
    return re.sub(r"\s+", " ", (text or "")).strip()


def extract_json_object(text):
    text = (text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text).strip()
        text = re.sub(r"```$", "", text).strip()

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON object found in response")
    return json.loads(text[start:end + 1])


_MAX_RETRIES = 3
_RETRY_DELAYS = [5, 15, 30]


def call_openrouter(api_key, model, system_prompt, user_prompt):
    last_exc = None
    for attempt in range(_MAX_RETRIES):
        try:
            req = urllib.request.Request(
                "https://openrouter.ai/api/v1/chat/completions",
                data=json.dumps({
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": 0.0,
                    "max_tokens": 1200,
                }).encode("utf-8"),
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://job-scraper.local",
                    "X-Title": "Job Scraper ATS Python Normalizer",
                },
                method="POST",
            )

            with urllib.request.urlopen(req, timeout=300) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            return payload["choices"][0]["message"]["content"]
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as exc:
            last_exc = exc
            if attempt < _MAX_RETRIES - 1:
                delay = _RETRY_DELAYS[attempt]
                log.warning("OpenRouter call failed (attempt %d/%d): %s. Retrying in %ds...",
                            attempt + 1, _MAX_RETRIES, exc, delay)
                time.sleep(delay)
            else:
                log.error("OpenRouter call failed after %d attempts: %s", _MAX_RETRIES, exc)
    raise last_exc


def build_resume_prompt(resume_text):
    schema = {
        "candidate_seniority": "string",
        "management_type": "string",
        "primary_role_type": "string",
        "role_families": [{"role": "string", "weight": "float"}],
        "skills": ["string"],
        "skills_with_strength": [{"skill": "string", "strength": "string"}],
        "domains": ["string"],
        "leadership_signals": ["string"],
        "location": "string|null",
        "must_have_constraints": ["string"],
        "evidence": ["string"],
    }
    return (
        "Extract a normalized candidate profile from the resume. Return JSON only. Do not invent facts. "
        "Use `unknown` when unclear.\n\n"
        "1. Extract these fields from the resume:\n"
        f"   Schema: {json.dumps(schema)}\n\n"
        "2. Normalize all values:\n"
        "- Role families, primary_role_type: use ONLY these exact values — "
        "backend, frontend, full-stack, mobile, ios, android, machine-learning, data, "
        "data-platform, analytics, security, infrastructure, platform, devops, sre, cloud, qa, "
        "management, product-engineering. "
        "Include expanded secondary role_families (backend -> distributed-systems; full-stack -> frontend+backend; "
        "ML engineer -> data). Use hyphens not underscores or spaces.\n"
"- Skills: standard forms (React not react.js, Go not golang, Kubernetes not k8s, "
"PostgreSQL not postgresql, TypeScript not ts, etc.). "
"Strip cloud provider prefixes (aws, amazon, azure, gcp) from service names (DynamoDB not aws-dynamodb, S3 not aws-s3, SQS not aws-sqs).\n"
        "- Management type: ic, ic_lead, people_manager, executive_manager, unclear. "
        "lead/tech-lead/team-lead -> ic_lead; manager-of-people/director -> people_manager.\n"
        "- Seniority: intern, junior, mid, senior, staff, principal, unknown.\n"
"- Role_families: assign a weight (0.0-1.0) indicating strength in that role family. "
"Your primary role type -> weight 1.0, secondary -> 0.6-0.8, tertiary -> 0.3-0.5, distant -> 0.1-0.2.\n"
"- Skills_with_strength: rate each as 'expert', 'strong', 'proficient', or 'familiar'. "
"Skills listed first or most frequently/deeply -> higher rating.\n"
        "- Domains: expand to include related areas.\n\n"
        f"Resume text:\n{resume_text[:12000]}"
    )


def build_job_prompt(job):
    schema = {
        "role_family": "string",
        "secondary_role_families": ["string"],
        "seniority": "string",
        "management_type": "string",
        "people_management_required": "boolean",
        "required_skills": ["string"],
        "preferred_skills": ["string"],
        "required_domains": ["string"],
        "preferred_domains": ["string"],
        "must_have_qualifications": ["string"],
        "preferred_qualifications": ["string"],
        "hard_gates": ["string"],
        "work_mode": "string",
        "location_constraints": ["string"],
        "evidence": ["string"],
    }
    return (
        "Extract normalized job fields from the posting. Return JSON only. "
        "Do not invent requirements. Use `unknown`, empty arrays, or false when unclear.\n\n"
        "1. Extract these fields from the job description:\n"
        f"   Schema: {json.dumps(schema)}\n\n"
        "2. Normalize all values:\n"
        "- Role family, secondary_role_families: use ONLY these exact values — "
        "backend, frontend, full-stack, mobile, ios, android, machine-learning, data, "
        "data-platform, analytics, security, infrastructure, platform, devops, sre, cloud, qa, "
        "management, product-engineering. "
        "Include ALL secondary families the role spans. Use hyphens not underscores or spaces.\n"
"- Skills: standard forms (React not react.js, Go not golang, Kubernetes not k8s, "
"PostgreSQL not postgresql, TypeScript not ts, etc.). "
"Strip cloud provider prefixes (aws, amazon, azure, gcp) from service names (DynamoDB not aws-dynamodb, S3 not aws-s3, SQS not aws-sqs).\n"
        "- Management type: ic, ic_lead, people_manager, executive_manager, unclear. "
        "tech-lead/lead -> unclear/ic_lead; manager-of-people -> people_manager.\n"
        "- Seniority: intern, junior, mid, senior, staff, principal, unknown.\n\n"
        f"Job title: {job.get('title', '')}\n"
        f"Company: {job.get('company', '')}\n"
        f"Location: {job.get('location', '')}\n"
        f"Description:\n{(job.get('description') or '')[:12000]}"
    )


def listify(value):
    if isinstance(value, list):
        return [normalize_text(str(item)).lower() for item in value if normalize_text(str(item))]
    if value is None:
        return []
    text = normalize_text(str(value))
    return [text.lower()] if text else []


def normalize_skills_with_strength(raw_list):
    result = {}
    if not isinstance(raw_list, list):
        return result
    for entry in raw_list:
        if not isinstance(entry, dict):
            continue
        skill = normalize_text(str(entry.get("skill", ""))).lower()
        strength = normalize_text(str(entry.get("strength", "familiar"))).lower()
        if not skill:
            continue
        if strength not in STRENGTH_WEIGHTS:
            strength = "familiar"
        result[skill] = strength
    return result


def _normalize_role_families(raw):
    entries = raw if isinstance(raw, list) else []
    seen = {}
    for item in entries:
        if isinstance(item, dict):
            role = normalize_text(str(item.get("role", ""))).lower()
            weight = float(item.get("weight", 1.0))
        else:
            role = normalize_text(str(item)).lower()
            weight = 1.0
        if not role:
            continue
        weight = max(0.0, min(1.0, weight))
        if role not in seen or weight > seen[role]:
            seen[role] = weight
    return [{"role": r, "weight": w} for r, w in seen.items()]


def _get_role_family_names(families):
    names = set()
    for item in families:
        if isinstance(item, dict):
            names.add(item.get("role", ""))
        else:
            names.add(item)
    return names


def normalize_resume_profile(raw_profile, resume_text):
    profile = raw_profile if isinstance(raw_profile, dict) else {}
    role_families = _normalize_role_families(profile.get("role_families"))

    primary = normalize_text(str(profile.get("primary_role_type", ""))).lower()
    if not primary or primary == "unknown":
        primary = role_families[0]["role"] if role_families else "unknown"

    skills_with_strength = normalize_skills_with_strength(profile.get("skills_with_strength"))

    return {
        "candidate_seniority": normalize_text(str(profile.get("candidate_seniority", "unknown"))).lower().replace(" ", "-"),
        "management_type": normalize_text(str(profile.get("management_type", "unclear"))).lower().replace(" ", "_"),
        "primary_role_type": primary,
        "role_families": role_families,
        "skills": sorted(set(
            normalize_text(str(s)).lower() for s in listify(profile.get("skills"))
        )),
        "skills_with_strength": skills_with_strength,
        "domains": sorted(set(
            normalize_text(str(d)).lower() for d in listify(profile.get("domains"))
        )),
        "leadership_signals": listify(profile.get("leadership_signals")),
        "location": normalize_text(profile.get("location") or ""),
        "must_have_constraints": listify(profile.get("must_have_constraints")),
        "evidence": listify(profile.get("evidence"))[:8],
    }


def normalize_job_profile(raw_profile, job):
    profile = raw_profile if isinstance(raw_profile, dict) else {}
    role_family = normalize_text(str(profile.get("role_family", "unknown"))).lower()

    secondary = []
    for rf in listify(profile.get("secondary_role_families")):
        cleaned = normalize_text(str(rf)).lower()
        if cleaned not in ("unknown", role_family):
            secondary.append(cleaned)

    return {
        "role_family": role_family,
        "secondary_role_families": secondary,
        "seniority": normalize_text(str(profile.get("seniority", "unknown"))).lower().replace(" ", "-"),
        "management_type": normalize_text(str(profile.get("management_type", "unclear"))).lower().replace(" ", "_"),
        "people_management_required": bool(profile.get("people_management_required", False)),
        "required_skills": sorted(set(
            normalize_text(str(s)).lower() for s in listify(profile.get("required_skills"))
        )),
        "preferred_skills": sorted(set(
            normalize_text(str(s)).lower() for s in listify(profile.get("preferred_skills"))
        )),
        "required_domains": sorted(set(
            normalize_text(str(d)).lower() for d in listify(profile.get("required_domains"))
        )),
        "preferred_domains": sorted(set(
            normalize_text(str(d)).lower() for d in listify(profile.get("preferred_domains"))
        )),
        "must_have_qualifications": listify(profile.get("must_have_qualifications")),
        "preferred_qualifications": listify(profile.get("preferred_qualifications")),
        "hard_gates": listify(profile.get("hard_gates")),
        "work_mode": normalize_text(profile.get("work_mode") or "unknown").lower(),
        "location_constraints": listify(profile.get("location_constraints")),
        "evidence": listify(profile.get("evidence"))[:8],
    }


def seniority_rank(level):
    order = {
        "intern": 0,
        "junior": 1,
        "mid": 2,
        "senior": 3,
        "staff": 4,
        "principal": 5,
        "manager": 4,
        "senior-manager": 5,
        "director": 6,
        "unknown": 2,
    }
    return order.get(level, 2)


def overlap_ratio(left, right):
    left_set = set(left or [])
    right_set = set(right or [])
    if not left_set:
        return 1.0, []
    matches = sorted(left_set & right_set)
    return len(matches) / len(left_set), matches


def compute_score(resume_profile, job_profile):
    required_ratio, matched_required = overlap_ratio(job_profile["required_skills"], resume_profile["skills"])
    preferred_ratio, matched_preferred = overlap_ratio(job_profile["preferred_skills"], resume_profile["skills"])
    domain_ratio, matched_domains = overlap_ratio(job_profile["required_domains"], resume_profile["domains"])

    skills_with_strength = resume_profile.get("skills_with_strength", {})
    if skills_with_strength and matched_required:
        weighted_matches = sum(
            STRENGTH_WEIGHTS.get(skills_with_strength.get(skill, "familiar"), 0.4)
            for skill in matched_required
        )
        skill_strength_factor = weighted_matches / len(matched_required)
    else:
        skill_strength_factor = 1.0

    role_match = 1.0 if (
        job_profile["role_family"] == "unknown"
        or job_profile["role_family"] in _get_role_family_names(resume_profile.get("role_families", []))
    ) else 0.0

    secondary_roles = job_profile.get("secondary_role_families", [])
    if secondary_roles and role_match > 0:
        family_names = _get_role_family_names(resume_profile.get("role_families", []))
        secondary_matches = []
        for sr in secondary_roles:
            secondary_matches.append(1.0 if sr in family_names else 0.0)
        role_match = (role_match * 2 + sum(secondary_matches)) / (2 + len(secondary_matches))

    management_match = 1.0
    management_notes = []
    resume_mgmt = resume_profile["management_type"]
    job_mgmt = job_profile["management_type"]

    if job_profile["people_management_required"] and resume_mgmt not in {"people_manager", "executive_manager"}:
        management_match = 0.0
        management_notes.append("job requires people management but resume looks IC-oriented")
    elif job_mgmt == "people_manager" and resume_mgmt not in {"people_manager", "executive_manager"}:
        management_match = 0.2
        management_notes.append("job appears manager-oriented while resume looks more IC-oriented")
    elif job_mgmt == "ic_lead" and resume_mgmt == "ic":
        management_match = 0.7
        management_notes.append("job expects lead-level scope; resume shows less explicit leadership scope")

    seniority_match = 1.0
    if seniority_rank(resume_profile["candidate_seniority"]) + 1 < seniority_rank(job_profile["seniority"]):
        seniority_match = 0.25

    score = (
        required_ratio * 0.35 * skill_strength_factor +
        preferred_ratio * 0.10 +
        role_match * 0.20 +
        management_match * 0.15 +
        seniority_match * 0.10 +
        domain_ratio * 0.05
    )

    missing_required = sorted(set(job_profile["required_skills"]) - set(resume_profile["skills"]))
    missing_preferred = sorted(set(job_profile["preferred_skills"]) - set(resume_profile["skills"]))

    return {
        "score": round(max(0.0, min(1.0, score)) * 100),
        "required_skills_ratio": required_ratio,
        "preferred_skills_ratio": preferred_ratio,
        "domain_ratio": domain_ratio,
        "matched_required": matched_required,
        "matched_preferred": matched_preferred,
        "matched_domains": matched_domains,
        "missing_required": missing_required,
        "missing_preferred": missing_preferred,
        "role_match": role_match,
        "skill_strength_factor": skill_strength_factor,
        "management_match": management_match,
        "seniority_match": seniority_match,
        "management_notes": management_notes,
    }


def build_reasoning(job_profile, score_data):
    role_match = score_data.get("role_match", 0)
    lines = [
        f"Normalized role: {job_profile['role_family']} / {job_profile['seniority']} / {job_profile['management_type']}. Role match: {role_match:.2f}.",
        f"Required skill match: {len(score_data['matched_required'])}/{len(job_profile['required_skills'])}.",
    ]

    secondary_roles = job_profile.get("secondary_role_families", [])
    if secondary_roles:
        lines.append(f"  Secondary roles: {', '.join(secondary_roles)}.")

    if job_profile["preferred_skills"]:
        lines.append(
            f"Preferred skill match: {len(score_data['matched_preferred'])}/{len(job_profile['preferred_skills'])}."
        )

    if score_data["matched_required"]:
        lines.append("Matched required skills: " + ", ".join(score_data["matched_required"]) + ".")
    if score_data["missing_required"]:
        lines.append("Missing required skills: " + ", ".join(score_data["missing_required"][:8]) + ".")
    if score_data["missing_preferred"]:
        lines.append("Missing preferred skills: " + ", ".join(score_data["missing_preferred"][:6]) + ".")
    if score_data["management_notes"]:
        lines.extend(note[:1].upper() + note[1:] + "." for note in score_data["management_notes"])

    return "\n".join(lines)


def error_result(job, error_message):
    return {
        **job,
        "normalizedJob": None,
        "scoreBreakdown": None,
        "atsScore": 0,
        "atsReasoning": f"Error: {error_message}",
        "scoredAt": utc_now(),
    }


def openrouter_score_jobs(api_key, model, resume_text, jobs):
    system_prompt = (
        "You extract structured hiring information from resumes and job descriptions. "
        "Return only valid JSON. Never add facts not grounded in the text."
    )

    resume_raw = call_openrouter(
        api_key,
        model,
        system_prompt,
        build_resume_prompt(resume_text),
    )
    resume_profile = normalize_resume_profile(extract_json_object(resume_raw), resume_text)

    scored_jobs = []
    for job in jobs:
        try:
            job_raw = call_openrouter(
                api_key,
                model,
                system_prompt,
                build_job_prompt(job),
            )
            normalized_job = normalize_job_profile(extract_json_object(job_raw), job)
            score_data = compute_score(resume_profile, normalized_job)
            scored_jobs.append({
                **job,
                "normalizedJob": normalized_job,
                "scoreBreakdown": {
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
                    "managementNotes": score_data["management_notes"],
                },
                "atsScore": score_data["score"],
                "atsReasoning": build_reasoning(normalized_job, score_data),
                "scoredAt": utc_now(),
            })
        except (ValueError, KeyError, urllib.error.URLError, urllib.error.HTTPError, RuntimeError) as exc:
            scored_jobs.append(error_result(job, str(exc)))

    return {"normalizedResumeProfile": resume_profile, "jobs": scored_jobs}


def main():
    payload = json.load(sys.stdin)
    llm_cfg = payload.get("config", {}).get("llm", {})
    api_key = normalize_text(llm_cfg.get("api_key") or os.environ.get("OPENROUTER_KEY") or "")
    model = normalize_text(llm_cfg.get("model") or "openrouter/auto")

    if not api_key:
        raise RuntimeError("Missing OpenRouter API key for openrouter scorer")

    resume_text = payload.get("resumeText") or ""
    jobs = payload.get("jobs") or []

    system_prompt = (
        "You extract structured hiring information from resumes and job descriptions. "
        "Return only valid JSON. Never add facts not grounded in the text."
    )

    resume_raw = call_openrouter(
        api_key,
        model,
        system_prompt,
        build_resume_prompt(resume_text),
    )
    resume_profile = normalize_resume_profile(extract_json_object(resume_raw), resume_text)

    scored_jobs = []
    for job in jobs:
        try:
            job_raw = call_openrouter(
                api_key,
                model,
                system_prompt,
                build_job_prompt(job),
            )
            normalized_job = normalize_job_profile(extract_json_object(job_raw), job)
            score_data = compute_score(resume_profile, normalized_job)
            scored_jobs.append({
                **job,
                "normalizedJob": normalized_job,
                "scoreBreakdown": {
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
                    "managementNotes": score_data["management_notes"],
                },
                "atsScore": score_data["score"],
                "atsReasoning": build_reasoning(normalized_job, score_data),
                "scoredAt": utc_now(),
            })
        except (ValueError, KeyError, urllib.error.URLError, urllib.error.HTTPError, RuntimeError) as exc:
            scored_jobs.append(error_result(job, str(exc)))

    json.dump({
        "normalizedResumeProfile": resume_profile,
        "jobs": scored_jobs
    }, sys.stdout)


if __name__ == "__main__":
    main()
