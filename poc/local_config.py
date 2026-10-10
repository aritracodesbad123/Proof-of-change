"""Machine-local settings that must not live in the public repo (paths of private data on one machine).

Read from ops/local.json (git-ignored) and overridden by environment variables. Every key is optional:
  libraries_file    tracked-libraries CSV                      env POC_LIBRARIES_FILE
  chosen_prs_dir    folder of <date>.md files naming PRs to test env POC_CHOSEN_PRS_DIR
  verification_dir  folder of <date>/verification.jsonl          env POC_VERIFICATION_DIR
  golden_status     latest known-answer replay status (JSON)     env BR_GOLDEN_STATUS
  research_dir      folder with the golden-record run artifacts  env BR_RESEARCH_DIR
"""
from __future__ import annotations

import json
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
LOCAL_FILE = REPO_ROOT / "ops" / "local.json"
ENV = {"libraries_file": "POC_LIBRARIES_FILE", "chosen_prs_dir": "POC_CHOSEN_PRS_DIR",
       "verification_dir": "POC_VERIFICATION_DIR", "golden_status": "BR_GOLDEN_STATUS", "research_dir": "BR_RESEARCH_DIR"}


def get(key: str, default: str | None = None) -> str | None:
    """Environment variable first (an empty value means 'none'), then ops/local.json, then default."""
    env = ENV.get(key)
    if env and env in os.environ:
        return os.environ[env] or None
    try:
        val = json.loads(LOCAL_FILE.read_text()).get(key)
    except (OSError, ValueError):
        val = None
    return val or default
