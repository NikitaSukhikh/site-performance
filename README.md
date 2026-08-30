# Web Performance Audit Agent Skill

A portable [Agent Skills](https://agentskills.io) package for diagnosing website and user-journey performance with real-user field data, HTTP transport evidence, and browser measurement.

The same package is designed to work with:

- OpenAI Codex.
- Anthropic Claude Code, claude.ai skill uploads, and the Anthropic Skills API.
- Other agents that implement the Agent Skills specification and can load supporting files.

## Portability model

`SKILL.md` uses only `name` and `description`, the frontmatter intersection accepted by Codex, Claude, and the Agent Skills specification. Other fields are intentionally excluded from the shared source:

- Claude-only invocation, model, subagent, and hook settings do not belong in the shared source.
- Environment requirements stay in the body and this README because the standard `compatibility` field is not accepted by every current host validator.
- `allowed-tools` is omitted because it is experimental in the standard and permission syntax varies between hosts.
- Codex-specific UI metadata is not required to run the skill.

Each host keeps control of permissions and tool selection. The skill detects available HTTP, browser, shell, and Python capabilities and preserves the measurement semantics when substituting equivalent tools.

## Package contents

The repository keeps documentation at the root and the distributable skill in a directory whose name matches its standard frontmatter:

```text
site-performance/
|-- README.md
`-- web-performance-audit/
    |-- SKILL.md
    |-- references/
    |   |-- browser-measurement.md
    |   |-- field-data.md
    |   |-- runtime-adapters.md
    |   `-- transport.md
    `-- scripts/
        |-- fetch_google_data.py
        |-- playwright_observe.js
        |-- playwright_read.js
        |-- summarize_field_data.py
        |-- test_fetch_google_data.py
        `-- test_summarize_field_data.py
```

Install or upload the whole `web-performance-audit/` folder, not only `SKILL.md` and not the outer repository directory. The references and scripts are part of the skill.

## Install in Codex

Codex discovers skills from `.agents/skills` directories. Copy the package to one of these locations:

- User scope: `$HOME/.agents/skills/web-performance-audit/`
- Repository scope: `$REPO_ROOT/.agents/skills/web-performance-audit/`

Invoke it explicitly with `$web-performance-audit`, or let Codex select it automatically from the description.

See the current [OpenAI skill documentation](https://learn.chatgpt.com/docs/build-skills) for additional repository, admin, and system locations.

## Install in Claude Code

Copy the package to one of these locations:

- Personal scope: `~/.claude/skills/web-performance-audit/`
- Project scope: `.claude/skills/web-performance-audit/`

Invoke it with `/web-performance-audit`, or let Claude select it automatically from the description.

The standard frontmatter is also valid for claude.ai uploads and the Anthropic Skills API. See the current [Claude Code skills documentation](https://code.claude.com/docs/en/skills).

## Install in another agent

Place the entire `web-performance-audit` folder in the host’s documented skills directory or upload mechanism. The directory must contain `SKILL.md` at its root. Invocation syntax and automatic-selection behavior are host-defined.

If the host does not support bundled scripts, it can still follow the Markdown workflow using equivalent tools; it must disclose that the deterministic parser or browser observers were not run.

## Runtime capabilities

The skill can produce a partial audit when some capabilities are unavailable:

| Capability | Purpose | Required? |
|---|---|---|
| Internet access | Reach the target and public performance APIs | Yes for live external audits |
| Phase-aware HTTP client | Redirect, header, cache, DNS/TLS/TTFB checks | Needed for the transport layer |
| Browser automation or DevTools | Rendering, trace, interaction, and request diagnosis | Needed for the browser layer |
| Python 3.9+ | Run the secret-safe Google API client and PSI/CrUX parser | Recommended for the field/API layer; another secure host tool may substitute |
| Google API key | Query PSI and CrUX APIs | Needed only for their API-backed field/lab data |

Browser tooling may be a native host browser, Chrome DevTools integration, browser MCP server, or Playwright CLI. The skill does not require a particular agent connector.

## Optional Playwright CLI

Prefer browser tooling already supplied by the host. If Playwright CLI is available, check it with:

```bash
playwright-cli --version
```

If installation is necessary and authorized, follow the current [Microsoft Playwright CLI](https://github.com/microsoft/playwright-cli) documentation, prefer a pinned local or temporary version, and record the version in the audit. Do not globally install an unpinned `@latest` dependency as an automatic skill step.

## Google API key

For CrUX or PageSpeed Insights API calls, create a standard Google Cloud API key with the Chrome UX Report API and PageSpeed Insights API enabled. Restrict the key where practical and verify current quotas in Google Cloud.

Set it in the environment that launches the agent:

macOS, Linux, or Git Bash:

```bash
export PSI_API_KEY="PASTE_YOUR_KEY_HERE"
```

PowerShell:

```powershell
$env:PSI_API_KEY = "PASTE_YOUR_KEY_HERE"
```

Do not commit or print the key. It commonly travels in request query strings and may appear in verbose logs.

Agents do not discover the secret value automatically. The skill tells them the exact variable name, and the host supplies its value. The bundled client reads it internally; agents should not enumerate the environment, open `.env` files, inspect credential stores, or ask users to paste keys into chat.

Example commands contain no key argument:

```bash
python "web-performance-audit/scripts/fetch_google_data.py" check-key

python "web-performance-audit/scripts/fetch_google_data.py" crux \
  --origin "https://example.com" \
  --form-factor PHONE \
  --output crux-phone.json

python "web-performance-audit/scripts/fetch_google_data.py" psi \
  --url "https://example.com/" \
  --strategy MOBILE \
  --output psi-mobile.json
```

The client fails safely when `PSI_API_KEY` is absent, redacts it from API payloads and error messages, validates target URLs, limits response size, and refuses to overwrite evidence unless `--force` is supplied.

## Validate

From the repository root, run the portable Agent Skills validator when `skills-ref` is available:

```bash
skills-ref validate ./web-performance-audit
```

Run the bundled parser tests:

```bash
python -m unittest discover -s web-performance-audit/scripts -p "test_*.py" -v
python web-performance-audit/scripts/fetch_google_data.py --help
python web-performance-audit/scripts/summarize_field_data.py --help
```

Claude Code 2.1.233 or later can additionally validate an installed skills directory with `claude plugin validate`.

## Use

Codex example:

```text
Use $web-performance-audit to diagnose why product-list navigation is slow on https://example.com/. Compare first-load and menu-click behavior without load testing the site.
```

Claude Code example:

```text
/web-performance-audit Diagnose why product-list navigation is slow on https://example.com/. Compare first-load and menu-click behavior without load testing the site.
```

For another agent, invoke the installed `web-performance-audit` skill using its supported syntax or ask it naturally to use the skill.

Only test sites and journeys you are authorized to access. The skill defaults to low-volume diagnostics and treats authenticated or destructive flows as out of scope unless explicitly authorized.

## Specifications and authoritative documentation

- [Agent Skills specification](https://agentskills.io/specification)
- [OpenAI: build and install skills](https://learn.chatgpt.com/docs/build-skills)
- [Anthropic: Claude Code skills](https://code.claude.com/docs/en/skills)
- [Chrome UX Report API](https://developer.chrome.com/docs/crux/api)
- [PageSpeed Insights API](https://developers.google.com/speed/docs/insights/v5/get-started)
- [Microsoft Playwright CLI](https://github.com/microsoft/playwright-cli)
