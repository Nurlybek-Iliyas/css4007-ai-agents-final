# StudyRadar — Architecture and Decisions

Status: Week 10 design, not implemented. Student: Ilias Nurlybek.

## Scope and decisions

- One student first; natural-language requests and scheduled collection share one agent loop.
- Canvas, Gmail, Classroom, Telegram and Teams are all intended academic sources. Telegram matters because teachers post homework there.
- Few Canvas assignments do not invalidate the use case: practice documents, meetings and requests for replies are also obligations.
- Start with Python, SQLite and a small web UI; retain the instructor's existing Node checks.
- A single agent is sufficient. Framework choice and multiple agents do not establish A-level autonomy.
- Implement connectors incrementally. Never represent mock data or an inaccessible source as a successful live integration.

## Proposed modules

| Path | Responsibility |
|---|---|
| `src/study_radar/agent/` | Model adapter, tool registry, adaptive loop and run state |
| `src/study_radar/connectors/` | Authorized Canvas, Google, Telegram and Microsoft reads |
| `src/study_radar/tasks/` | Obligation extraction, deadlines, evidence and reconciliation |
| `src/study_radar/calendar/` | Proposals, approved changes, idempotency and verification |
| `src/study_radar/safety/` | Argument schemas, allowlists, approval checks and execution budgets |
| `src/study_radar/storage/` | SQLite persistence and migrations |
| `src/study_radar/scheduler/` | Periodic runs, locks, checkpointing and last-success timestamps |
| `src/study_radar/ui/` | Questions, obligations, calendar previews and connection health |
| `tests/` | Application tests alongside preserved instructor starter tests |
| `data/fixtures/` | Synthetic, non-sensitive evaluation data |

These paths are planned; empty modules are not presented as working functionality.

## Data model

An obligation records `id`, action, course/category, status, due date (nullable), date precision, timezone, evidence references, discovery/update times and any calendar event ID. Date-only deadlines remain date-only rather than acquiring an invented time. Default display timezone is Asia/Almaty; source timestamps are preserved.

Evidence records source system, source record ID, URL if available, timestamp and supporting excerpt. A source status records last attempt, last success, cursor and access errors. Completion requires an explicit service status or user confirmation; read email is not evidence of completion.

A run records goal, authorized scope, observed records, unresolved questions, tool outcomes, step/call/retry counts, elapsed time and stopping reason. Runs stop on completion, clarification, unrecoverable failure, authorization denial or exhausted limits.

## Agent behavior

The model chooses tools from schemas, receives results and selects the next action. Missing context can trigger a thread read; unclear identity can trigger a question. An inaccessible service yields a partial result naming the missing coverage. Generic questions may need no tools. Connectors themselves use deterministic pagination and parsing.

Deduplicate primarily by provider IDs and saved mappings. Similar titles are candidates, not proof that two items are the same. Preserve multiple evidence references. Newer messages are not automatically authoritative; ambiguous deadlines are surfaced to the user.

## Access inventory — Week 10 evidence

| Source | Known so far | Still to verify |
|---|---|---|
| Canvas Narxoz | User supplied the login URL and screenshot showing token creation control | Actual authorized reads, available fields, rate limits |
| Gmail | User confirmed usage | Google authorization and permitted access |
| Classroom | User confirmed usage | Coursework and own submission access |
| Telegram | User confirmed homework is posted in an academic group | Group/channel identity and permitted bot/account access method |
| Teams | User confirmed usage | Whether data is in assignments, chats, channels or meetings; tenant approval |
| Google Calendar | User wants calendar synchronization | Authorization and dedicated calendar selection |

No account is connected and no credentials have been collected. API access is not established by the presence of a settings button alone. If institutional restrictions prevent access, document the limitation and discuss an authorized alternative or scope adjustment; do not bypass controls.

## Guardrails and calendar writes

Source messages and attachments are untrusted. Restrict tool access to configured accounts/resources. Validate arguments before dispatch. Do not expose unrestricted shell, deletion or message-sending tools. Configure finite step, call, retry, time and token budgets.

A calendar proposal includes exact changes, source evidence and a version. Approval comes from the UI and is stored server-side; the model cannot mint an approval ID. Before execution, check ownership, proposal version, freshness and whether approval was already consumed. Recheck existing events to avoid overwriting intervening changes. Write only to the selected agent calendar and read back important fields. A failed read-back means unverified, not success. Retried operations must reconcile saved event IDs rather than duplicate events.

Daily runs collect findings and prepare proposals; unattended writes are outside the first version. The scheduler needs a running machine/service. Show last-success timestamps so an offline application never implies continuous monitoring.

## Privacy and observability

Keep credentials, session files, private downloads and the runtime database in ignored local storage. Logs contain observable tool actions and concise reasons, not hidden reasoning or secrets. Public fixtures use invented people and accounts. Minimize private content sent to the model and obtain the user's consent during connection setup.

## AI assistance

Codex assisted with requirement analysis, documentation drafting and repository preparation. These documents describe a proposal, not implemented features. The student is responsible for reviewing the design, understanding future code, verifying behavior and explaining technical decisions.
