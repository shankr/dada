#!/usr/bin/env python3

import os
from datetime import datetime
from pathlib import Path

import yaml


def build_run_label(timezone="America/Los_Angeles"):
    os.environ["TZ"] = timezone
    try:
        # Handle timezone on non-macOS
        if hasattr(time, "tzset"):
            time.tzset()
    except Exception:
        pass

    now = datetime.now()
    return now.strftime("%Y-%m-%d-%H%M")


def main():
    timezone = os.environ.get("JOB_MATCHER_TIMEZONE", "America/Los_Angeles")
    run_label = build_run_label(timezone)

    config_path = Path(__file__).parent.parent / "config" / "jobs.yaml"
    with open(config_path) as f:
        config = yaml.safe_load(f)

    resume_path = Path(config["resume_path"]).resolve()
    base_output_path = Path(config["output_path"]).resolve()
    output_dir = base_output_path.parent / run_label
    output_txt = output_dir / base_output_path.name
    output_json = output_txt.with_suffix(".json")
    cache_db = Path(config.get("ats_cache_db_path", "./output/ats-cache.sqlite")).resolve()

    print(f"JOB_MATCHER_RUN_LABEL={run_label}", flush=True)
    print(f"JOB_MATCHER_RESUME_PATH={resume_path}", flush=True)
    print(f"JOB_MATCHER_OUTPUT_TXT={output_txt}", flush=True)
    print(f"JOB_MATCHER_OUTPUT_JSON={output_json}", flush=True)
    print(f"JOB_MATCHER_CACHE_DB={cache_db}", flush=True)


if __name__ == "__main__":
    main()
