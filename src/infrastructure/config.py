from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, Field


REPO_ROOT = Path(__file__).resolve().parents[2]
DATASET_DIR = REPO_ROOT / "dataset"
OUTPUT_PATH = REPO_ROOT / "output.csv"
CACHE_DIR = REPO_ROOT / ".cache"
EVALUATION_DIR = REPO_ROOT / "evaluation"


class Settings(BaseModel):
    """Runtime settings loaded from environment variables only."""

    repo_root: Path = REPO_ROOT
    dataset_dir: Path = DATASET_DIR
    output_path: Path = OUTPUT_PATH
    cache_dir: Path = CACHE_DIR
    evaluation_dir: Path = EVALUATION_DIR

    llm_api_key: str = ""
    text_model: str = ""
    image_model: str = ""
    vision_fallback_model: str = "inclusionai/ling-3.0-flash-vl:free"
    llm_base_url: str = "https://openrouter.ai/api/v1"
    llm_timeout_seconds: float = 90.0
    llm_max_retries: int = 4
    use_llm: bool = False
    forecast_days: int = 90
    batch_size: int = 250


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    load_dotenv(REPO_ROOT / ".env", override=False)
    shared_model = (
        os.getenv("model")
        or os.getenv("MODEL")
        or ""
    ).strip()
    text_model = (
        os.getenv("tex_model")
        or os.getenv("text_model")
        or os.getenv("TEXT_MODEL")
        or shared_model
    ).strip()
    image_model = (
        os.getenv("image_model")
        or os.getenv("IMAGE_MODEL")
        or shared_model
    ).strip()
    use_llm = os.getenv("USE_LLM", "").strip().lower() in {"1", "true", "yes", "on"}
    return Settings(
        llm_api_key=os.getenv("LLM_API_KEY", "").strip(),
        text_model=text_model,
        image_model=image_model,
        llm_base_url=os.getenv("LLM_BASE_URL", "https://openrouter.ai/api/v1").strip(),
        use_llm=use_llm,
    )
