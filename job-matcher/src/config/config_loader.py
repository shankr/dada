import os
import re
import yaml
from pathlib import Path


class ConfigLoader:
    REQUIRED_FIELDS = ["resume_path", "output_path", "job_boards"]

    @classmethod
    def load(cls, config_path=None):
        if config_path is None:
            config_path = Path(__file__).parent.parent.parent / "config" / "jobs.yaml"
        config_path = Path(config_path).resolve()

        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")

        with open(config_path) as f:
            config = yaml.safe_load(f)

        config = cls._process_env_vars(config)
        config = cls._apply_env_overrides(config)
        cls._validate(config)

        config["resume_path"] = str(Path(config["resume_path"]).resolve())
        config["output_path"] = str(Path(config["output_path"]).resolve())
        config["ats_cache_db_path"] = str(
            Path(config.get("ats_cache_db_path", "./output/ats-cache.sqlite")).resolve()
        )

        return config

    @classmethod
    def _process_env_vars(cls, obj):
        if isinstance(obj, str):
            def replacer(m):
                env_var = m.group(1)
                value = os.environ.get(env_var)
                if value is None:
                    print(f"Warning: Environment variable {env_var} is not set")
                    return m.group(0)
                return value
            return re.sub(r"\$\{([^}]+)\}", replacer, obj)
        if isinstance(obj, list):
            return [cls._process_env_vars(item) for item in obj]
        if isinstance(obj, dict):
            return {k: cls._process_env_vars(v) for k, v in obj.items()}
        return obj

    @classmethod
    def _validate(cls, config):
        for field in cls.REQUIRED_FIELDS:
            if not config.get(field):
                raise ValueError(f"Missing required configuration field: {field}")

        boards = config.get("job_boards", [])
        if not isinstance(boards, list) or len(boards) == 0:
            raise ValueError("Configuration must include at least one job_board")

        llm = config.get("llm", {})
        if llm.get("provider") and llm.get("provider") != "openrouter":
            raise ValueError(f"Unsupported llm.provider: {llm['provider']}. Supported: openrouter")
        if llm.get("provider") == "openrouter":
            api_key = llm.get("api_key") or os.environ.get("OPENROUTER_KEY")
            if not api_key:
                raise ValueError("OpenRouter API key required. Set llm.api_key or OPENROUTER_KEY env var.")

        for board in boards:
            if not board.get("name") or not board.get("type") or not board.get("url"):
                raise ValueError("Each job board must have name, type, and url")

    @classmethod
    def _apply_env_overrides(cls, config):
        result = dict(config)
        result["scoring"] = dict(config.get("scoring", {}))

        force = os.environ.get("JOB_MATCHER_FORCE_RECOMPUTE", "").strip().lower()
        if force:
            result["scoring"]["force_recompute"] = force in ("1", "true", "yes", "on")

        if os.environ.get("JOB_MATCHER_OUTPUT_PATH"):
            result["output_path"] = os.environ["JOB_MATCHER_OUTPUT_PATH"]

        return result
