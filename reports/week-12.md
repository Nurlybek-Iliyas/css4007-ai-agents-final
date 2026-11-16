# Semester Week 12 Progress Report

Reporting window: 16–22 November 2026. In-progress report, prepared on 16 November.
Student: Ilias Nurlybek.

## Completed Work

Implemented account-scoped SQLite snapshots for Canvas with `sync`, `tasks`, `changes` and `sources` commands. Successful course snapshots are atomic; failures preserve old records and last-success timestamps. Repeated syncs do not create duplicates, and derived remaining-time fields do not produce false changes. Disappearing records are marked unavailable, never automatically completed.

Implemented optional read-only Google authorization using official OAuth libraries, separate Gmail/Classroom credentials, bounded Google pagination, Classroom course/work listing and Gmail metadata/snippet retrieval for a bounded date interval. Classroom submission status is explicitly unknown because that endpoint is not queried yet. Gmail messages are not yet classified by importance or converted into obligations.

Added 24 tests, bringing the application suite to 43. Restored the environment template and Python CI step that were absent from the student's manual Week 11 upload. Added ignore rules for OAuth files, local databases and environments. Documented setup and actual access limitations.

## Important Commits

Planned implementation commit title: `feat: add week 12 persistence and Google readers`.
The local hash is created at commit time; inspect with `git log --format="%h %s" -- src/study_radar/storage.py src/study_radar/google_sources.py`.
Publication repository: https://github.com/Nurlybek-Iliyas/css4007-ai-agents-final
A manual GitHub upload has its own commit hash and is not claimed to share local history.

## Current Functionality

The synthetic CLI sync saves three assignments; a repeat produces zero new or updated records. Cache commands report source freshness and do not claim a live check. A live read of one previously authorized Canvas course succeeded on 16 November and saved three records without sending them to an LLM. Raw private course data is excluded from this report and repository.

All 43 application tests pass with mocked network responses. Google OAuth dependencies were installed and imported locally; system Python 3.9 and LibreSSL generated compatibility warnings, so setup recommends a supported Python 3.11+ environment. No real Google authorization or data read has been demonstrated: the student does not yet have an OAuth Desktop client and requested setup instructions.

Week 11's Canvas-to-model flow remains available. The new persistence and Google readers are not yet integrated into autonomous model-selected tool execution. Google reads do not yet persist in the combined obligation database. Telegram, Teams, Google Calendar writes and the daily scheduler are not implemented.

## Problems Encountered

Manual uploads omitted two hidden configuration updates. Volatile countdown fields could cause a false update every run. Missing records could otherwise be incorrectly treated as completed. A source failure must not erase previously valid data. Google access requires user-controlled OAuth setup and possibly organization approval. Telegram is now confirmed to be a teacher's channel, but whether a bot may be added is not established.

## Solutions

Started from remote main, restored the omitted configuration and preserved existing user credentials. Compare only stable record fields, partition by Canvas account and course, keep last-success timestamps, and separate demo/live databases. Apply one complete snapshot per course and record errors without raw exception bodies. Use read-only Google scopes and a documented Desktop authorization flow with local token storage. Mark unsupported features explicitly instead of fabricating live evidence.

## What I Learned

Persistence requires identity, atomic updates and freshness tracking, not just saving JSON. An item missing from a successful listing does not establish cancellation or completion. OAuth access is different from an API key; installing a library is not proof that a university account grants permissions. Date interpretation must follow each provider's documented semantics. Partial coverage and truncated Gmail results must remain visible.

AI assistance: Codex assisted with implementation, tests, documentation and repository preparation. The student must perform the Google authorization, review the code, verify real results and explain the design during defense.

## Next Week

Before closing Week 12, complete Google Cloud setup, authorize the intended accounts and compare a small real Gmail/Classroom sample with the source interfaces. Confirm the permitted Telegram channel access method. Then add extraction of obligations from messages, integrate additional sources into storage, and begin genuine model-selected tool execution. Record any inaccessible integration and revise scope transparently.
