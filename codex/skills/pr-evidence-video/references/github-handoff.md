# GitHub handoff

The renderer never uploads. A later, explicitly authorized PR Conversation upload is valid only
for the exact tuple:

`repository + branch + head SHA + review fingerprint + artifact SHA-256`

The operator prepares only the target and hash; `git_operator_luna` carries out that preparation. The Coordinator performs the browser/UI upload when the operator cannot operate the UI, and checks the exact tuple immediately before the write. No API or `gh` pretend upload is allowed, and there is no external-storage or other fallback.
Stop on a target, head, fingerprint, or artifact-hash mismatch. Uploading a replacement,
re-encoding the video, moving it to external storage, or changing the PR requires new
authorization and a new evidence review. The manifest starts with `handoff.status: pending`; later
status values are `approved`, `uploaded`, or `invalid`, and must never be conflated with the
completion-review gate.

`reviewer_luna` checks only video/artifact completeness, privacy, target/fingerprint binding, and
handoff evidence. It does not judge visual styling, re-render the artifact, run tests, or review
application source.
