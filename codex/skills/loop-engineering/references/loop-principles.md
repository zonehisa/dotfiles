# Loop Engineering Principles

This reference backs the `loop-engineering` skill. Use it when designing a project harness or deciding how to evolve `SPEC.md`, `HARNESS.md`, `RETRO.md`, `AGENTS.md`, tests, checks, hooks, or skills.

Unless the user explicitly requests another language, write loop artifacts and project-harness content in Japanese. Keep code, commands, filenames, identifiers, product names, source titles, and exact quoted terms in their original language when needed.

## Source-Backed Principles

### 1. Treat improvement as PDSA, not vague iteration

The Deming Institute describes PDSA as a cycle for continual learning: plan identifies the goal, theory, success metrics, and plan; do implements; study compares outcomes to the theory; act integrates learning and adjusts the next cycle. Deming emphasized `Study` because the point is to revise theory, not merely check success or failure.

Apply this by requiring every non-trivial loop to state a hypothesis and expected observation before changing code.

Source: https://deming.org/explore/pdsa/

### 2. Optimize for short, amplified feedback loops

Gene Kim's Three Ways frame DevOps around systems thinking, amplified feedback loops, and continual experimentation and learning. The second way explicitly aims to shorten and amplify feedback so corrections happen continuously; the third way emphasizes experimentation, learning from failure, and deliberate practice.

Apply this by choosing the smallest sensor that can falsify the current hypothesis and by leaving behind a better sensor when a failure class recurs.

Source: https://itrevolution.com/articles/the-three-ways-principles-underpinning-devops/

### 3. Make repository guidance durable but scoped

Codex official guidance says `AGENTS.md` is the right surface for durable repository guidance such as layout, commands, conventions, constraints, PR expectations, and verification. It also recommends updating `AGENTS.md` after repeated Codex mistakes. Codex skills are for reusable workflows and rely on descriptions for triggering, with progressive disclosure to avoid context bloat.

Apply this by keeping the loop method global, but promoting only project-specific behavior and checks into the project harness.

Sources:

- Codex manual, Best practices: `/codex/learn/best-practices.md`
- Codex manual, Agent Skills: `/codex/skills.md`
- Codex manual, AGENTS.md: `/codex/guides/agents-md.md`

### 4. Split specification, verification, and learning history

A useful harness separates three concerns:

- `SPEC.md`: what the system must do.
- `HARNESS.md`: how the project observes, reproduces, tests, and verifies behavior.
- `RETRO.md`: what failed, what was learned, and what was promoted.

This avoids turning `AGENTS.md` into a dumping ground. Promote only durable agent behavior into `AGENTS.md`; promote machine-detectable risks into tests, scripts, sensors, or hooks.

### 5. Use testing to reduce uncertainty

Google SRE's reliability testing chapter frames tests as a way to demonstrate equivalence across change and reduce uncertainty. It also notes that passing tests do not prove reliability, while failing tests demonstrate absence of reliability. Strong tests can block pushes and create effectively zero-MTTR detection before users are affected.

Apply this by starting with the nearest meaningful test and broadening only when the change's blast radius demands it.

Source: https://sre.google/sre-book/testing-reliability/

### 6. Combine black-box and white-box observations

Google SRE distinguishes black-box monitoring as externally visible user behavior and white-box monitoring as internal signals such as logs and metrics. It also recommends monitoring the four golden signals for user-facing systems: latency, traffic, errors, and saturation.

Apply this by pairing user-visible reproduction with internal branch-point evidence when debugging.

Source: https://sre.google/sre-book/monitoring-distributed-systems/

### 7. Keep test portfolios fast and layered

The practical test pyramid recommends a well-rounded automated test portfolio so teams learn whether software is broken in seconds or minutes instead of days or weeks. It emphasizes automation, different test granularities, and maintainable checks.

Apply this by keeping many fast checks, fewer expensive cross-boundary checks, and only enough end-to-end/browser verification to cover critical user flows.

Source: https://martinfowler.com/articles/practical-test-pyramid.html

### 8. Keep postmortems blameless and actionable

Google SRE describes postmortems as written records of impact, mitigation, root causes, and follow-up actions. It emphasizes that postmortems are learning opportunities, not punishment, and should focus on contributing causes and effective prevention.

Apply this by recording severe or repeated failures in `RETRO.md` and converting action items into `HARNESS.md`, tests, sensors, docs, or hooks.

Source: https://sre.google/sre-book/postmortem-culture/

### 9. Build eval datasets for diagnosis, not size

OpenAI eval guidance frames evaluations as a way to specify behavior, run test inputs, analyze results, and iterate. OpenAI's realtime eval guide emphasizes that eval datasets exist to drive iteration: run evals, localize failures, change one thing, re-run, and confirm no regressions. It also stresses coverage over raw count, balanced positive/negative cases, and precise tags to localize failure causes.

Apply this to LLM and agent workflows with small, tagged golden sets that include expected successes and expected refusals or non-actions.

Sources:

- https://developers.openai.com/api/docs/guides/evals
- https://developers.openai.com/cookbook/examples/realtime_eval_guide#42-build-for-iteration-not-just-volume

## Harness Maturity Model

### Level 0: Ad hoc

- No stable spec or verification map.
- Agent relies on conversation and local inspection.
- Final reports mention tests but the project does not retain learning.

Next step: create initial `SPEC.md`, `HARNESS.md`, and `RETRO.md`.

### Level 1: Named checks

- Core test commands and manual checks are documented.
- Common workflows have known reproduction steps.
- Failures are occasionally recorded.

Next step: map checks to behavior boundaries and add missing sensors.

### Level 2: Behavior-linked harness

- `SPEC.md` defines business or product boundaries.
- `HARNESS.md` maps each boundary to tests, fixtures, browser checks, logs, or metrics.
- `RETRO.md` records repeated failure classes and promotions.

Next step: convert recurring manual checks into automated tests or scripts.

### Level 3: Regression-aware

- New bugs usually get a reproducer or sensor.
- PRs cite exact checks and known gaps.
- Repeated failures promote into rules, tests, hooks, or skills.

Next step: add dashboards, eval datasets, contract tests, and hooks where they reduce repeated mistakes.

### Level 4: Self-improving

- Harness changes are part of normal delivery.
- Failures automatically suggest missing sensors.
- Hooks or CI enforce high-value checks.
- Project-specific agent guidance stays short because durable knowledge lives in the right artifact.

## Promotion Matrix

| Learning | Put it in |
| --- | --- |
| Business rule, invariant, acceptance criterion | `SPEC.md` |
| TDD red/green/refactor command, fixture, covered behavior | `HARNESS.md` |
| Test command, manual verification path, reproduction recipe | `HARNESS.md` |
| Incident, failed hypothesis, recurring mistake, decision log | `RETRO.md` |
| Process rule, service workflow, checklist, operating agreement | `SPEC.md` or the project's process spec |
| Metric definition, experiment method, KPI guardrail, sampling plan | `HARNESS.md` |
| Decision rationale, tradeoff accepted, assumption that later changed | `RETRO.md` or a project decision log |
| Agent behavior required across the repository | `AGENTS.md` |
| Mechanical enforcement around commands, files, or turn completion | `.codex/hooks` or config hooks |
| Cross-project reusable workflow | global Skill |
| Tool-specific deterministic operation | Skill script |

## Route Selection

Loop engineering is not a single ceremony. Pick the loop shape from the user's desired outcome:

| Desired outcome | First question | Good first sensor |
| --- | --- | --- |
| Fix a defect | "What observation proves it is broken?" | Reproducer, failing test, log line, visible mismatch |
| Develop with TDD | "What is the smallest behavior we can prove first?" | Failing unit/feature/contract test |
| Ship a feature | "What behavior must be true when done?" | Acceptance test, example, user-flow check |
| Refactor safely | "What proves behavior stayed the same?" | Current tests, snapshot, golden output |
| Improve an operation | "Where is the current bottleneck?" | Cycle time, queue length, error/rework count |
| Make a decision | "What criteria decide between options?" | Tradeoff table, source evidence, small prototype |
| Improve a metric | "What is the baseline and guardrail?" | KPI baseline, cohort, counter-metric |
| Improve an LLM workflow | "What examples define success and failure?" | Tagged golden set, grader, tool-call trace |
| Build a harness | "What should future work never need to rediscover?" | Existing docs/tests/checks and recent failures |

For non-software work, interpret the harness broadly:

- `SPEC.md` means "what must be true" for the workflow or decision domain.
- `HARNESS.md` means "how we know" through metrics, review criteria, sampling, checklists, or experiments.
- `RETRO.md` means "what we learned" from attempts, incidents, decisions, and reversals.

## Loop Anti-Patterns

- Changing multiple unknowns in one loop.
- Fixing without a reproducer when a reproducer is feasible.
- Implementing new behavior first when a small failing test is feasible.
- Writing a broad end-to-end test when a focused unit, feature, or contract test would falsify the same hypothesis faster.
- Treating "tests passed" as proof instead of evidence.
- Adding broad `AGENTS.md` warnings when a test or hook can catch the issue.
- Creating large eval sets without tags or negative cases.
- Recording retrospectives without converting action items into sensors.
- Re-running the same failing command without adding information.

## Minimal Project Harness Templates

Use the script in `scripts/init_harness.py` for first-time setup. If writing manually, keep the files short at first and let them grow from real work.

`SPEC.md` should answer:

- What behavior matters?
- What invariants must not break?
- What is out of scope?
- What open questions affect implementation?

`HARNESS.md` should answer:

- How do we reproduce important behavior?
- Which tests/checks verify which boundaries?
- Which browser/manual checks matter?
- What logs, metrics, fixtures, evals, or seed data are useful?
- What gaps are known?

`RETRO.md` should answer:

- What failed?
- What hypothesis did we test?
- What did we change?
- What did verification show?
- What was promoted into spec, harness, docs, tests, hooks, or skills?
