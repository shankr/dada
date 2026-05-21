#!/usr/bin/env python3

import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone


ROLE_FAMILIES = [
    "backend", "frontend", "full-stack", "mobile", "ios", "android",
    "machine-learning", "data", "data-platform", "analytics", "security",
    "infrastructure", "platform", "devops", "sre", "cloud", "qa",
    "management", "product-engineering"
]

SENIORITY_LEVELS = [
    "intern", "junior", "mid", "senior", "staff", "principal",
    "manager", "senior-manager", "director", "unknown"
]

MANAGEMENT_TYPES = [
    "ic", "ic_lead", "people_manager", "executive_manager", "unclear"
]

SKILL_ONTOLOGY = [
    "python", "java", "javascript", "typescript", "node.js", "react",
    "angular", "vue", "go", "golang", "ruby", "rails", "php", "c#",
    ".net", "scala", "kotlin", "swift", "sql", "postgresql", "mysql",
    "mongodb", "redis", "elasticsearch", "spark", "hadoop", "airflow",
    "dbt", "snowflake", "bigquery", "aws", "gcp", "azure", "docker",
    "kubernetes", "terraform", "pulumi", "ansible", "jenkins", "github actions",
    "grpc", "rest", "graphql", "microservices", "distributed systems",
    "system design", "linux", "ci/cd", "observability", "prometheus",
    "grafana", "machine learning", "llm", "rag", "vector database",
    "pytorch", "tensorflow", "scikit-learn", "nlp", "computer vision",
    "security", "oauth", "oidc", "saml", "networking", "leadership",
    "mentoring", "people management", "architecture", "product sense"
]

DOMAIN_ONTOLOGY = [
    "fintech", "e-commerce", "developer tools", "cloud infrastructure",
    "machine learning", "ml platform", "ads", "security", "healthcare",
    "consumer", "enterprise saas", "data platform", "observability"
]

STRENGTH_LEVELS = ["expert", "strong", "proficient", "familiar"]
STRENGTH_WEIGHTS = {"expert": 1.0, "strong": 0.8, "proficient": 0.6, "familiar": 0.4}

ROLE_KEYWORDS = {
    "backend": ["backend", "server", "api", "distributed systems"],
    "frontend": ["frontend", "ui", "web application", "react", "angular", "vue"],
    "full-stack": ["full stack", "full-stack"],
    "mobile": ["mobile"],
    "ios": ["ios", "swift"],
    "android": ["android", "kotlin"],
    "machine-learning": ["machine learning", "ml", "llm", "nlp"],
    "data": ["data engineer", "etl", "warehouse", "analytics"],
    "data-platform": ["data platform", "platform"],
    "security": ["security", "identity", "oauth", "oidc"],
    "infrastructure": ["infrastructure", "terraform", "kubernetes"],
    "platform": ["platform", "developer productivity"],
    "devops": ["devops", "ci/cd"],
    "sre": ["sre", "reliability", "observability"],
    "management": ["manager", "director", "leadership", "people management"],
}


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


def call_openrouter(api_key, model, system_prompt, user_prompt):
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

    with urllib.request.urlopen(req, timeout=120) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    return payload["choices"][0]["message"]["content"]


def build_resume_prompt(resume_text):
    schema = {
        "candidate_seniority": "string",
        "management_type": "string",
        "primary_role_type": "string",
        "role_families": ["string"],
        "role_features": ["string"],
        "skills": ["string"],
        "skills_with_strength": [{"skill": "string", "strength": "string"}],
        "domains": ["string"],
        "leadership_signals": ["string"],
        "location": "string|null",
        "must_have_constraints": ["string"],
        "evidence": ["string"],
    }
    return (
        "Extract a normalized candidate profile from the resume. "
        "Return JSON only. Do not invent facts. Use `unknown` when unclear. "
        "Identify the candidate's primary_role_type (e.g. backend, frontend, full-stack, mobile, data, machine-learning, devops). "
        "Extract role_features: a list of ~3-8 free-form strings describing the candidate's core technical domain (e.g. 'server-side development', 'API design', 'distributed systems'). "
        "Extract skills_with_strength: rate each skill as 'expert', 'strong', 'proficient', or 'familiar'. "
        "Skills listed first or mentioned most frequently/deeply in experience should be rated higher. "
        f"Expected schema: {json.dumps(schema)}\n\n"
        f"Resume text:\n{resume_text[:12000]}"
    )


def build_job_prompt(job):
    schema = {
        "role_family": "string",
        "secondary_role_families": ["string"],
        "role_features": ["string"],
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
        "Extract normalized job fields from the posting. "
        "Return JSON only. Do not invent requirements. Use `unknown`, empty arrays, or false when unclear. "
        "Identify the job's role_family (primary software engineering type) and secondary_role_families if the role spans multiple areas. "
        "Extract role_features: a list of ~3-8 free-form strings describing the job's core technical domain (e.g. 'mobile development', 'iOS', 'UI implementation'). "
        f"Expected schema: {json.dumps(schema)}\n\n"
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


def normalize_role_family(value, source_text):
    text = normalize_text(str(value)).lower()
    if text in ROLE_FAMILIES:
        return text
    haystack = f"{source_text} {text}".lower()
    for family, keywords in ROLE_KEYWORDS.items():
        if any(keyword in haystack for keyword in keywords):
            return family
    return "unknown"


def normalize_seniority(value, source_text):
    text = normalize_text(str(value)).lower().replace(" ", "-")
    if text in SENIORITY_LEVELS:
        return text

    haystack = f"{source_text} {text}".lower()
    checks = [
        ("director", ["director"]),
        ("senior-manager", ["senior manager"]),
        ("manager", ["engineering manager", "manager"]),
        ("principal", ["principal"]),
        ("staff", ["staff"]),
        ("senior", ["senior", "sr."]),
        ("mid", ["mid", "intermediate"]),
        ("junior", ["junior", "jr."]),
        ("intern", ["intern"]),
    ]
    for level, words in checks:
        if any(word in haystack for word in words):
            return level
    return "unknown"


def normalize_management_type(value, source_text):
    text = normalize_text(str(value)).lower().replace(" ", "_")
    alias_map = {
        "ic": "ic",
        "individual_contributor": "ic",
        "tech_lead": "ic_lead",
        "team_lead": "ic_lead",
        "lead": "ic_lead",
        "ic_lead": "ic_lead",
        "people_manager": "people_manager",
        "manager_of_people": "people_manager",
        "executive_manager": "executive_manager",
        "unclear": "unclear",
    }
    if text in alias_map:
        return alias_map[text]

    haystack = f"{source_text} {text}".lower()
    if any(term in haystack for term in ["manage engineers", "people manager", "engineering manager", "direct reports"]):
        return "people_manager"
    if any(term in haystack for term in ["mentor engineers", "technical lead", "lead cross-functional"]):
        return "ic_lead"
    if "manager" in haystack or "director" in haystack:
        return "people_manager"
    return "ic"


def normalize_skill_list(values, source_text):
    items = set()
    haystack = source_text.lower()

    for raw in listify(values):
        raw_clean = raw.replace("js", "javascript").replace("ts", "typescript")
        for skill in SKILL_ONTOLOGY:
            if skill == raw_clean or skill in raw_clean or raw_clean in skill:
                items.add(skill)
                break
        else:
            if raw_clean:
                items.add(raw_clean)

    for skill in SKILL_ONTOLOGY:
        if skill in haystack:
            items.add(skill)

    return sorted(items)


def normalize_domain_list(values, source_text):
    items = set()
    haystack = source_text.lower()
    for raw in listify(values):
        for domain in DOMAIN_ONTOLOGY:
            if domain == raw or domain in raw or raw in domain:
                items.add(domain)
                break
        else:
            if raw:
                items.add(raw)

    for domain in DOMAIN_ONTOLOGY:
        if domain in haystack:
            items.add(domain)

    return sorted(items)


def normalize_skills_with_strength(raw_list):
    result = {}
    if not isinstance(raw_list, list):
        return result
    for entry in raw_list:
        if not isinstance(entry, dict):
            continue
        skill = normalize_text(str(entry.get("skill", "")))
        strength = normalize_text(str(entry.get("strength", "familiar"))).lower()
        if not skill:
            continue
        if strength not in STRENGTH_LEVELS:
            strength = "familiar"
        result[skill] = strength
    return result


def normalize_resume_profile(raw_profile, resume_text):
    profile = raw_profile if isinstance(raw_profile, dict) else {}
    role_families = listify(profile.get("role_families"))
    if not role_families:
        inferred = normalize_role_family("", resume_text)
        role_families = [inferred] if inferred != "unknown" else []

    primary = normalize_text(str(profile.get("primary_role_type", ""))).lower()
    if not primary or primary == "unknown":
        primary = role_families[0] if role_families else "unknown"

    skills_with_strength = normalize_skills_with_strength(profile.get("skills_with_strength"))

    return {
        "candidate_seniority": normalize_seniority(profile.get("candidate_seniority", "unknown"), resume_text),
        "management_type": normalize_management_type(profile.get("management_type", "unclear"), resume_text),
        "primary_role_type": primary,
        "role_families": sorted(set(role_families)),
        "role_features": listify(profile.get("role_features")),
        "skills": normalize_skill_list(profile.get("skills"), resume_text),
        "skills_with_strength": skills_with_strength,
        "domains": normalize_domain_list(profile.get("domains"), resume_text),
        "leadership_signals": listify(profile.get("leadership_signals")),
        "location": normalize_text(profile.get("location") or ""),
        "must_have_constraints": listify(profile.get("must_have_constraints")),
        "evidence": listify(profile.get("evidence"))[:8],
    }


def normalize_job_profile(raw_profile, job):
    text = f"{job.get('title', '')} {(job.get('description') or '')}"
    profile = raw_profile if isinstance(raw_profile, dict) else {}

    secondary = []
    for rf in listify(profile.get("secondary_role_families")):
        cleaned = normalize_role_family(rf, text)
        if cleaned not in ("unknown", profile.get("role_family", "")):
            secondary.append(cleaned)

    return {
        "role_family": normalize_role_family(profile.get("role_family", "unknown"), text),
        "secondary_role_families": secondary,
        "role_features": listify(profile.get("role_features")),
        "seniority": normalize_seniority(profile.get("seniority", "unknown"), text),
        "management_type": normalize_management_type(profile.get("management_type", "unclear"), text),
        "people_management_required": bool(profile.get("people_management_required", False)),
        "required_skills": normalize_skill_list(profile.get("required_skills"), text),
        "preferred_skills": normalize_skill_list(profile.get("preferred_skills"), text),
        "required_domains": normalize_domain_list(profile.get("required_domains"), text),
        "preferred_domains": normalize_domain_list(profile.get("preferred_domains"), text),
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
        or job_profile["role_family"] in set(resume_profile.get("role_families", []))
    ) else 0.0

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
        "role_similarity": role_match,
        "role_penalty": 0,
        "skill_strength_factor": skill_strength_factor,
        "management_match": management_match,
        "seniority_match": seniority_match,
        "management_notes": management_notes,
    }


def build_reasoning(job_profile, score_data):
    lines = [
        f"Normalized role: {job_profile['role_family']} / {job_profile['seniority']} / {job_profile['management_type']}.",
        f"Required skill match: {len(score_data['matched_required'])}/{len(job_profile['required_skills'])}.",
    ]

    role_sim = score_data.get("role_similarity")
    if role_sim is not None:
        lines.append(f"Role type similarity: {role_sim:.2f}.")

    skill_factor = score_data.get("skill_strength_factor")
    if skill_factor is not None and skill_factor != 1.0:
        lines.append(f"Skill strength adjustment: {skill_factor:.2f}.")

    role_penalty = score_data.get("role_penalty", 0)
    if role_penalty > 0:
        lines.append(f"Role mismatch penalty: -{role_penalty:.2f}.")

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
                    "roleSimilarity": score_data.get("role_similarity"),
                    "rolePenalty": score_data.get("role_penalty", 0),
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
                    "roleSimilarity": score_data.get("role_similarity"),
                    "rolePenalty": score_data.get("role_penalty", 0),
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
