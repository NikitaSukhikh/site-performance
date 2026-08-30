# Runtime adapters

Use this reference when running the skill in Codex, Claude Code, or another Agent Skills-compatible environment.

## Portable core

The audit method is tool-neutral. Map the required capability to tools already exposed by the runtime:

| Capability | Suitable implementations |
|---|---|
| HTTP timing and headers | `curl`/`curl.exe`, a shell HTTP client with phase timings, or an HTTP/MCP tool that exposes status, redirects, headers, and timing |
| Browser navigation and interaction | Chrome DevTools integration, Playwright CLI, a browser MCP server, or native browser automation |
| Performance diagnosis | DevTools/Lighthouse traces, browser performance APIs, or an equivalent trace analyzer |
| JSON parsing | Bundled Python parser, another JSON-capable runtime, or careful native inspection |

Preserve the semantic requirement when substituting tools. For example, an HTTP client that reports only total duration cannot replace a transport check that needs DNS, connection, TLS, and TTFB phases.

## Resolve bundled files

Treat all relative links in `SKILL.md` as relative to the skill root: the directory containing `SKILL.md`.

Before executing a bundled script:

1. Determine the absolute skill-root path using the host runtime’s skill metadata or filesystem location.
2. Join that root with the relative script path.
3. Pass the resolved path to Python, Node, or the browser tool.

Do not assume the agent’s current working directory is the installed skill directory. Claude Code may expose `${CLAUDE_SKILL_DIR}` for Claude-specific commands, but the shared instructions do not depend on that extension.

## Secret contract

Agent Skills frontmatter does not provide a portable secret-binding mechanism. This skill uses one runtime contract instead: the process executing `scripts/fetch_google_data.py` must receive `PSI_API_KEY` from its host environment or secret manager.

The agent learns the variable name from this skill; it does not discover the value. It must not enumerate environment variables, read `.env` files, inspect credential stores, or request the value in chat. Invoke the helper normally and let it check the exact variable internally. Hosted agents can use the API layer only when their platform injects the secret into the execution environment.

If `PSI_API_KEY` is unavailable, continue with other supported layers and mark Google API field data unavailable. Do not treat a missing secret as permission to search for one.

## Codex

Codex can load the standard `SKILL.md`, `references/`, and `scripts/` structure directly. Invoke explicitly with `$web-performance-audit` or allow automatic selection from the description. Keep Codex-specific UI metadata outside the portable core unless a separate distribution requires it.

## Claude Code

Claude Code can load the same standard package directly and invoke it as `/web-performance-audit`. The shared frontmatter intentionally omits Claude-only fields such as `context`, `disable-model-invocation`, and `model`, so the same package remains valid for claude.ai uploads, the Skills API, and non-Claude implementations.

The portable package also omits `allowed-tools`. That field is experimental in the Agent Skills specification and permission syntax varies by implementation. Let the host runtime apply its normal permission flow. A Claude-only distribution may add narrowly scoped permissions in a separate wrapper, not in this shared source.

## Other Agent Skills implementations

Use the host’s documented skill directory and invocation method. A conforming implementation should read the standard frontmatter and Markdown body, then load `references/` and `scripts/` as needed. If the host cannot execute scripts, follow their behavior using available tools and disclose that the bundled parser or observer was not run.

## Missing capabilities

- No field-data API access: continue with transport and browser layers; mark real-user impact as unknown.
- No browser automation: complete field and transport analysis; do not invent LCP elements, CLS sources, interaction latency, or page-weight totals.
- No phase-aware HTTP client: use browser navigation timing where available and label it browser-observed; do not claim DNS/TLS isolation.
- No Python runtime: parse the captured schema with another JSON tool, preserving missing-versus-zero distinctions.
