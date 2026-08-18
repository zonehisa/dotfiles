# Decision and privacy rules

The renderer applies the required decision truth table:

| Condition | Result |
| --- | --- |
| `requires_captions` OR `requires_zoom` OR `requires_comparison` is true | `remotion` |
| All three required booleans are false | `raw` |

Missing or non-boolean decision fields fail closed. A supplied mode is accepted only when it
matches this table; there is no silent override. A screenshot is supplementary evidence only.

Fail closed when any of the following is true:

- `privacy.reviewed` is not explicitly `true`, the reviewer is missing, or any of `secrets`,
  `personal_data`, or `customer_data` is not explicitly `false`;
- a recording, output, or manifest is an HTTP(S), `data:`, or other URL, is missing, or the input
  resolves outside an explicitly allowed input root;
- an input/output path resolves inside the configured application checkout;
- the repository, PR number/null marker, 40-character head SHA, or fingerprint fields are absent,
  malformed, or non-hex;
- normalized media is not MP4/H.264/yuv420p, is not standard muted output, lasts outside 1–60
  seconds, or exceeds 10 MiB.

Raw and Remotion output are normalized with ffmpeg to a 1280×720 H.264 MP4 with yuv420p,
`-movflags +faststart`, and no audio. Privacy and evidence review are separate statuses; an upload
handoff is not evidence approval. Remotion's `npm ci --ignore-scripts` uses only a private relative
`.npm-cache` directory inside the disposable run. On macOS, `sandbox-exec` limits npm writes to that
run; unsupported platforms fail closed rather than using an unsafe pathname cache. The cache is
removed after rendering and may require network/tool approval each time. Before evidence materialization, an executable local Chrome/Chromium
path is resolved from the config, environment, or conservative OS allowlist and passed with
`--browser-executable`; missing or unsafe browsers fail closed, so browser downloads cannot inspect
local evidence. The copied template, npm cache, recordings, props, and outputs remain in the
disposable run and never enter the application checkout.
