# Image understanding and content matching

This local service classifies an image library, embeds descriptions and articles, ranks candidates, and refuses a recommendation when confidence, similarity or a subject check fails. A review endpoint records approvals and rejections. It uses local Ollama models and SQLite; model calls cost $0 in API fees, excluding hardware and electricity.

```text
images -> background batch -> vision schema -> image metadata -> embedding --+
                                                                            +-> cosine rank -> mismatch guard -> review
article -------------------------------------------------------> embedding --+
```

## Setup

Install Python dependencies with `pip install -r requirements.txt`. Install Ollama and pull the `moondream` and `all-minilm` models. Copy `.env.example` to `.env`; start Ollama and run `uvicorn app:app --host 127.0.0.1 --port 8000`. The interactive API is at `/docs`. Run `python download_corpus.py` to reproduce the 40-image Wikimedia Commons corpus, checking each image's source and license in `corpus.json`. Run `python seed.py` once on a fresh database, then `POST /jobs` and poll `GET /jobs/{id}` until done. Run `python evaluate.py` after classification. `seed.py` requires the embedding model and is intended for an empty database; it does not deduplicate repeated seeds.

| Endpoint | Purpose |
|---|---|
| POST /images | Register a local image and its source and license |
| POST /jobs, GET /jobs/{id} | Process pending images; inspect progress, failures and model-call records |
| POST /posts | Add and embed an article with its expected subject |
| GET /posts/{id}/images | Ranked accepted suggestions and explained rejections |
| GET /posts/{id}/images/{image_id} | Inspect a specific candidate's guard decision |
| POST /posts/{id}/images/{image_id}/reviews | Approve or reject a candidate |
| GET /reviews | List decisions |

## Decisions and limitations

Vision output is checked with Pydantic before use, and low-confidence results are flagged. Batches retry failures up to three times and record call duration, model and token counts when available. In-process background work is not a durable queue: restart marks unfinished jobs interrupted, and pending/failed images can be resubmitted. Costs are recorded as zero for the local provider, not estimated commercial pricing. Image and post vectors are stored as JSON and compared exactly in process, appropriate only for this small corpus.

The guard uses a deliberately small explicit subject vocabulary and refuses unknown expected subjects. Its thresholds are initial placeholders, not tuned results. The evaluation contains ten manually selected exact-image labels; `evaluate.py` counts refusals as misses. **No real-model precision has been measured yet**, and the current corpus includes search results that need individual content and license review. The system has not demonstrated the fox-first acceptance probe with a real model. Human-supplied expected subjects are a constraint, not an independently inferred article label. SQLite and the in-process worker differ from the recommended PostgreSQL/durable-worker stack and should be upgraded for production.

Tests: `pip install pytest httpx`, then `python -m pytest -q`. See `EVIDENCE.md` for what was actually checked. This local folder must be moved into its own public GitHub repository for submission; no public repository or staged history has been created here.
