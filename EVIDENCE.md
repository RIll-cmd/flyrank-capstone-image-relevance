# Evidence and outstanding checks

- Guard, provider and API tests: `python -m pytest -q` -> 9 passed. The API test substitutes the vision and embedding providers; it exercises batch state, rejection of a wolf for a fox post, and review behavior.
- Corpus download: 40 files across the search terms red fox, gray wolf, domestic dog and brown bear; `corpus.json` records source, license and creator metadata. A contact sheet was inspected, but search terms are not ground truth and individual licensing still needs review.
- Live vision batch on 2026-11-05: Moondream processed 40/40 images, with 0 failed and 4 flagged for low confidence. Call records show model, duration, token counts when available, and $0 local API cost. Successful processing does not mean the classifications were all correct; individual source review is still required.
- A later Qwen/Nomic run processed all 40 corpus images with no processing failures. A separately generated blank fixture was flagged with confidence 0.0 and an image-quality warning. Processing records store model, token counts when available, duration, and zero local API fees.
- Live probes: `The behavior of red foxes` returned a `Red fox` suggestion; forcing image 11, a wolf, produced `Subject mismatch: expected red fox, detected wolf`. An otter article returned `no confident match`; a `Vulpes vulpes` article returned a red-fox suggestion.
- Image and post embeddings were generated with `nomic-embed-text`, using its document and query prefixes, and stored; ranking and refusal were exercised against the real data.
- Review endpoints: exercised with simulated embeddings and classification.
- Top-1 precision on 10 manually labeled posts at similarity 0.72 and confidence 0.75: **7/10 (0.70)**, counting refusals as misses. This small set was used to select models and is not an independent test set. The earlier Moondream/all-minilm run scored 2/10; Qwen/all-minilm scored 4/10; Qwen/mxbai scored 6/10. Thresholds are not validated against a broad negative set.
- The dedicated repository began locally rather than publicly from day one. Individual license review and submission remain outstanding.
