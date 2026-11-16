# Semester Week 11 Progress Report

Reporting window: 9–15 November 2026. Progress recorded on 9 November; this is an in-progress report, not a claim that the entire week is complete.
Student: Ilias Nurlybek.

## Completed Work

Implemented a Python command-line prototype with `setup`, `demo`, `courses`, `assignments` and `ask` commands. Added a read-only Canvas Narxoz connector, bounded pagination and normalized assignment records. Dates are timezone-aware and displayed in Asia/Almaty; missing deadlines remain unknown. Submission state is preserved without assuming that graded or overdue means completed.

Implemented an OpenAI Responses API adapter using the proposed configurable model, structured output and local validation. The first workflow is intentionally fixed: read selected Canvas courses then ask the LLM; autonomous tool selection is a later milestone. The model selects relevant source IDs. Code validates these IDs and builds status explanations, counts, dates and URLs from known records, rather than displaying unverified model claims about overdue work.

Added a synthetic fixture, setup instructions and 19 application tests using mocked network responses. Added Python tests to CI alongside the instructor's existing checks. Credentials are entered locally with hidden input and never included in the public files.

## Important Commits

Implementation commit title: `feat: add week 11 Canvas and LLM prototype`.
The hash will be generated upon commit creation. Locate it with `git log --format="%h %s" -- studyradar.py src/study_radar tests/python`.
Repository: https://github.com/Nurlybek-Iliyas/css4007-ai-agents-final
If files are uploaded through the GitHub UI, its upload commit is the publication record; a local commit hash is not claimed to exist remotely.

## Current Functionality

The CLI runs locally on Python 3.9.6 without third-party Python dependencies. The synthetic demo correctly shows a submitted assignment, a future deadline and an assignment with no deadline. All 19 application tests pass, including six new status/response regression cases. The missing-credentials path reports a clear error without exposing secrets.

On 9 November, the student ran the CLI locally and shared successful output: seven active Canvas courses, three assignments in a selected course, and a live Canvas-to-LLM answer. A deadline matched the student’s browser check. The assistant also verified a real model call using synthetic data. The student then repeated the corrected workflow at 05:18 UTC on 9 November and shared its output: two not-submitted items were selected, while the graded item with no submission timestamp was explicitly not established as a debt and was excluded from the attention list. Counts and evidence fields were consistent in this run. Live validation is limited to this sample; private course records and credentials are not included in the repository. Gmail, Classroom, Telegram, Teams, Google Calendar, persistence, scheduling and autonomous tool selection remain unimplemented.

## Problems Encountered

The student's first-week documents were uploaded through the website, so the remote history differs from the earlier local planning commit. Live account tests require local credentials. Python on the computer is 3.9.6. Canvas pagination could otherwise forward a token to an untrusted host or run indefinitely. The first live answer incorrectly called a graded assignment overdue because its due date had passed and submitted_at was null, despite missing=false. Its summary also mixed inconsistent counts. Earlier connector attempts returned HTTP 401 and 503 before the student obtained a successful local response.

## Solutions

Based this implementation branch on the student's actual remote main branch. Used Python 3.9-compatible standard-library code. Added hidden local credential setup, same-origin pagination validation, redirect rejection, page/response/time limits and safe HTTP error messages. Preserved submission metadata and explicit unknown values. Required an explicit CLI flag before sending live Canvas records to the model. Added deterministic status assessment: graded alone establishes neither debt nor submission, missing=true is explicit missing evidence, and elapsed dates alone do not prove an obligation is outstanding. The returned answer no longer displays free-form model status claims or counts. Regression tests reproduce the problematic combination using synthetic records. A repeat real model call on synthetic data selected the two outstanding items correctly.

## What I Learned

An implemented API adapter and mocked tests are distinct from verified live integration. Calendar dates require timezone-aware parsing; absence of a deadline must remain explicit. Provider response schemas and source-ID validation prevent some malformed or invented references, but do not prove every model statement true. Integration scope must be visible to avoid presenting a single-course check as a complete scan of all platforms.

AI assistance disclosure: Codex helped implement the prototype, tests and documentation. The student remains responsible for inspecting the code, performing authorized live checks and explaining behavior during defense.

## Next Week

The first live Canvas-to-LLM milestone and its corrected repeat are verified. Continue Week 11 by checking a second course and a different question; this single sample does not establish general accuracy. Begin Gmail access setup and resolve Telegram/Teams permissions. Week 12 will extend the obligation schema and persistence, add source integrations and evolve the fixed first workflow toward genuine model-selected tools. Any unfinished integration will remain explicitly documented.
