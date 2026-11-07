# Semester Week 10 Progress Report

Reporting window: 2–8 November 2026. Prepared on 7 November 2026.
Student: Ilias Nurlybek.

## Completed Work

Defined StudyRadar as an individual A-level project addressing fragmented academic information for a fourth-year student. Identified Canvas, Gmail, Classroom, Telegram and Teams as intended sources, with Google Calendar as an approved output destination. Clarified that supported natural-language scenarios can expand beyond the initial examples.

Completed the project proposal with function specifications, tool responsibilities, a provisional model selection, architecture, example requests, evaluation design and weekly milestones. Documented task state, source evidence, deduplication, approval boundaries and API-access risks in `docs/architecture.md`. Specified eighteen planned application test scenarios in `docs/evaluation.md`, including all four mandatory guardrail categories.

Inspected the instructor starter and prepared this change in a local clone linked to the student's fork. The Canvas settings screenshot establishes the presence of a token-creation control, not working API access. No real connector or model call has been implemented or tested.

## Important Commits

The initial planning commit is the commit that introduces this report, titled `docs: define StudyRadar proposal and week 10 plan`.

Its immutable hash is generated only when the commit is created, so it is not embedded into its own content. After creation, locate the exact hash with `git log -1 --format=%H -- reports/week-10.md`. Repository history: https://github.com/Nurlybek-Iliyas/css4007-ai-agents-final/commits/main/reports/week-10.md

The contribution is a concrete architecture and evaluation plan, not a claim of completed application functionality.

## Current Functionality

The repository contains the instructor's starter utilities and the StudyRadar planning documents. StudyRadar cannot yet read accounts, run an LLM agent, schedule checks or update a calendar. The instructor's starter tests do not count as StudyRadar's required application tests.

Repository verification: proposal validation, Week 10 report validation and the combined required-week check passed. All 10 instructor starter tests passed under Node 22.23.4. These results check the starter and documentation, not StudyRadar behavior.

## Problems Encountered

Information about account permissions is incomplete. Telegram access type and Teams content/tenant permissions remain unresolved. Calendar actions need an application-enforced approval mechanism. Few real Canvas assignments may not exercise important failure cases. The initial workspace had no checkout or configured Git author.

## Solutions

Created a local checkout retaining instructor history and configured the student's fork and supplied author identity. Planned incremental connection checks, beginning with Canvas and Gmail, with explicit reporting of blocked sources. Designed versioned calendar previews and read-back verification. Planned synthetic scenarios with expected results plus a small authorized real-data demonstration.

## What I Learned

The planning process distinguished model-selected tool use from a fixed synchronization script. A-level autonomy requires state, decisions based on observations, bounded recovery and verified outcomes. Source text must not grant permissions. A message without a deadline should remain uncertain, and completion cannot be inferred from elapsed time. More integrations alone do not demonstrate agent quality.

AI assistance disclosure: Codex helped interpret the assignment, draft the design and reports, prepare the repository and run repository checks. The student must review this material and understand and defend the implementation as it is developed.

## Next Week

Verify authorized Canvas reads and remaining source-access prerequisites; implement the first real LLM request and evidence-backed response. Start Gmail authorization, define typed tool results, validate inputs and record actual successes/failures. Document any access restrictions and revised integration scope rather than claiming unsupported connectivity.
