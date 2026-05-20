import json
import logging
import math
import os
import re
from datetime import datetime, timezone

from sentence_transformers import SentenceTransformer

log = logging.getLogger(__name__)

ROLE_FAMILIES = [
    "backend", "frontend", "full-stack", "mobile", "ios", "android",
    "machine-learning", "data", "data-platform", "analytics", "security",
    "infrastructure", "platform", "devops", "sre", "cloud", "qa",
    "management", "product-engineering",
]

SENIORITY_LEVELS = [
    "intern", "junior", "mid", "senior", "staff", "principal",
    "manager", "senior-manager", "director", "unknown",
]

MANAGEMENT_TYPES = ["ic", "ic_lead", "people_manager", "executive_manager", "unclear"]

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
    "mentoring", "people management", "architecture", "product sense",
    "html", "css", "tailwind", "bootstrap", "springboot",
    "helm", "istio", "argo", "argocd", "crossplane", "kubevirt",
    "pulumi", "cloudinit", "podman", "rancher", "cilium", "kubebuilder",
    "knative", "openstack", "cassandra", "dynamodb", "redshift",
    "opensearch", "hive", "presto", "trino", "databricks", "kafka",
    "flink", "flume", "sqs", "sns", "pubsub", "rabbitmq",
    "keras", "scikitlearn", "xgboost", "transformers", "huggingface",
    "sentencetransformers", "langchain", "langgraph", "llamaindex",
    "autogen", "crewai", "mcp", "modelcontextprotocol",
    "vectorsearch", "vectordb", "embedding", "embeddings",
    "finetuning", "inference", "promptengineering", "agents", "agentic",
    "datadog", "splunk", "newrelic", "opentelemetry",
    "playwright", "pytest", "jest", "cypress", "junit", "selenium",
    "openai", "openrouter", "anthropic", "claude", "gemini",
    "mlflow", "kubeflow", "vertex ai", "sagemaker",
    "django", "flask", "fastapi", "express", "spring", "nextjs", "nuxt",
    "tailwindcss", "shadcn", "radix", "prisma", "drizzle", "typeorm",
    "postgres", "mysql", "mariadb", "sqlite", "cockroachdb", "tidb",
    "couchbase", "neo4j", "arangodb", "influxdb", "timescaledb",
    "nats", "pulsar", "rocketmq", "zeromq", "millvus", "pinecone",
    "weaviate", "qdrant", "chromadb", "redisearch",
    "istio", "linkerd", "consul", "vault", "boundary",
    "sops", "age", "gpg", "tink", "keycloak", "auth0", "fusedav",
]

TECH_ALIASES = {
    "js": "javascript",
    "ts": "typescript",
    "py": "python",
    "golang": "go",
    "react.js": "react",
    "reactjs": "react",
    "vue.js": "vue",
    "vuejs": "vue",
    "node.js": "node",
    "nodejs": "node",
    "spring-boot": "springboot",
    "k8s": "kubernetes",
    "postgresql": "postgres",
    "mongo": "mongodb",
    "elastic": "elasticsearch",
    "github-actions": "github actions",
    "ci/cd": "ci",
    "machinelearning": "machine learning",
    "machine-learning": "machine learning",
    "genai": "ai",
    "llms": "llm",
    "llmops": "llm",
    "scikit-learn": "scikitlearn",
    "sklearn": "scikitlearn",
    "tf": "tensorflow",
    "tensor-flow": "tensorflow",
    "hugging-face": "huggingface",
    "sentence-transformers": "sentencetransformers",
    "lang-chain": "langchain",
    "lang-graph": "langgraph",
    "llama-index": "llamaindex",
    "model-context-protocol": "modelcontextprotocol",
    "vector-db": "vectordb",
    "vector-database": "vectordb",
    "vectorstore": "vectordb",
    "cloud-init": "cloudinit",
    "argo-cd": "argocd",
}

PHRASE_NORMALIZATIONS = [
    (r"\bHugging Face\b", "huggingface"),
    (r"\bsentence transformers\b", "sentencetransformers"),
    (r"\bmodel context protocol\b", "modelcontextprotocol"),
    (r"\bvector database\b", "vectordb"),
    (r"\bvector db\b", "vectordb"),
    (r"\bmachine learning\b", "machinelearning"),
    (r"\bopen ai\b", "openai"),
    (r"\bartificial intelligence\b", "ai"),
]

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from",
    "has", "he", "in", "is", "it", "its", "of", "on", "that", "the",
    "to", "was", "were", "will", "with", "you", "your", "we", "our",
    "they", "their", "i", "me", "my", "this", "these", "those", "or",
    "but", "if", "then", "than", "also", "not", "no", "yes", "so",
    "such", "about", "across", "after", "before", "between", "both",
    "during", "each", "few", "more", "most", "other", "over", "under",
    "up", "down", "out", "into", "through", "using", "use", "used",
    "uses", "based", "within", "per", "etc",
}

SENIORITY_ORDER = {
    "intern": 0, "junior": 1, "mid": 2, "senior": 3,
    "staff": 4, "principal": 5, "manager": 4,
    "senior-manager": 5, "director": 6, "unknown": 2,
}


class ATSScorer:
    def __init__(self, config, cache_db):
        self.config = config
        self.cache_db = cache_db
        self._embedding_model = None
        self._scoring_cfg = None

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

        scored = []
        total = len(jobs)

        resume_profile = await self._compute_resume_profile(resume_text, api_key, model)

        for idx, job in enumerate(jobs):
            if on_progress:
                on_progress(job, idx, total)

            cached = None if force_recompute else self.cache_db.get_by_url(job.get("url"))
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
                continue

            job_profile = await self._normalize_job_profile_with_llm(job, api_key, model)

            score_data = self._compute_score(resume_profile, job_profile, job, resume_text)
            reasoning = self._build_reasoning(job_profile, score_data)

            job_data = dict(job)
            job_data["normalizedJob"] = job_profile
            job_data["scoreBreakdown"] = {
                "requiredSkillsRatio": score_data["required_skills_ratio"],
                "preferredSkillsRatio": score_data["preferred_skills_ratio"],
                "domainMatch": score_data["domain_ratio"],
                "roleMatch": score_data["role_match"],
                "managementMatch": score_data["management_match"],
                "seniorityMatch": score_data["seniority_match"],
                "matchedRequired": score_data["matched_required"],
                "matchedPreferred": score_data["matched_preferred"],
                "matchedDomains": score_data["matched_domains"],
                "missingRequired": score_data["missing_required"],
                "missingPreferred": score_data["missing_preferred"],
                "managementNotes": score_data.get("management_notes", []),
                "explicitMatchRatio": score_data.get("explicit_match_ratio"),
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

        if api_key:
            try:
                raw = call_openrouter(api_key, model,
                    "You extract structured hiring information from resumes and job descriptions. Return only valid JSON. Never add facts not grounded in the text.",
                    build_job_prompt(job))
                raw_profile = extract_json_object(raw)
                return normalize_job_profile(raw_profile, job)
            except Exception:
                log.warning("LLM job extraction failed for %s, using rule-based", job.get("title", ""))

        return self._normalize_job_profile(job)

    def _normalize_job_profile(self, job):
        text = f"{job.get('title', '')} {job.get('description', '')}"
        description = job.get("description", "")
        required_section = self._extract_required_qual_sections(description)
        preferred_section = self._extract_preferred_qual_sections(description)
        management_type = self._normalize_management_type("unclear", text)
        people_management_required = (
            management_type in ("people_manager", "executive_manager")
            or any(term in text.lower() for term in ("people management", "engineering manager", "direct reports"))
        )
        return {
            "role_family": self._normalize_role_family("unknown", text),
            "seniority": self._normalize_seniority("unknown", text),
            "management_type": management_type,
            "people_management_required": people_management_required,
            "required_skills": self._normalize_skill_list(required_section or description),
            "preferred_skills": self._normalize_skill_list(preferred_section),
            "required_domains": [],
            "preferred_domains": [],
            "must_have_qualifications": self._split_into_bullets(required_section),
            "preferred_qualifications": self._split_into_bullets(preferred_section),
            "hard_gates": [],
            "work_mode": "unknown",
            "location_constraints": [],
            "evidence": [],
        }

    def _normalize_role_family(self, value, source_text):
        text = str(value).lower().strip()
        if text in ROLE_FAMILIES:
            return text
        haystack = f"{source_text} {text}".lower()
        role_keywords = {
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
        for family, keywords in role_keywords.items():
            if any(kw in haystack for kw in keywords):
                return family
        return "unknown"

    def _normalize_seniority(self, value, source_text):
        text = str(value).lower().strip().replace(" ", "-")
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
            if any(w in haystack for w in words):
                return level
        return "unknown"

    def _normalize_management_type(self, value, source_text):
        text = str(value).lower().strip().replace(" ", "_")
        alias_map = {
            "ic": "ic", "individual_contributor": "ic",
            "tech_lead": "ic_lead", "team_lead": "ic_lead",
            "lead": "ic_lead", "ic_lead": "ic_lead",
            "people_manager": "people_manager",
            "manager_of_people": "people_manager",
            "executive_manager": "executive_manager",
            "unclear": "unclear",
        }
        if text in alias_map:
            return alias_map[text]
        haystack = f"{source_text} {text}".lower()
        if any(t in haystack for t in ["manage engineers", "people manager", "engineering manager", "direct reports"]):
            return "people_manager"
        if any(t in haystack for t in ["mentor engineers", "technical lead", "lead cross-functional"]):
            return "ic_lead"
        if "manager" in haystack or "director" in haystack:
            return "people_manager"
        return "ic"

    def _normalize_skill_list(self, source_text):
        items = set()
        haystack = source_text.lower()

        text = haystack
        for pat, repl in PHRASE_NORMALIZATIONS:
            text = re.sub(pat, repl, text)
        haystack = text

        for skill in SKILL_ONTOLOGY:
            normalized_skill = skill.lower()
            alias = TECH_ALIASES.get(normalized_skill, normalized_skill)
            if alias in haystack:
                items.add(skill)
            elif normalized_skill in haystack:
                items.add(skill)

        return sorted(items)

    def _normalize_text_for_matching(self, text):
        normalized = (text or "").lower()
        for pat, repl in PHRASE_NORMALIZATIONS:
            normalized = re.sub(pat, repl, normalized)
        return normalized

    def _compute_explicit_match_ratio(self, resume_text, job):
        text_lower = resume_text.lower()
        description = (job.get("description") or "").lower()
        title = (job.get("title") or "").lower()
        haystack = f"{text_lower}"

        for pat, repl in PHRASE_NORMALIZATIONS:
            description = re.sub(pat, repl, description)

        words = re.findall(r"[a-z0-9+#_.-]+", description)
        raw_skills = set()
        for w in words:
            alias = TECH_ALIASES.get(w, w)
            for skill in SKILL_ONTOLOGY:
                if skill.lower() == alias or alias == skill.lower():
                    raw_skills.add(skill)
                    break
            else:
                if w in SKILL_ONTOLOGY:
                    raw_skills.add(w)

        if not raw_skills:
            return 1.0

        matched = 0
        for skill in raw_skills:
            if skill.lower() in haystack:
                matched += 1
            else:
                alias = TECH_ALIASES.get(skill.lower())
                if alias and alias in haystack:
                    matched += 1

        return matched / len(raw_skills)

    def _compute_score(self, resume_profile, job_profile, job, resume_text):
        weights = self.get_scoring_config()["weights"]

        required_skills = job_profile["required_skills"]
        resume_skills = set(resume_profile.get("skills", []))
        matched_required = sorted(set(required_skills) & resume_skills) if isinstance(required_skills, list) else []
        missing_required = sorted(set(required_skills) - resume_skills) if isinstance(required_skills, list) else []

        required_ratio = len(matched_required) / len(required_skills) if required_skills else 1.0

        preferred_skills = job_profile.get("preferred_skills", [])
        matched_preferred = sorted(set(preferred_skills) & resume_skills)
        preferred_ratio = len(matched_preferred) / len(preferred_skills) if preferred_skills else 1.0

        domains = set(resume_profile.get("domains", []))
        req_domains = job_profile.get("required_domains", [])
        matched_domains = sorted(set(req_domains) & domains)
        domain_ratio = len(matched_domains) / len(req_domains) if req_domains else 1.0

        role_match = 1.0 if (
            job_profile["role_family"] == "unknown"
            or job_profile["role_family"] in set(resume_profile.get("role_families", []))
        ) else 0.0

        management_match, management_notes = self._compute_management_match(
            resume_profile, job_profile
        )

        seniority_match = self._compute_seniority_match(
            resume_profile.get("candidate_seniority", "unknown"),
            job_profile["seniority"],
        )

        explicit_ratio = self._compute_explicit_match_ratio(resume_text, job)

        lexical_score = (
            required_ratio * 0.35
            + explicit_ratio * 0.25
            + preferred_ratio * 0.10
            + role_match * 0.10
            + management_match * 0.10
            + seniority_match * 0.05
            + domain_ratio * 0.05
        )

        embedding_score = self._compute_embedding_score(
            resume_text, job.get("description", ""), job_profile
        )

        recency_score = self._compute_recency_score(job)

        qualification_analysis = self._analyze_qualifications(job_profile, job, resume_text)
        penalty = qualification_analysis["total_penalty"]

        final_score = (
            lexical_score * weights["lexical"]
            + embedding_score * weights["embedding"]
            + recency_score * weights["recency"]
        ) - penalty
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
            "management_match": management_match,
            "seniority_match": seniority_match,
            "management_notes": management_notes,
            "penalty": penalty,
            "embedding_score": embedding_score,
            "lexical_score": lexical_score,
            "explicit_match_ratio": explicit_ratio,
            "qualification_analysis": qualification_analysis,
        }

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
        return 1.0

    def _compute_embedding_score(self, resume_text, job_description, job_profile):
        if not resume_text or not job_description:
            return 0.5

        try:
            model = self._get_embedding_model()
            emb_resume = model.encode(resume_text[:10000], normalize_embeddings=True)
            emb_job = model.encode(job_description[:10000], normalize_embeddings=True)
            sim = float(emb_resume @ emb_job)
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
            return 0.0

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
        )
        preferred_analysis = self._score_bullets(
            resume_text,
            preferred_bullets,
            cfg["preferred_qualifications_penalty_per_bullet"],
            cfg["preferred_qualifications_penalty_max"],
        )

        required_named = self._compute_named_tech_penalty(
            required_bullets,
            resume_text,
            cfg["named_required_tech_match_threshold"],
            cfg["named_required_tech_penalty_per_term"],
            cfg["named_required_tech_penalty_max"],
        )
        preferred_named = self._compute_named_tech_penalty(
            preferred_bullets,
            resume_text,
            cfg["named_required_tech_match_threshold"],
            cfg["named_preferred_tech_penalty_per_term"],
            cfg["named_preferred_tech_penalty_max"],
        )

        required_penalty = min(
            cfg["required_qualifications_penalty_max"],
            required_analysis["weak_penalty"] + required_named["penalty"],
        )
        preferred_penalty = min(
            cfg["preferred_qualifications_penalty_max"],
            preferred_analysis["weak_penalty"] + preferred_named["penalty"],
        )

        return {
            "required": {
                **required_analysis,
                "unsupported_named_tech": required_named["unsupported_terms"],
                "named_tech_checked": required_named["checked_terms"],
                "named_tech_penalty": required_named["penalty"],
                "applied_penalty": required_penalty,
            },
            "preferred": {
                **preferred_analysis,
                "unsupported_named_tech": preferred_named["unsupported_terms"],
                "named_tech_checked": preferred_named["checked_terms"],
                "named_tech_penalty": preferred_named["penalty"],
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

    def _compute_named_tech_penalty(self, bullets, resume_text, threshold, per_term, max_penalty):
        tech_terms = self._extract_named_tech_terms("\n".join(bullets))
        if not tech_terms:
            return {"penalty": 0.0, "unsupported_terms": [], "checked_terms": []}

        unsupported_terms = []
        for term in tech_terms:
            if not self._resume_semantically_supports_term(resume_text, term, threshold):
                unsupported_terms.append(term)

        return {
            "penalty": min(len(unsupported_terms) * per_term, max_penalty),
            "unsupported_terms": unsupported_terms,
            "checked_terms": tech_terms,
        }

    def _extract_named_tech_terms(self, text):
        text_lower = text.lower()
        for pat, repl in PHRASE_NORMALIZATIONS:
            text_lower = re.sub(pat, repl, text_lower)
        words = re.findall(r"[a-z0-9+#_.-]+", text_lower)
        found = []
        for w in words:
            alias = TECH_ALIASES.get(w, w)
            for skill in SKILL_ONTOLOGY:
                if skill.lower() == alias or alias == skill.lower():
                    found.append(skill)
                    break
            else:
                if w in SKILL_ONTOLOGY:
                    found.append(w)
        return sorted(set(found))

    def _resume_semantically_supports_term(self, resume_text, term, threshold):
        if not resume_text or not term:
            return False

        normalized_resume = self._normalize_text_for_matching(resume_text)
        normalized_term = self._normalize_text_for_matching(term)
        aliases = {normalized_term}
        if normalized_term in TECH_ALIASES:
            aliases.add(TECH_ALIASES[normalized_term])
        for alias_key, alias_value in TECH_ALIASES.items():
            if alias_value == normalized_term:
                aliases.add(alias_key)
        for alias in aliases:
            if alias and alias in normalized_resume:
                return True

        resume_units = self._split_resume_into_semantic_units(resume_text)
        supported = False
        for unit in resume_units:
            sim = self._compute_semantic_similarity(unit, term)
            if sim >= threshold:
                supported = True
                break
        return supported

    def _split_resume_into_semantic_units(self, resume_text):
        units = re.split(r'\n\s*\n', resume_text)
        return [u.strip() for u in units if len(u.strip()) > 20]

    def _score_bullets(self, resume_text, bullets, per_bullet_penalty, max_penalty):
        if not bullets:
            return {
                "coverage_ratio": None,
                "best_matches": [],
                "weakest_matches": [],
                "penalty_triggering_matches": [],
                "weak_penalty": 0.0,
            }

        scored = []
        weak_matches = []
        for bullet in bullets:
            sim = self._compute_semantic_similarity(resume_text, bullet)
            entry = {"bullet": bullet, "score": sim}
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
        lines = [
            f"Normalized role: {job_profile['role_family']} / {job_profile['seniority']} / {job_profile['management_type']}.",
            f"Required skill match: {len(score_data['matched_required'])}/{len(job_profile['required_skills'])}.",
        ]
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
                f"(weak bullets {required.get('weak_penalty', 0):.2f}, named tech {required.get('named_tech_penalty', 0):.2f})."
            )
            best = required.get("best_matches", [])
            if best:
                lines.append(
                    "Best required matches: " + " | ".join(
                        f"{item['score']:.0%}: {item['bullet'][:120]}" for item in best
                    ) + "."
                )
            weakest = required.get("weakest_matches", [])
            if weakest:
                lines.append(
                    "Weakest required matches: " + " | ".join(
                        f"{item['score']:.0%}: {item['bullet'][:120]}" for item in weakest
                    ) + "."
                )
            penalty_hits = required.get("penalty_triggering_matches", [])
            if penalty_hits:
                lines.append(
                    "Penalty-triggering required gaps: " + " | ".join(
                        f"{item['score']:.0%}: {item['bullet'][:120]}" for item in penalty_hits
                    ) + "."
                )
            unsupported_required = required.get("unsupported_named_tech", [])
            lines.append(
                "Unsupported named required tech: "
                + (", ".join(unsupported_required) if unsupported_required else "none")
                + f" ({len(required.get('named_tech_checked', []))} checked)."
            )
        if preferred.get("coverage_ratio") is not None:
            lines.append(
                f"Preferred qualification coverage: {preferred['coverage_ratio']:.0%}. "
                f"Penalty: {preferred.get('applied_penalty', 0):.2f} "
                f"(weak bullets {preferred.get('weak_penalty', 0):.2f}, named tech {preferred.get('named_tech_penalty', 0):.2f})."
            )
            best_pref = preferred.get("best_matches", [])
            if best_pref:
                lines.append(
                    "Best preferred matches: " + " | ".join(
                        f"{item['score']:.0%}: {item['bullet'][:120]}" for item in best_pref
                    ) + "."
                )
            weak_pref = preferred.get("weakest_matches", [])
            if weak_pref:
                lines.append(
                    "Weakest preferred matches: " + " | ".join(
                        f"{item['score']:.0%}: {item['bullet'][:120]}" for item in weak_pref
                    ) + "."
                )
            penalty_pref = preferred.get("penalty_triggering_matches", [])
            if penalty_pref:
                lines.append(
                    "Penalty-triggering preferred gaps: " + " | ".join(
                        f"{item['score']:.0%}: {item['bullet'][:120]}" for item in penalty_pref
                    ) + "."
                )
            unsupported_preferred = preferred.get("unsupported_named_tech", [])
            lines.append(
                "Unsupported named preferred tech: "
                + (", ".join(unsupported_preferred) if unsupported_preferred else "none")
                + f" ({len(preferred.get('named_tech_checked', []))} checked)."
            )
        lines.append(f"Explicit term match: {score_data.get('explicit_match_ratio', 0):.0%}.")
        lines.append(f"Lexical: {score_data.get('lexical_score', 0):.2f}, Embedding: {score_data.get('embedding_score', 0):.2f}, Penalty: {score_data.get('penalty', 0):.2f}")
        return "\n".join(lines)
