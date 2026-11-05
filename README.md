# Image understanding and content matching

This local service classifies an image library, embeds descriptions and articles, ranks candidates, and refuses a recommendation when confidence, similarity or a subject check fails. A review endpoint records approvals and rejections. It uses local Ollama models and SQLite; model calls cost $0 in API fees, excluding hardware and electricity.

```text
images -> background batch -> vision schema -> image metadata -> embedding --+
                                                                            +-> cosine rank -> mismatch guard -> review
article -------------------------------------------------------> embedding --+
```

## Setup

Install Python dependencies with `pip install -r requirements.txt`. Install Ollama and pull `qwen3-vl:2b-instruct` and `nomic-embed-text`. Copy `.env.example` to `.env`; start Ollama and run `uvicorn app:app --host 127.0.0.1 --port 8000`. The interactive API is at `/docs`. Run `python download_corpus.py` to reproduce the 40-image Wikimedia Commons corpus, checking each image's source and license in `corpus.json`. Run `python seed.py` once on a fresh database, then `POST /jobs` and poll `GET /jobs/{id}` until done. Run `python evaluate.py` for the original exact-label benchmark and `python evaluate_reviewed.py` for the reviewed relevance benchmark after classification. The latter registers a corrected article; repeated identical requests reuse its record. The seed adds one synthetic blank image to exercise uncertainty, requires the embedding model, and deduplicates repeated image and article registrations. The provider resizes images before inference; original files remain untouched.

| Endpoint | Purpose |
|---|---|
| POST /images | Register a local image and its source and license |
| POST /jobs, GET /jobs/{id} | Process pending images; inspect progress, failures and model-call records |
| POST /posts | Add and embed an article, optionally specifying its expected subject |
| GET /posts/{id}/images | Ranked accepted suggestions and explained rejections |
| GET /posts/{id}/images/{image_id} | Inspect a specific candidate's guard decision |
| POST /posts/{id}/images/{image_id}/reviews | Approve or reject a candidate |
| GET /reviews | List decisions |

## Decisions and limitations

Vision output is checked with Pydantic before use, and low-confidence results are flagged. Nearly blank images are also flagged even if the model is overconfident; the original model confidence is retained separately. Batches retry failures up to three times and record call duration, model and token counts when available. In-process background work is not a durable queue: restart marks unfinished jobs interrupted, and pending/failed images can be resubmitted. Costs are recorded as zero for the local provider, not estimated commercial pricing. Image and post vectors are stored as JSON and compared exactly in process, appropriate only for this small corpus.

The guard uses a deliberately small explicit subject vocabulary and refuses unknown expected subjects. An expected subject may be supplied explicitly; otherwise the service extracts a known subject from the article text. This extraction is a conservative vocabulary lookup, not general semantic understanding. On 2026-11-05, Qwen plus Nomic scored **7/10 (0.70) top-1 precision** on ten manually selected exact-image labels, counting refusals as misses. A red-fox article returned a fox image, a wolf candidate was rejected, an otter article returned no confident match, and the Latin synonym retrieved a fox. The earlier Moondream/all-minilm baseline scored 2/10. The ten-case evaluation is small and was used during model selection, so it is not an independent estimate. It does not validate the safety thresholds; model-reported confidence is uncalibrated, and individual classifications still need human review. License metadata for all 40 sources was rechecked; see ATTRIBUTION.md. SQLite and the in-process worker differ from the recommended PostgreSQL/durable-worker stack and should be upgraded for production.

An audit found that the benchmark's “fox at rest” label is incorrect: its selected image actually shows a fox leaping after prey. Two portrait prompts also admit another visually verified fox image. The reviewed relevance benchmark corrects that article and permits the additional appropriate image for those two cases: it scored **10/10** on the existing processed corpus. A small composition bonus favors close-view captions for explicitly close-view requests; the guard still uses unmodified cosine similarity. The original single-label benchmark remains **7/10**. The reviewed annotations and ranking adjustment were made after examining these cases and model results, so 10/10 is an in-sample result, not evidence of perfect general accuracy; an independently labeled holdout is still needed.

Tests: `pip install pytest httpx`, then `python -m pytest -q`. See `EVIDENCE.md` for what was actually checked. This repository's history began locally, so the brief's public-from-day-one requirement was not met.

## Operational safeguards

Versioned SQL migrations in migrations/ run automatically and are recorded in schema_migrations. Matching and batch services are separate from HTTP routing; persistence lives in store.py.

Default mode is trusted, single-user localhost operation. For multiple tenants, set TENANT_API_KEYS to a JSON mapping of distinct secret API keys to tenant names, and send X-API-Key with requests. Each tenant has a separate SQLite file derived from its name. Do not deploy without configured keys and HTTPS. CLI seed/evaluation scripts accept API_KEY for this mode.

MAX_MODEL_CALLS_PER_DAY (default 500) is an atomic per-tenant budget checked before provider calls, including retries. Local API fees remain zero. Image and identical article registration and identical review submission are idempotent. Batch creation atomically claims pending images. Interrupted processing becomes eligible for resubmission on startup. Failed images produce an error log and persisted alert at GET /alerts. The worker is in-process and single-instance; use a durable external worker for production availability.

All 40 image source license records were rechecked on 2026-11-05 with no missing or changed licenses. Preserve ATTRIBUTION.md with redistributed images.
