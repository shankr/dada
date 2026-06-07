import json
import logging
import os
import re
from datetime import datetime, timezone

from sentence_transformers import SentenceTransformer

log = logging.getLogger(__name__)

STRENGTH_WEIGHTS = {"expert": 1.0, "strong": 0.8, "proficient": 0.6, "familiar": 0.4}

SENIORITY_ORDER = {
    "intern": 0, "junior": 1, "mid": 2, "senior": 3,
    "staff": 4, "principal": 5, "manager": 4,
    "senior-manager": 5, "director": 6, "unknown": 2,
}


_SECTION_HEADERS = [
    r"technical\s+skills",
    r"experience",
    r"selected\s+projects",
    r"education",
]

_EDUCATION_KEYWORDS = [
    "bachelor", "master", "phd", "degree", "bs ", "ms ", "ba ",
    "education", "university", "college",
]


class ATSScorer:
    def __init__(self, config, cache_db):
        self.config = config
        self.cache_db = cache_db
        self._embedding_model = None
        self._scoring_cfg = None
        self._role_sim_cache = {}
        self._cached_resume_embedding = None
        self._cached_resume_text = None

    def get_scoring_config(self):
        if self._scoring_cfg:
            return self._scoring_cfg

        defaults = {
            "embedding_model": "BAAI/bge-small-en-v1.5",
            "weights": {
                "lexical": 0.20,
                "embedding": 0.45,
                "recency": 0.15,
            },
            "recency": {"half_life_days": 30, "max_bonus": 0.10},
            "embedding_match_threshold": 0.62,
            "required_qualifications_penalty_max": 0.30,
            "required_qualifications_penalty_per_bullet": 0.06,
            "preferred_qualifications_penalty_max": 0.12,
            "preferred_qualifications_penalty_per_bullet": 0.03,
            "named_required_tech_match_threshold": 0.58,
            "named_required_tech_penalty_per_term": 0.08,
            "named_required_tech_penalty_max": 0.24,
            "named_preferred_tech_penalty_per_term": 0.04,
            "named_preferred_tech_penalty_max": 0.12,
        }

        cfg = dict(self.config.get("scoring", {}))
        result = {}

        w = dict(defaults["weights"])
        user_w = cfg.get("weights", {})
        for k in w:
            if k in user_w:
                w[k] = float(user_w[k])
        result["weights"] = w

        result["embeddingModel"] = cfg.get("embedding_model", defaults["embedding_model"])

        result["recency"] = dict(defaults["recency"])
        user_rec = cfg.get("recency", {})
        for k in result["recency"]:
            if k in user_rec:
                result["recency"][k] = float(user_rec[k]) if isinstance(user_rec[k], (int, float)) else user_rec[k]

        for key in ("embedding_match_threshold", "required_qualifications_penalty_max",
                     "required_qualifications_penalty_per_bullet",
                     "preferred_qualifications_penalty_max",
                     "preferred_qualifications_penalty_per_bullet",
                     "named_required_tech_match_threshold",
                     "named_required_tech_penalty_per_term",
                     "named_required_tech_penalty_max",
                     "named_preferred_tech_penalty_per_term",
                     "named_preferred_tech_penalty_max"):
            result[key] = float(cfg.get(key, defaults[key]))

        self._scoring_cfg = result
        return result

    async def score_jobs_batch(self, resume_text, jobs, on_progress=None):
        self.cache_db.initialize()

        force_recompute = self.config.get("scoring", {}).get("force_recompute", False)

        llm_cfg = self.config.get("llm", {})
        api_key = llm_cfg.get("api_key") or os.environ.get("OPENROUTER_KEY", "")
        model = llm_cfg.get("model", "openrouter/auto")
        llm_version = int(llm_cfg.get("extraction_version", 1))

        scored = []
        total = len(jobs)

        resume_profile = None
        resume_key = self.cache_db.compute_resume_key(resume_text) if resume_text else None
        cached_resume = self.cache_db.get_resume_profile(resume_key, llm_version) if resume_key else None
        if cached_resume is not None:
            resume_profile = cached_resume
            log.info("Resume profile loaded from cache (v%s)", llm_version)

        if not force_recompute:
            uncached = [j for j in jobs if not self.cache_db.get_by_url(j.get("url"), llm_version, resume_key or "")]
        else:
            uncached = list(jobs)

        if resume_profile is None and uncached:
            resume_profile = await self._compute_resume_profile(resume_text, api_key, model)
            if resume_key:
                resume_path = self.config.get("resume_path", "")
                self.cache_db.set_resume_profile(resume_key, llm_version, resume_path, resume_profile)
        elif not uncached:
            log.info("All jobs cached, skipping LLM entirely")

        for idx, job in enumerate(jobs):
            cached = None if force_recompute else self.cache_db.get_by_url(job.get("url"), llm_version, resume_key or "")
            if cached:
                job_data = dict(job)
                stored_job = self.cache_db.get_job_by_url(job.get("url")) if job.get("url") else None
                job_data["atsScore"] = cached["score"]
                job_data["atsReasoning"] = cached["reasoning"]
                job_data["scoredAt"] = cached["scoredAt"]
                job_data["provider"] = cached["provider"]
                job_data["model"] = cached["model"]
                if stored_job:
                    job_data["normalizedJob"] = stored_job.get("normalizedJob")
                    job_data["scoreBreakdown"] = stored_job.get("scoreBreakdown")
                    job_data["firstSeenAt"] = stored_job.get("firstSeenAt", "")
                    job_data["lastSeenAt"] = stored_job.get("lastSeenAt", "")
                scored.append(job_data)
                log.info("  ✓ %s (cached, score: %d)", job.get("title", "")[:60], job_data["atsScore"])
                continue

            if on_progress:
                on_progress(job, idx, total)

            try:
                job_profile = await self._normalize_job_profile_with_llm(job, api_key, model)
            except Exception as exc:
                log.error("LLM extraction failed for %s after retries: %s", job.get("title", ""), exc)
                job_data = dict(job)
                job_data["atsScore"] = 0
                job_data["atsReasoning"] = f"Error: LLM extraction failed: {exc}"
                job_data["scoredAt"] = datetime.now(timezone.utc).isoformat()
                scored.append(job_data)
                continue

            score_data = self._compute_score(resume_profile, job_profile, job, resume_text)
            reasoning = self._build_reasoning(job_profile, score_data)

            job_data = dict(job)
            job_data["normalizedJob"] = job_profile
            job_data["scoreBreakdown"] = {
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
            job_data["atsScore"] = score_data["score"]
            job_data["atsReasoning"] = reasoning
            job_data["scoredAt"] = datetime.now(timezone.utc).isoformat()
            job_data["provider"] = f"extract:{model} score:local-hybrid"
            job_data["model"] = model
            scored.append(job_data)

            self.cache_db.upsert(
                job_data,
                {
                    "score": job_data["atsScore"],
                    "reasoning": job_data["atsReasoning"],
                    "timestamp": job_data["scoredAt"],
                    "normalizedJob": job_data.get("normalizedJob"),
                    "scoreBreakdown": job_data.get("scoreBreakdown"),
                },
                f"extract:{model}",
                model,
                llm_version,
                resume_key or "",
            )
            stored_job = self.cache_db.get_job_by_url(job_data.get("url")) if job_data.get("url") else None
            if stored_job:
                job_data["normalizedJob"] = stored_job.get("normalizedJob")
                job_data["scoreBreakdown"] = stored_job.get("scoreBreakdown")
                job_data["firstSeenAt"] = stored_job.get("firstSeenAt", "")
                job_data["lastSeenAt"] = stored_job.get("lastSeenAt", "")

        return {"normalizedResumeProfile": resume_profile, "jobs": scored}

    async def _compute_resume_profile(self, resume_text, api_key, model):
        from .openrouter_scorer import build_resume_prompt, extract_json_object, normalize_resume_profile, call_openrouter

        if not api_key:
            return normalize_resume_profile({}, resume_text)

        system_prompt = (
            "You extract structured hiring information from resumes and job descriptions. "
            "Return only valid JSON. Never add facts not grounded in the text."
        )
        try:
            raw = call_openrouter(api_key, model, system_prompt, build_resume_prompt(resume_text))
            profile = extract_json_object(raw)
        except Exception:
            log.warning("LLM resume extraction failed, using rule-based profile")
            profile = {}

        return normalize_resume_profile(profile, resume_text)

    async def _normalize_job_profile_with_llm(self, job, api_key, model):
        from .openrouter_scorer import build_job_prompt, extract_json_object, normalize_job_profile, call_openrouter

        raw = call_openrouter(api_key, model,
            "You extract structured hiring information from resumes and job descriptions. Return only valid JSON. Never add facts not grounded in the text.",
            build_job_prompt(job))
        raw_profile = extract_json_object(raw)
        return normalize_job_profile(raw_profile, job)



    def _compute_score(self, resume_profile, job_profile, job, resume_text):
        weights = self.get_scoring_config()["weights"]

        required_skills = job_profile["required_skills"]
        preferred_skills = job_profile.get("preferred_skills", [])
        resume_skills = set(resume_profile.get("skills", []))
        matched_required = sorted(set(required_skills) & resume_skills) if isinstance(required_skills, list) else []
        missing_required = sorted(set(required_skills) - resume_skills) if isinstance(required_skills, list) else []
        matched_preferred = sorted(set(preferred_skills) & resume_skills)

        if required_skills:
            required_ratio = len(matched_required) / len(required_skills)
        elif preferred_skills:
            required_ratio = len(matched_preferred) / len(preferred_skills)
        else:
            required_ratio = 0.0

        skills_with_strength = resume_profile.get("skills_with_strength", {})
        if skills_with_strength and matched_required:
            weighted_matches = 0.0
            for skill in matched_required:
                strength = skills_with_strength.get(skill, "familiar")
                weight = STRENGTH_WEIGHTS.get(strength, 0.4)
                weighted_matches += weight
            skill_strength_factor = weighted_matches / len(matched_required)
        else:
            skill_strength_factor = 1.0

        preferred_ratio = len(matched_preferred) / len(preferred_skills) if preferred_skills else 0.0

        domains = set(resume_profile.get("domains", []))
        req_domains = job_profile.get("required_domains", [])
        matched_domains = sorted(set(req_domains) & domains)
        domain_ratio = len(matched_domains) / len(req_domains) if req_domains else 1.0

        role_family = self._normalize_role_key(job_profile["role_family"])
        candidate_roles, candidate_weights = self._parse_weighted_role_families(resume_profile.get("role_families", []))
        role_match = 0.0
        for i, cr in enumerate(candidate_roles):
            if cr == role_family:
                role_match = max(role_match, candidate_weights[i])
        if role_match == 0.0 and role_family != "unknown":
            fallback_roles = [cr for cr, cw in zip(candidate_roles, candidate_weights) if cw < 1.0]
            fallback_weights = [cw for cr, cw in zip(candidate_roles, candidate_weights) if cw < 1.0]
            if fallback_roles:
                role_match = self._compute_role_similarity(role_family, fallback_roles, fallback_weights)
                role_match = role_match ** 2

        secondary_roles = job_profile.get("secondary_role_families", [])
        if secondary_roles and role_match > 0:
            candidate_names = set(candidate_roles)
            secondary_matches = []
            for sr in secondary_roles:
                sr = self._normalize_role_key(sr)
                if sr in candidate_names:
                    idx = candidate_roles.index(sr)
                    secondary_matches.append(candidate_weights[idx])
                else:
                    sim = self._compute_role_similarity(sr, candidate_roles, candidate_weights)
                    secondary_matches.append(sim)
            role_match = (role_match * 2 + sum(secondary_matches)) / (2 + len(secondary_matches))

        management_match, management_notes = self._compute_management_match(
            resume_profile, job_profile
        )

        seniority_match = self._compute_seniority_match(
            resume_profile.get("candidate_seniority", "unknown"),
            job_profile["seniority"],
        )

        lexical_score = (
            required_ratio * 0.70 * skill_strength_factor
            + preferred_ratio * 0.20
            + domain_ratio * 0.10
        )

        embedding_score = self._compute_embedding_score(
            resume_text, job.get("description", ""), job_profile
        ) * role_match

        recency_score = self._compute_recency_score(job)

        qualification_analysis = self._analyze_qualifications(job_profile, job, resume_text)

        final_score = (
            lexical_score * weights["lexical"]
            + role_match * weights.get("role_match", 0.15)
            + embedding_score * weights["embedding"]
            + recency_score * weights["recency"]
        ) * seniority_match * management_match
        final_score = max(0.0, min(1.0, final_score))

        return {
            "score": round(final_score * 100),
            "required_skills_ratio": required_ratio,
            "preferred_skills_ratio": preferred_ratio,
            "domain_ratio": domain_ratio,
            "matched_required": matched_required,
            "matched_preferred": matched_preferred,
            "matched_domains": matched_domains,
            "missing_required": missing_required,
            "missing_preferred": sorted(set(preferred_skills) - resume_skills),
            "role_match": role_match,
            "skill_strength_factor": skill_strength_factor,
            "management_match": management_match,
            "seniority_match": seniority_match,
            "management_notes": management_notes,
            "penalty": qualification_analysis["total_penalty"],
            "embedding_score": embedding_score,
            "lexical_score": lexical_score,
            "qualification_analysis": qualification_analysis,
        }

    @staticmethod
    def _normalize_role_key(value):
        result = value.lower().strip().replace("_", "-").replace(" ", "-")
        for suffix in ("-engineering", "-engineer", "-developer", "-development"):
            if result.endswith(suffix):
                result = result[:-len(suffix)]
        return result

    def _parse_weighted_role_families(self, raw_list):
        roles = []
        weights = []
        for item in raw_list:
            if isinstance(item, dict):
                role = item.get("role", "")
                w = float(item.get("weight", 1.0))
            else:
                role = item
                w = 1.0
            role = self._normalize_role_key(role)
            if role:
                roles.append(role)
                weights.append(max(0.0, min(1.0, w)))
        return roles, weights

    def _compute_role_similarity(self, job_family, candidate_roles, candidate_weights=None):
        if not candidate_roles:
            return 0.0
        if candidate_weights is None:
            candidate_weights = [1.0] * len(candidate_roles)
        model = self._get_embedding_model()
        if job_family not in self._role_sim_cache:
            self._role_sim_cache[job_family] = model.encode(job_family, normalize_embeddings=True)
        job_emb = self._role_sim_cache[job_family]
        best = 0.0
        for i, cf in enumerate(candidate_roles):
            if cf not in self._role_sim_cache:
                self._role_sim_cache[cf] = model.encode(cf, normalize_embeddings=True)
            sim = float(self._role_sim_cache[cf] @ job_emb)
            weighted = sim * candidate_weights[i]
            if weighted > best:
                best = weighted
        return max(0.0, min(1.0, best))

    def _compute_management_match(self, resume, job):
        notes = []
        resume_mgmt = resume.get("management_type", "unclear")
        job_mgmt = job.get("management_type", "unclear")

        if job.get("people_management_required") and resume_mgmt not in ("people_manager", "executive_manager"):
            notes.append("job requires people management but resume looks IC-oriented")
            return 0.0, notes
        elif job_mgmt == "people_manager" and resume_mgmt not in ("people_manager", "executive_manager"):
            notes.append("job appears manager-oriented while resume looks more IC-oriented")
            return 0.2, notes
        elif job_mgmt == "ic_lead" and resume_mgmt == "ic":
            notes.append("job expects lead-level scope; resume shows less explicit leadership scope")
            return 0.7, notes
        return 1.0, notes

    def _compute_seniority_match(self, resume_level, job_level):
        r = SENIORITY_ORDER.get(resume_level, 2)
        j = SENIORITY_ORDER.get(job_level, 2)
        if r + 1 < j:
            return 0.25
        if j < r:
            return max(0.25, 1.0 - (r - j) * 0.30)
        return 1.0

    def _compute_embedding_score(self, resume_text, job_description, job_profile):
        if not resume_text or not job_description:
            return 0.5

        try:
            model = self._get_embedding_model()
            if resume_text != self._cached_resume_text:
                self._cached_resume_embedding = model.encode(
                    resume_text[:10000], normalize_embeddings=True
                )
                self._cached_resume_text = resume_text
            emb_job = model.encode(job_description[:10000], normalize_embeddings=True)
            sim = float(self._cached_resume_embedding @ emb_job)
            return max(0.0, min(1.0, sim))
        except Exception:
            log.warning("Embedding scoring failed, falling back")
            return 0.5

    def _compute_recency_score(self, job):
        cfg = self.get_scoring_config()["recency"]
        half_life_days = cfg.get("half_life_days", 30)
        max_bonus = cfg.get("max_bonus", 0.10)

        posted = job.get("postedDate", "")
        if not posted:
            desc = job.get("description", "")
            if desc:
                m = re.search(r"Posted\s*:\s*\w+\s+\d+,?\s*\d{4}", desc)
                if m:
                    posted = m.group(0)

        try:
            posted_date = self._parse_date(posted)
            if posted_date is None:
                return 0.0
            days_ago = (datetime.now(timezone.utc) - posted_date).days
            if days_ago < 0:
                return max_bonus
            return max_bonus * (0.5 ** (days_ago / half_life_days))
        except Exception:
            return 0.0

    def _parse_date(self, date_str):
        patterns = [
            r"Posted\s+(?:on\s+)?(\w+ \d+,?\s*\d{4})",
            r"(\w+ \d+,?\s*\d{4})",
            r"(\d{4}-\d{2}-\d{2})",
            r"Posted\s+(\d+)\s+(day|days|week|weeks)\s+ago",
        ]
        for pat in patterns:
            m = re.search(pat, str(date_str))
            if m:
                groups = m.groups()
                if groups[0].isdigit():
                    num = int(groups[0])
                    unit = groups[1]
                    if "day" in unit:
                        days = num
                    elif "week" in unit:
                        days = num * 7
                    else:
                        continue
                    from datetime import timedelta
                    return datetime.now(timezone.utc) - timedelta(days=days)
                else:
                    from dateutil import parser as dateparser
                    try:
                        return dateparser.parse(groups[0]).replace(tzinfo=timezone.utc)
                    except Exception:
                        pass
        return None

    def _analyze_qualifications(self, job_profile, job, resume_text):
        cfg = self.get_scoring_config()
        resume_lower = resume_text.lower()
        sections = self._parse_resume_sections(resume_text)

        required_skills = job_profile.get("required_skills", [])
        preferred_skills = job_profile.get("preferred_skills", [])
        unsupported_required = [s for s in required_skills if s.lower() not in resume_lower]
        unsupported_preferred = [s for s in preferred_skills if s.lower() not in resume_lower]

        required_named_penalty = min(
            len(unsupported_required) * cfg["named_required_tech_penalty_per_term"],
            cfg["named_required_tech_penalty_max"],
        )
        preferred_named_penalty = min(
            len(unsupported_preferred) * cfg["named_preferred_tech_penalty_per_term"],
            cfg["named_preferred_tech_penalty_max"],
        )

        description = job.get("description", "")
        required_bullets = job_profile.get("must_have_qualifications") or self._split_into_bullets(
            self._extract_required_qual_sections(description)
        )
        preferred_bullets = job_profile.get("preferred_qualifications") or self._split_into_bullets(
            self._extract_preferred_qual_sections(description)
        )

        required_analysis = self._score_bullets(
            resume_text,
            required_bullets,
            cfg["required_qualifications_penalty_per_bullet"],
            cfg["required_qualifications_penalty_max"],
            sections=sections,
        )
        preferred_analysis = self._score_bullets(
            resume_text,
            preferred_bullets,
            cfg["preferred_qualifications_penalty_per_bullet"],
            cfg["preferred_qualifications_penalty_max"],
            sections=sections,
        )

        required_penalty = min(
            cfg["required_qualifications_penalty_max"],
            required_analysis["weak_penalty"] + required_named_penalty,
        )
        preferred_penalty = min(
            cfg["preferred_qualifications_penalty_max"],
            preferred_analysis["weak_penalty"] + preferred_named_penalty,
        )

        return {
            "required": {
                **required_analysis,
                "unsupported_named_tech": unsupported_required,
                "named_tech_checked": required_skills,
                "named_tech_penalty": required_named_penalty,
                "applied_penalty": required_penalty,
            },
            "preferred": {
                **preferred_analysis,
                "unsupported_named_tech": unsupported_preferred,
                "named_tech_checked": preferred_skills,
                "named_tech_penalty": preferred_named_penalty,
                "applied_penalty": preferred_penalty,
            },
            "total_penalty": min(0.45, required_penalty + preferred_penalty),
        }

    def _extract_required_qual_sections(self, text):
        patterns = [
            r"(?:minimum|required|basic)\s*(?:qualifications|requirements|skills|experience)[:\s]*\n?(.*?)(?=\n\s*(?:preferred|desired|nice.to.have|bonus|additional|qualifications|about you|what we offer|benefits|apply|$)|\Z)",
            r"(?:what you(?:'ll)?\s*(?:need|bring|have)|you(?:'ll)?\s*(?:need|have|bring))[:\s]*\n?(.*?)(?=\n\s*(?:preferred|nice.to.have|bonus|about you|what we offer|benefits)|\Z)",
        ]
        text_lower = text.lower()
        for pat in patterns:
            m = re.search(pat, text_lower, re.DOTALL | re.IGNORECASE)
            if m:
                section = m.group(1).strip()
                if len(section) > 30:
                    return section
        return ""

    def _extract_preferred_qual_sections(self, text):
        patterns = [
            r"(?:preferred|desired|nice[\s-]*to[\s-]*have|bonus)\s*(?:qualifications|requirements|skills|experience)?[:\s]*\n?(.*?)(?=\n\s*(?:benefits|what we offer|about you|apply|additional information|$)|\Z)",
        ]
        text_lower = text.lower()
        for pat in patterns:
            m = re.search(pat, text_lower, re.DOTALL | re.IGNORECASE)
            if m:
                section = m.group(1).strip()
                if len(section) > 30:
                    return section
        return ""

    def _split_into_bullets(self, text):
        if not text:
            return []
        bullets = re.split(r'\n\s*[-•*]\s*|\n\s*\d+\.\s*|\n(?=\s{2,}[A-Z])', text)
        return [b.strip() for b in bullets if len(b.strip()) > 15]

    @staticmethod
    def _parse_resume_sections(text):
        sections = {}
        header_pattern = re.compile(
            r"^\s*(" + "|".join(_SECTION_HEADERS) + r")\s*$",
            re.MULTILINE | re.IGNORECASE,
        )
        matches = list(header_pattern.finditer(text))
        if not matches:
            return sections

        prev_end = 0
        prev_name = "summary"
        for m in matches:
            chunk = text[prev_end : m.start()].strip()
            if chunk:
                sections[prev_name] = chunk
            prev_end = m.end()
            prev_name = m.group(1).lower().replace(" ", "_").replace("-", "_")

        tail = text[prev_end:].strip()
        if tail:
            sections[prev_name] = tail
        return sections

    @staticmethod
    def _route_bullet_to_section(bullet, sections):
        if not sections:
            return None
        bullet_lower = bullet.lower()
        if any(kw in bullet_lower for kw in _EDUCATION_KEYWORDS):
            edu = sections.get("education")
            if edu:
                return edu
        return None

    def _compute_semantic_similarity(self, text_a, text_b):
        if not text_a or not text_b:
            return 0.0
        try:
            model = self._get_embedding_model()
            emb_a = model.encode(text_a[:5000], normalize_embeddings=True)
            emb_b = model.encode(text_b[:5000], normalize_embeddings=True)
            return max(0.0, min(1.0, float(emb_a @ emb_b)))
        except Exception:
            return 0.5

    def _score_bullets(self, resume_text, bullets, per_bullet_penalty, max_penalty, sections=None):
        if not bullets:
            return {
                "coverage_ratio": None,
                "best_matches": [],
                "weakest_matches": [],
                "penalty_triggering_matches": [],
                "weak_penalty": 0.0,
            }

        model = self._get_embedding_model()
        cache = {}
        def _get_emb(text):
            if text not in cache:
                cache[text] = model.encode(text[:5000], normalize_embeddings=True)
            return cache[text]

        full_emb = _get_emb(resume_text)
        edu_emb = None
        if sections:
            edu = sections.get("education")
            if edu:
                edu_emb = _get_emb(edu)

        scored = []
        weak_matches = []
        for bullet in bullets:
            if edu_emb is not None and any(kw in bullet.lower() for kw in _EDUCATION_KEYWORDS):
                emb_a = edu_emb
                section_used = "education"
            else:
                emb_a = full_emb
                section_used = "full"
            emb_b = _get_emb(bullet)
            sim = float(emb_a @ emb_b)
            entry = {"bullet": bullet, "score": max(0.0, min(1.0, sim)), "section_used": section_used}
            scored.append(entry)
            if sim < 0.55:
                weak_matches.append(entry)

        scored.sort(key=lambda item: item["score"], reverse=True)
        weak_sorted = sorted(scored, key=lambda item: item["score"])
        weak_penalty = min(len(weak_matches) * per_bullet_penalty, max_penalty)

        return {
            "coverage_ratio": sum(item["score"] for item in scored) / len(scored),
            "best_matches": scored[:3],
            "weakest_matches": weak_sorted[:3],
            "penalty_triggering_matches": sorted(weak_matches, key=lambda item: item["score"])[:3],
            "weak_penalty": weak_penalty,
        }

    def _get_embedding_model(self):
        if self._embedding_model is not None:
            return self._embedding_model

        model_id = self.get_scoring_config()["embeddingModel"]
        log.info("Loading embedding model: %s", model_id)
        self._embedding_model = SentenceTransformer(model_id)
        return self._embedding_model

    @staticmethod
    def _build_reasoning(job_profile, score_data):
        qual = score_data.get("qualification_analysis", {})
        required = qual.get("required", {})
        preferred = qual.get("preferred", {})
        role_match = score_data.get("role_match", 0)
        lines = [
            f"Normalized role: {job_profile['role_family']} / {job_profile['seniority']} / {job_profile['management_type']}. Role match: {role_match:.2f}.",
            f"Required skill match: {len(score_data['matched_required'])}/{len(job_profile['required_skills'])}.",
        ]

        secondary_roles = job_profile.get("secondary_role_families", [])
        if secondary_roles:
            lines.append(f"  Secondary roles: {', '.join(secondary_roles)}.")
        if job_profile.get("preferred_skills"):
            lines.append(
                f"Preferred skill match: {len(score_data['matched_preferred'])}/{len(job_profile['preferred_skills'])}."
            )
        if score_data["matched_required"]:
            lines.append("Matched required skills: " + ", ".join(score_data["matched_required"]) + ".")
        if score_data["missing_required"]:
            lines.append("Missing required skills: " + ", ".join(score_data["missing_required"][:8]) + ".")
        if score_data.get("missing_preferred"):
            lines.append("Missing preferred skills: " + ", ".join(score_data["missing_preferred"][:6]) + ".")
        if score_data.get("management_notes"):
            for note in score_data["management_notes"]:
                lines.append(note[:1].upper() + note[1:] + ".")
        if required.get("coverage_ratio") is not None:
            lines.append(
                f"Required qualification coverage: {required['coverage_ratio']:.0%}. "
                f"Penalty: {required.get('applied_penalty', 0):.2f} "
                f"(weak bullets {required.get('weak_penalty', 0):.2f}, skill gaps {required.get('named_tech_penalty', 0):.2f})."
            )
            best = required.get("best_matches", [])
            if best:
                lines.append(
                    "Best required matches: " + " | ".join(
                        f"{item['score']:.0%}: {item['bullet'][:120]}" for item in best
                    ) + "."
                )
            unsupported_required = required.get("unsupported_named_tech", [])
            if unsupported_required:
                lines.append(
                    "Missing required skills: "
                    + ", ".join(unsupported_required)
                    + f" ({len(required.get('named_tech_checked', []))} checked)."
                )
        if preferred.get("coverage_ratio") is not None:
            lines.append(
                f"Preferred qualification coverage: {preferred['coverage_ratio']:.0%}. "
                f"Penalty: {preferred.get('applied_penalty', 0):.2f} "
                f"(weak bullets {preferred.get('weak_penalty', 0):.2f}, skill gaps {preferred.get('named_tech_penalty', 0):.2f})."
            )
            unsupported_preferred = preferred.get("unsupported_named_tech", [])
            if unsupported_preferred:
                lines.append(
                    "Missing preferred skills: "
                    + ", ".join(unsupported_preferred)
                    + f" ({len(preferred.get('named_tech_checked', []))} checked)."
                )
        lines.append(f"Lexical: {score_data.get('lexical_score', 0):.2f}, Embedding: {score_data.get('embedding_score', 0):.2f}, Required: {score_data.get('required_skills_ratio', 0):.2f}")
        return "\n".join(lines)
