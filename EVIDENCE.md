# Evidence and outstanding checks

- Guard and API tests: `python -m pytest -q` -> 6 passed. The API test substitutes the vision and embedding providers; it exercises batch state, rejection of a wolf for a fox post, and review behavior.
- Corpus download: 40 files across the search terms red fox, gray wolf, domestic dog and brown bear; `corpus.json` records source, license and creator metadata. A contact sheet was inspected, but search terms are not ground truth and individual licensing still needs review.
- Live vision schema validation and low-confidence flag: not run; Ollama and vision model unavailable.
- Live batch retries, progress and call costs: not run against a model.
- Live image and post embeddings and semantic retrieval: not run.
- Fox-first ranking, wolf rejection on live output, no-match response: not run end-to-end. The fox/wolf guard is covered by simulated tests only.
- Review endpoints: exercised with simulated embeddings and classification.
- Top-1 precision on 10 labeled posts: not measured. Thresholds are untuned.
- Public dedicated repository, commit history, license audit, and submission: outstanding.
