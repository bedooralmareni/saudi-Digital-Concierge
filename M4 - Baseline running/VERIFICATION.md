# M4 verification record

Prepared on 2026-10-14. See the [README](README.md) for the third-party setup.

Environment: Windows, Python 3.14.2, an existing local virtual environment.
Python 3.11 is the recommended third-party setup. A fresh dependency installation
and execution on other platforms have not been verified in this session.

| Check | Observed result |
| --- | --- |
| Notebook structure | Both submitted notebook copies validated with nbformat; code cells compile. |
| Offline test suite | `python -m pytest -q`: 42 passed. |
| Isolated source/CSV build | Entity resolution → SQLite → vector index completed without pre-existing artifacts, using `EMBED_MODEL=stub`. |
| Isolated test suite | 42 passed; one Windows pytest cache permission warning. |
| Existing real SQLite KB | `PRAGMA integrity_check` returned `ok`. |
| API hotel demo coverage | 30 Riyadh hotels satisfy ≤400 SAR, guest rating ≥8/10, capacity ≥2 in the stored KB. |
| Qwen hotel demo coverage | 45 Riyadh hotels satisfy ≤250 SAR, guest rating ≥7/10, capacity ≥2. |
| Qwen restaurant demo coverage | 303 Riyadh restaurant records have the Italian tag and average rating ≥4/5. |
| Real semantic retrieval | Cached `intfloat/multilingual-e5-base` returned six evidence records with IDs for each Qwen hotel/restaurant example; no model downloads. |
| Dependency declarations | 13 unique dependencies; shared requirements include OpenAI and FAISS for the API notebook. |
| Secret pattern check | No OpenAI API key patterns found in the submitted code/documentation. |
| Main README | Restored to its contents before this M4 preparation; instructions are in this folder. |

The isolated build used an offline hashing stub to check the build pipeline; it
does not demonstrate semantic quality. Real retrieval was checked separately using
the existing real index and cached embedding weights. Neither check ran Qwen answer
generation or a paid OpenAI call.

## Live demonstration record

Complete this table after running each submitted notebook in a fresh Colab runtime.
The clean notebook copies have no saved execution outputs; older API outputs were
not reused as proof of the updated code. Save the downloaded JSON files, and record
the repository commit used for the run.

| Baseline | Model | Fresh runtime run | Evidence and answer | Result artifact |
| --- | --- | --- | --- | --- |
| Local Qwen | Qwen/Qwen3-8B, 4-bit | Pending | Pending | `baseline_results.zip` after running |
| OpenAI API | gpt-4o-mini | Pending | Pending | `openai_baseline_results.zip` after running |

For each run record the date, commit, runtime hardware, displayed model, prompt,
status, and downloaded file. Review the generated names/prices/ratings against the
evidence before marking the demo successful. A completed API status is not an
accuracy score. Tests with mocked answers must not be reported as model results.
