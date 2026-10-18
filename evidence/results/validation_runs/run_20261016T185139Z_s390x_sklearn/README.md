# BLACKBOX runtime validation run

- started_at_utc: 2026-10-16T18:50:38.584403+00:00
- finished_at_utc: 2026-10-16T18:51:39.241435+00:00
- process architecture: s390x
- runtime label: linuxone (process is s390x)
- python: 3.12.3
- git_revision: (unavailable)
- model_backend: sklearn
- dataset_sha256: 546f57ce91292214e813e7fd7f7004c32188da54e8a952894076a0e5a8d2d5c3
- dataset_matches_manifest: True
- overall_status: **PASS**

| step | required | status | exit | duration_s | notes |
|---|---|---|---|---|---|
| pip_install_requirements_dev | no | **NOT RUN** | - | 0.0 | skipped (no --install flag); use on target only if install is permitted |
| environment_diagnostics | yes | **PASS** | 0 | 0.946 | process_machine=s390x; runtime_label=linuxone; backend=sklearn; linuxone_verified=True |
| dataset_manifest_integrity | yes | **PASS** | 0 | 0.0 | sha256=546f57ce91292214e813e7fd7f7004c32188da54e8a952894076a0e5a8d2d5c3; manifest=546f57ce91292214e813e7fd7f7004c32188da54e8a952894076a0e5a8d2d5c3 |
| run_tests_dependency_free | yes | **PASS** | 0 | 26.927 | no FAIL lines |
| pytest_full_suite | yes | **PASS** | 0 | 27.18 | pytest reported passed without failed |
| smoke_test_pipeline_and_http | yes | **PASS** | 0 | 3.141 | all smoke checks PASS including HTTP |
| live_http_uvicorn | no | **PASS** | 0 | 0.076 | real HTTP against a live uvicorn process |
| validation_experiment_rerun | no | **NOT RUN** | - | 0.0 | deliberately not run by default: re-running overwrites evidence/results/validation. See docs/BACKEND_EVIDENCE.md; use scripts/run_experiment.py manually when needed. |

AMD64 (or any non-s390x) results do NOT establish LinuxONE results.
Full command stdout/stderr tails are in validation_report.json.
