---
name: web-performance-audit
description: Diagnose website and user-journey performance with real-user field data, HTTP transport evidence, and browser measurement. Use for Core Web Vitals, TTFB, caching, page-load, navigation, or evidence-backed performance audits. Do not use for generic frontend refactoring without a performance question.
---

# Web Performance Audit

Identify what users experience, locate the delay, and report only conclusions the evidence supports.

Field, transport, and browser measurements are complementary:

| Evidence | Best for | Does not prove |
|---|---|---|
| CrUX field data | Real-user impact over the reporting window | The technical cause |
| HTTP transport checks | Redirect, cache, cookie, and timing behavior from one vantage point | Rendering behavior or origin internals |
| Browser/trace data | Rendering, main-thread, request-chain, and journey diagnosis | Population-wide impact |

Do not let execution order decide which result “wins.” Reconcile differences by scope, population, time window, cache state, device, geography, and measurement method.

## Adapt to the runtime

Read [references/runtime-adapters.md](references/runtime-adapters.md) before executing tools when the agent environment or skill root is not already known.

- Discover available HTTP, browser, shell, and Python capabilities; do not assume a product-specific tool name exists.
- Use equivalent native, MCP, or command-line tools while preserving the measurement semantics in this skill.
- Resolve every bundled file relative to the directory containing this `SKILL.md`. Do not assume the current working directory is the skill directory.
- Do not stop an otherwise useful audit because one named tool is unavailable. Run the supported layers, state the coverage gap, and identify the tool or evidence needed to close it.
- Ask before installing software when installation is outside the user’s requested scope. Prefer existing or pinned local/temporary tooling over global mutable installs.

## Establish scope

Before measuring, determine or reasonably infer:

- The URL or origin and the specific journey being investigated.
- Whether the complaint concerns first load, repeat load, in-page interaction, client-side navigation, or server navigation.
- The audience/device context and whether a recent deployment may be absent from the field-data window.
- Whether authentication, personalization, consent state, locale, or experiment assignment can change the response.

Measure the complained-about journey. Direct navigation is a baseline, not a substitute for clicking the menu, submitting the form, opening the modal, or performing the interaction the user named.

## Safety and measurement boundaries

- Keep ordinary diagnostics low volume: three sequential baseline samples are normally enough. Do not turn cache or concurrency checks into a load test.
- Do not probe authenticated, private, or destructive journeys unless the user has placed them in scope and suitable test credentials/data are available.
- Never recommend shared caching for HTML until you have ruled out user-specific, authorization-specific, consent-specific, locale-specific, and experiment-specific content. Incorrect caching can expose data.
- Prefer existing browser tooling. Do not globally install an unpinned `@latest` package. If tooling is missing, use an existing local version or a pinned temporary/local installation when that mutation is within scope.
- Store API keys in the host environment or secret manager. Do not enumerate the environment, search `.env` files, print secret values, or commit captured responses containing secrets or private URLs.

## Evidence language

Keep three levels distinct in notes and reports:

- **Observation:** directly measured, such as `cache-status: DYNAMIC` or field LCP p75 of a stated value.
- **Inference:** best explanation supported by multiple observations, with alternatives considered.
- **Hypothesis:** plausible but unverified; state the next measurement needed.

Avoid converting correlation into cause. For example, field TTFB being much slower than a synthetic run is evidence of a population or operating-condition difference, not proof of origin saturation.

## Workflow

Use all three layers for a full audit. For a focused question, use only the layers needed to answer it.

### 1. Field impact

Read [references/field-data.md](references/field-data.md) before querying or interpreting CrUX or PageSpeed Insights.

1. When direct CrUX access is configured, query URL level first and use origin level as fallback. Without a key, run anonymous PSI and clearly label direct CrUX unavailable; do not label the entire field or PSI layer unavailable.
2. Segment by form factor only when the API has sufficient data. The CrUX API does not provide country segmentation or device traffic shares.
3. Report the collection period, scope, p75, and histogram distribution. Do not call p75 “typical.”
4. Treat missing URL- or origin-level data as a coverage limitation, not an error. Continue with transport and browser measurement.
5. Use field data to establish impact and prioritization. It cannot validate a deployment newer than its rolling window.

Use the bundled `scripts/fetch_google_data.py`, resolved from the skill root, for PSI and CrUX requests. PSI runs anonymously when `CRUX_API_KEY` is absent; direct CrUX requires it. The helper reads the key only from the process environment, keeps the value out of agent-generated arguments, sanitizes responses and errors, and refuses silent overwrites. If the user wants direct CrUX but the key is missing, provide the secure platform-specific setup command from `references/field-data.md` and explain that the agent must be relaunched from the configured environment. Then use `scripts/summarize_field_data.py` to parse captured JSON without silently assuming optional fields exist.

### 2. Transport behavior

Read [references/transport.md](references/transport.md) before drawing conclusions from `curl`, redirects, cookies, or cache headers.

1. Take at least three sequential samples and retain DNS, connect, TLS, TTFB, total time, status, final URL, and downloaded bytes.
2. Inspect every response in a redirect chain rather than merging headers from different hops.
3. Repeat the same eligible request to observe cache transitions, but first determine whether the response is intended and safe to cache.
4. Compare HTML and static-resource timings only as a diagnostic contrast. Separate commands do not guarantee the same connection or TLS session, and the paths may exercise different infrastructure.
5. Use response headers to form hypotheses. `DYNAMIC`, `BYPASS`, `Set-Cookie`, or a missing `Age` header is not automatically a fault.
6. Test session-lock serialization only when the stack and symptom make it plausible, and keep concurrency modest unless load testing is explicitly authorized.

Transport TTFB includes network, CDN, connection, redirect, and server effects. Do not label it “server time” without origin telemetry.

### 3. Browser and journey diagnosis

Read [references/browser-measurement.md](references/browser-measurement.md) before using Playwright, DevTools, Resource Timing, or long-task observers.

1. Establish a declared profile: viewport/device emulation, CPU/network throttling, cache state, browser version, vantage point, and sample count.
2. Use a cold-load trace for initial-load diagnosis and a separate interaction recording for the user’s journey.
3. For unstable lab metrics, run five samples and report the median plus range. Do not compare runs made under different profiles as if they were equivalent.
4. Capture FCP, LCP and its element/resource, CLS and shift sources, request chains, console failures, and main-thread work.
5. Report Lighthouse TBT when Lighthouse produced it. A custom sum of long-task blocking time is diagnostic only and must not be labeled TBT.
6. Prefer browser network or trace data for transferred bytes. Include the document and explain cache/service-worker state. Resource Timing totals alone may omit the document and expose zero sizes for cross-origin resources; if used, label the result a lower bound.
7. For INP or interaction latency, perform representative interactions. A page-load trace cannot establish real-user INP.
8. Use counterfactual blocking only for non-essential resources and clearly record what was blocked. Do not block authentication, consent, payment, security, or other functional dependencies casually.

If Playwright CLI is already available, the reusable observer scripts can be run with the following pattern. Replace `{skill-root}` with the resolved absolute skill directory. They intentionally report `observed_long_task_blocking_after_fcp_ms`, not TBT:

```text
playwright-cli open
playwright-cli run-code --filename="{skill-root}/scripts/playwright_observe.js"
playwright-cli goto "https://example.com/"
playwright-cli run-code "async page => { await page.waitForTimeout(8000); }"
playwright-cli --raw run-code --filename="{skill-root}/scripts/playwright_read.js"
```

With another browser tool, reproduce the same observer-before-navigation order and measurement caveats using its native actions. Adapt commands to the available shell rather than assuming GNU utilities are present.

## Reconcile evidence

When measurements differ, test explanations rather than selecting a winner:

- Field slower than lab: compare geography, form factor, network/device capability, cache state, redirects, time period, and traffic conditions. Origin queuing is one hypothesis that requires server telemetry or controlled load evidence.
- Lab slower than field: verify throttling, cold-cache assumptions, device emulation, extensions, and whether the tested path represents the field population.
- URL data differs from origin data: preserve both scopes; do not average or substitute them silently.
- Lab flags a problem while field data is good: describe the affected scenario or segment before deprioritizing it. Origin-level field data can hide a slow page.

Use counterfactual tests where safe: change one factor, repeat under the same profile, and report the observed delta. Do not claim savings from unrelated before/after runs.

## Deliverable

Lead with the answer and produce:

1. **Scope and method:** journey, date, vantage point, browser/profile, cache state, sample count, and field-data window.
2. **User impact:** field metrics by URL/origin and form factor, including coverage gaps.
3. **Ranked findings:** observation, likely mechanism, measured impact, confidence, and evidence source for each.
4. **Recommendations:** specific owner/action, expected effect, validation method, and safety caveats.
5. **Not the problem:** material causes tested and not supported by evidence.
6. **Limitations and next evidence:** origin telemetry, RUM segmentation, traces, or controlled tests still needed.

Do not manufacture a numeric saving. Use “unquantified” with a validation plan when the evidence supports a problem but not its exact cost.

## Quality gate

Before delivery, verify:

- Every cause is supported by evidence or labeled as a hypothesis.
- Field and lab scopes, windows, and profiles are visible beside their numbers.
- TBT came from a conforming tool; custom long-task totals use a different label.
- Byte totals include the document or are labeled as lower bounds.
- Cache recommendations account for personalization and authorization.
- The tested interaction matches the complaint.
- Recommendations are ranked by demonstrated user impact and confidence, not by generic best-practice checklists.
