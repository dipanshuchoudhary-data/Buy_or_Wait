# Buy or Wait — run instructions

From the repository root:

```bash
uv sync
uv run pytest tests/ -q
uv run python code/main.py --mode samples
uv run python code/main.py
```

`code/main.py --mode evaluation` (the default) writes:

- `output.csv` at the repository root — one row per `dataset/requests.csv` request
- `dataset/output.csv` — same rows
- `evaluation/usage_report.md` — final-run report (copied under `code/evaluation/` and `src/evaluation/`)

Optional `.env` (never commit it):

| Variable | Purpose |
|---|---|
| `LLM_API_KEY` | OpenRouter key, only if you enable the model path |
| `tex_model` / `text_model` | Text model slug |
| `image_model` | Vision model slug |
| `USE_LLM` | `true` to send messages/images through the model |
| `--llm-explanations` | Rewrite explanations only; decisions stay on the safety gate |

The batch runner is deterministic without those variables.
