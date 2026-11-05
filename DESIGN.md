# Image understanding and matching: proposed design

**Problem:** recommend relevant, licensed images for articles while refusing uncertain or incompatible matches.

**Data:** images and validated vision metadata (subject, category, attributes, caption, confidence), posts, image/post embeddings, processing jobs, per-call usage, recommendations and review decisions. Persist in PostgreSQL with indexes on relations and review state.

**API:** batch submission and job status; image and post creation; ranked `GET /posts/{id}/images`; candidate guard inspection; approve/reject review.

**Layers:** API -> services/jobs -> vision and embedding adapters -> repository; similarity ranking -> standalone mismatch guard -> review. Validate every model response, flag low confidence, and track retries and usage.

**Guard:** reject low-confidence classifications, low similarity and explicit subject conflicts; return reasons. Select thresholds using a labeled evaluation set rather than claiming a guessed precision. A fox-versus-wolf case must be part of that set.

**Non-goal:** a full public user interface. Review can use API endpoints.

**Evidence needed:** at least 40 licensed images across four categories, 10 labeled posts, real model processing, measured top-1 precision, recorded calls and rejection examples. None has been verified yet. This design is a starting point, not a completed capstone.
