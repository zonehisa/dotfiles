# dotfiles

macOS を主対象にしつつ、Codex/agent/skill と PR evidence workflow は WSL2 でも利用できる
開発環境設定のリポジトリです。

## 含まれるもの

- `zsh`: [`.zshrc`](./.zshrc)
- `Homebrew`: [`Brewfile`](./Brewfile)
- `sheldon`: [`.config/sheldon/plugins.toml`](./.config/sheldon/plugins.toml)
- `zeno`: [`.config/zeno/config.yml`](./.config/zeno/config.yml)
- `starship`: [`.config/starship.toml`](./.config/starship.toml) ほか 2 ファイル
- `tmux`: [`.config/tmux/tmux.conf`](./.config/tmux/tmux.conf)
- `git`: [`.config/git/ignore`](./.config/git/ignore)
- `gh`: [`.config/gh/config.yml`](./.config/gh/config.yml)
- `lazygit`: [`.config/lazygit/config.yml`](./.config/lazygit/config.yml)
- `nvim`: [`.config/nvim/`](./.config/nvim)
- `wezterm`: [`.config/wezterm/`](./.config/wezterm)
- `alacritty`: [`.config/alacritty/alacritty.toml`](./.config/alacritty/alacritty.toml)
- `AeroSpace`: [`.config/aerospace/aerospace.toml`](./.config/aerospace/aerospace.toml)
- `Karabiner-Elements`: [`.config/karabiner/karabiner.json`](./.config/karabiner/karabiner.json)
- macOS 用補助スクリプト: [`bin/`](./bin)
- Codex Skills: [`codex/skills/`](./codex/skills)

## セットアップ

### macOS

```bash
git clone <your-repo-url> ~/dotfiles
cd ~/dotfiles
chmod +x setup.sh
./setup.sh link
```

`setup.sh` は既存ファイルを `*.bak.YYYYMMDD_HHMMSS` として退避してから、dotfiles へのシンボリックリンクを作成します。

初回に手元の設定をこのリポジトリへ取り込みたい場合は:

```bash
./setup.sh init
```

`init` は `LINKS` に定義された対象だけを `~/` からこの repo へコピーします。既に repo 側にあるファイルは上書きしません。

Codexの設定とSkillsは次へリンクされます。

- `codex/skills/parallel-worktree` → `~/.agents/skills/parallel-worktree`
- `codex/skills/git-workflow` → `~/.codex/skills/git-workflow`
- `codex/skills/pr-evidence-video` → `~/.codex/skills/pr-evidence-video`
- `codex/agents/implementer-luna.toml` → `~/.codex/agents/implementer-luna.toml`
- `codex/agents/explorer-luna.toml` → `~/.codex/agents/explorer-luna.toml`
- `codex/agents/verifier-luna.toml` → `~/.codex/agents/verifier-luna.toml`
- `codex/agents/git-operator-luna.toml` → `~/.codex/agents/git-operator-luna.toml`
- `codex/agents/reviewer-luna.toml` → `~/.codex/agents/reviewer-luna.toml`

実行時registry、lock、evidenceは`${CODEX_HOME:-$HOME/.codex}/parallel-worktree`、Worktreeはadapterごとの管理領域に保持され、dotfilesでは管理しません。

実装時はGPT-5.6 Luna `max`の`implementer_luna`を唯一のwriterとして使います。独立したcode／contract／impact調査はread-onlyの`explorer_luna`、開始時の安全な非変異baseline／test map／browser planは`verifier_luna`へ分離します。user-visible UIの実装checkpoint後はimplementerをpauseし、Coordinatorの`coordinator_browser_evidence` packetをverifierがread-onlyで検証し、targeted test／log分析／objective non-browser checksを実行します。Non-UI checkpointはbrowser packet・human UI acceptance・`accepted_source_fingerprint`なしでtargeted test／log分析／objective non-browser checksを直接実行します。親から起動できる子agentは最大3つ（Git／review roleを含む全delegated roleの合計）で、nested delegationは行いません。

### User-visible UI workflow order

The following order applies only to user-visible UI changes. Non-UI changes keep the existing flow.
For non-UI checkpoints, use targeted tests, log analysis, and objective non-browser checks directly; no Coordinator browser packet, human UI acceptance, or `accepted_source_fingerprint` is required.
Use explicit checkpoint/evidence wording; do not add a complex persisted state mechanism.

### Built-in IAB selection and evidence

Every user-visible UI checkpoint and human acceptance requires valid browser evidence owned by Coordinator/main; verifier final requires a validated `coordinator_browser_evidence` packet and source integrity. Verifier-side IAB availability is not required.

For user-visible UI, the Coordinator/main context is the browser executor and owner: it runs the visual/interactive checks and records the `coordinator_browser_evidence` packet.

For the default path, before the first visual or interactive check, explicitly select the built-in IAB with the exact selector `agent.browsers.get("iab")`. A Browser skill read, shell/HTTP/test result, `getDefault()`, `getForUrl()`, or `agent.browsers.get("extension")` is not valid browser evidence.

Chrome or Edge is an exception only when the user explicitly requests it, or Chrome/Edge-specific login, extension, or existing-tab access is required and the reason and approval are recorded. For an approved browser exception, select the exact matching `agent.browsers.get("chrome")` or `agent.browsers.get("edge")` selector and reject a missing reason, missing approval, or family mismatch. Never auto-fallback from IAB to another browser surface.

Both browser paths require an exact selector, checked URL, primary flow/view, applicable existing-policy viewport set, and no automatic fallback.

Missing vendor/node_modules/.env/DB, an app that is not started, or a port conflict is not a reason to defer IAB to verifier. The implementer must resolve setup/start, or stop and report IAB unavailable/blocker. Without valid browser evidence, do not advance to a coherent UI checkpoint, human acceptance, or verifier final.

For user-visible UI only, before human acceptance the Coordinator freezes one canonical `coordinator_browser_evidence` packet for the exact `checkpoint_token`, `checkpoint_scope`, and `accepted_source_fingerprint`. It includes `browser_executor=coordinator/main`, exact `selector`, `browser_family`, checked URL, primary flow/view, viewport, result, artifact/tool evidence identifiers with SHA-256 hashes, and `automatic_fallback=false`; an approved Chrome/Edge exception additionally includes `exception_reason`, `user_approval_evidence`, and `matching_family`. The default packet records exact selector `iab` and family `iab`. The packet records `automatic_fallback=false`.
The canonical packet serialization explicitly includes the exact `checkpoint_token`, exact `checkpoint_scope`, and `accepted_source_fingerprint` fields; those bindings are hashed as part of `browser_evidence_hash`.
Canonical serialization is deterministic UTF-8 canonical JSON with sorted keys and no insignificant whitespace (or the exact equivalent rule); compute `browser_evidence_hash=SHA-256` over those bytes before human acceptance. The human reviews that exact `browser_evidence_hash`. Human acceptance and the immutable final acceptance envelope must repeat and bind to the same `checkpoint_token`, `checkpoint_scope`, `accepted_source_fingerprint`, and `browser_evidence_hash`; verifier recomputes the hash and requires every binding to match. The verifier recomputes `browser_evidence_hash` and rejects a mismatch. The final acceptance envelope is immutable and repeats the packet/hash plus human evidence explicitly referencing the same hash. Any packet field, revision, artifact, or hash change invalidates acceptance and requires a new packet/hash and human acceptance. Any checkpoint, scope, or source-fingerprint change also invalidates acceptance and requires a new packet/hash and human acceptance.
For user-visible UI only, `accepted_source_fingerprint` is an ephemeral canonical hash for the exact `checkpoint_scope`. Build deterministic sorted/null-safe records for every scoped path; staged/unstaged/untracked inventory entries are filtered to the exact `checkpoint_scope` and included only when they belong to that scope. Each record includes path/type/mode, HEAD identity or null, index identity or null, and working-tree content SHA-256 or null (including untracked). Serialize the record set as canonical UTF-8 JSON with sorted keys and no insignificant whitespace, then SHA-256 those bytes. Git status/diff are supplementary before/after evidence, not the fingerprint. Any HEAD/index/worktree/untracked/staged content change inside the exact `checkpoint_scope` invalidates acceptance. Out-of-scope verifier artifacts, logs, and screenshots are excluded from `accepted_source_fingerprint` and do not invalidate acceptance.
For non-UI checkpoints, after `checkpoint_token`/`checkpoint_scope` and implementer pause, no Coordinator browser packet, human UI acceptance, or `accepted_source_fingerprint` is required; run targeted tests, log analysis, and objective non-browser checks directly. If Coordinator/main cannot obtain the approved browser surface for user-visible UI, stop and report IAB unavailable/blocker; verifier-side browser unavailability alone is non-blocking when the valid packet and human acceptance are present.

1. Implementation/IAB loop: Coordinator/main is the browser executor and owner. It runs the default IAB or approved Chrome/Edge exception, records and freezes the canonical packet/hash before human acceptance, and returns visual/interactive findings to the same saved implementer loop for micro-adjustments. The implementer owns runnable setup/start, browser plan, and checkpoint state. Do not start completion review during the implementation/IAB loop.
2. Human UI/behavior acceptance: the Coordinator presents the exact candidate and its same-checkpoint packet to a real human/user. Only a real human/user may provide explicit combined UI acceptance for appearance and primary behavior. Human combined appearance and primary-behavior acceptance applies to the same Coordinator checkpoint and its `coordinator_browser_evidence` packet. The Coordinator records that packet and human acceptance as the final UI acceptance evidence, tied to `checkpoint_token`, `checkpoint_scope`, and `accepted_source_fingerprint`. The Coordinator records explicit human UI/behavior acceptance evidence tied to `checkpoint_token` and `checkpoint_scope`. The Coordinator records an ephemeral `accepted_source_fingerprint` at acceptance time for the exact `checkpoint_scope`. The canonical accepted_source_fingerprint procedure above is read-only evidence. The human reviews and accepts the exact `browser_evidence_hash`; the final acceptance envelope repeats the immutable packet/hash and human evidence referencing the same hash. AI agents may not proxy or assume this acceptance. Human feedback resumes the same saved implementer loop; do not start verifier or reviewer yet.
3. Verifier technical verification: for user-visible UI only, only after the Coordinator packet, explicit human UI/behavior acceptance, and a read-only accepted_source_fingerprint comparison, `verifier_luna` validates the same accepted checkpoint through the packet, recomputes `browser_evidence_hash`, verifies source before/after integrity, and runs targeted tests, logs, and objective non-browser checks. It does not acquire, share, or rerun the Coordinator IAB session. A mismatch invalidates the acceptance and returns to the same implementer/IAB loop and human gate. It does not decide subjective appearance or usability acceptance. Tool-generated artifacts outside the exact checkpoint scope do not invalidate the accepted source fingerprint.
4. Completion review: only after verifier passes, freeze, stage, and fingerprint the accepted scope before starting the Luna/max completion review. If verifier finds a problem or later source changes affect user-visible appearance or behavior, return to the same implementer/IAB loop and require combined human acceptance again before verifier. Purely non-user-visible verification artifact changes do not invalidate human acceptance.

### PR evidence

Video evidence is opt-in: the full PR evidence lifecycle runs only when the user explicitly requests
a video/evidence attachment for this delivery. If the user did not explicitly request video/evidence,
do not create, capture, inspect, reference, transform, or review any recording/video; do not call
`$pr-evidence-video`, run the evidence-only review, apply the privacy/artifact gate, upload evidence,
or block PR delivery; use the exact PR body text "Not requested (video evidence is opt-in)". If the
user explicitly requests video/evidence, require the
full PR evidence lifecycle: create the video with `$pr-evidence-video`, run the evidence-only review,
pass privacy/artifact checks, revalidate authorization/fingerprint/head, upload through the
browser/UI, and add the `## Visual Evidence` link. IAB functional verification and explicit human
UI/behavior acceptance remain mandatory for every user-visible UI change, whether or not video
evidence is requested. Non-user-visible configuration, documentation, and backend-only changes
remain outside both the UI IAB/human gate and the opt-in video path.
A later explicit request for video/evidence for the same delivery enters the same full lifecycle and
authorization/fingerprint/head/privacy/upload boundaries; there is no automatic fallback or pretend
upload.

The reusable `pr-evidence-video` skill is installed at ~/.codex/skills/pr-evidence-video and renders
only local, privacy-reviewed, muted evidence with a manifest when the user explicitly requests it.
Never install Remotion globally or in an application checkout. The current dotfiles/configuration
change itself is non-user-visible and uses `Not required (non-user-visible change)`.

## コマンド

### `setup.sh`

```bash
./setup.sh init
./setup.sh link
./setup.sh unlink
./setup.sh link-codex
./setup.sh unlink-codex
./setup.sh
```

- `init`: ホーム配下の設定を repo にコピー
- `link`: repo からホーム配下へシンボリックリンクを作成
- `unlink`: `link` で作成したシンボリックリンクを外し、最新のバックアップがあれば復元
- `link-codex`: Codex/agent/skill のみをホームへリンク（WSL2 向け）
- `unlink-codex`: `link-codex` のリンクを解除し、最新のバックアップがあれば復元
- 引数なし: `init` → `link`

### WSL2

Codex 0.115 以降の Linux 実行環境として WSL2 をサポートします。WSL1 は Linux の
`bubblewrap` 境界を利用できないため対象外です。Windows 側の `/mnt/c` 配下ではなく、WSL2
の Linux ホーム（例: `~/code/dotfiles`）へ clone してください。`/mnt/c` は DrvFS の権限・
symlink・mount の挙動が異なるため、`link-codex` は警告を出し、PR evidence renderer は安全な
FD/mount 境界を確立できない場合に evidence materialization 前に fail closed します。

PR evidence の Remotion 実行には次の Linux 側依存が必要です。

- `bubblewrap >= 0.10.0` (`bwrap`, with `--bind-fd`)
- `node` / `npm` / `npx`
- `ffmpeg` / `ffprobe`
- WSLg 等から起動できる、既にインストール済みの Linux Chrome または Chromium

セキュリティ境界に使う `bwrap`、`npm`、`npx` は caller の `PATH` ではなく、root-owned
system path の `/usr/bin/bwrap`、`/usr/bin/npm`、`/usr/bin/npx` を使用します。これらを
その場所に用意してください。

WSL2 では macOS の shell、Homebrew、デスクトップアプリ設定をリンクせず、Codex/agent/skill
だけを次で有効化します。

```bash
cd ~/code/dotfiles
./setup.sh link-codex
```

戻す場合は `./setup.sh unlink-codex` を実行します。既存の `init`、`link`、`unlink`、引数なし
の `init → link` は従来どおりです。

WSL2 環境の依存確認と契約テスト（実際の WSL2 runtime や browser render を成功済みとは
主張しません）のコマンド:

```bash
set -e
for tool in /usr/bin/bwrap /usr/bin/npm /usr/bin/npx; do test -x "$tool"; done
for tool in node ffmpeg ffprobe; do command -v "$tool" >/dev/null; done
/usr/bin/bwrap --help | grep -F -- --bind-fd >/dev/null
command -v google-chrome || command -v chromium || command -v chromium-browser
python3 -m unittest codex/skills/pr-evidence-video/tests/test_render_pr_evidence.py -v
```

Remotion の実行時は `bwrap --ro-bind / / --share-net` を使い、disposable run だけを writable
mount として FD-bound に渡します。`HOME`、`TMPDIR`、npm cache は run 内に固定されます。
`bwrap`、local browser、または安全な mount/descriptor 境界がない場合は、入力録画を run に
materialize せず停止します。

## Homebrew

macOS で Homebrew パッケージを復元する場合:

```bash
brew bundle --file=~/dotfiles/Brewfile
```

## ロールバック

macOS 側のリンクを戻す場合:

```bash
./setup.sh unlink
```

## 注意点

- `gh` の認証情報は [`hosts.yml`](./.gitignore) で ignore しており、この repo には含めません。
- `bin/` 配下のスクリプトは `pbpaste`, `pbcopy`, `osascript`, `open`, `say` など macOS のコマンドを前提にしています。
