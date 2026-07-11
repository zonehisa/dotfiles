# Issue Workflows

## Create or Triage an Issue

1. Detect the repository and read its Issue/Project conventions.
2. Search open Issues for duplicates using title and body keywords.
3. Draft only relevant sections: summary, details or reproduction, expected/current behavior, acceptance criteria, and context.
4. List labels and use existing labels unless the user asks to create one.
5. Add the Issue to a Project only when repository docs require it or the user asks.
6. Create the Issue only with explicit authorization, report its URL, and stop.

Useful commands:

```bash
gh issue list --repo <owner/repo> --state open --limit 30
gh label list --repo <owner/repo> --limit 100
gh issue create --repo <owner/repo> --title "<title>" --body-file <body-file>
```

For triage, verify current state and evidence before changing labels, status, or Project fields. Do not infer authorization for external mutations from a request to inspect or summarize.
