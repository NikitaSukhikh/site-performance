# Browser measurement

Use this reference for Playwright, Chrome DevTools, traces, performance observers, interaction testing, and transferred-byte claims.

## Tooling and profile

Prefer an already configured browser or Chrome DevTools integration. If Playwright CLI is available, check its version before use. Prefer a repository-local installation; do not globally install an unpinned latest release. When installation is needed, verify the current upstream package and pin the version used in the audit notes.

Declare:

- Browser and version.
- Vantage point.
- Viewport/device emulation and user agent.
- Network and CPU throttling.
- Cold or warm cache and service-worker state.
- Sample count and aggregation method.

Choose the profile from the user’s target audience or an explicitly stated test scenario. CrUX form-factor records do not reveal device traffic shares.

## Page-load observers

Install observers before navigation:

```text
playwright-cli open
playwright-cli run-code --filename=scripts/playwright_observe.js
playwright-cli goto "https://example.com/"
playwright-cli run-code "async page => { await page.waitForTimeout(8000); }"
playwright-cli --raw run-code --filename=scripts/playwright_read.js
```

The scripts collect FCP, the latest observed LCP, CLS excluding shifts after recent input, and long tasks. The long-task value is named `observed_long_task_blocking_after_fcp_ms`; it is not Lighthouse TBT because it has no TTI boundary and depends on when it is read.

For a standards-comparable TBT value, use Lighthouse or another conforming implementation and identify the tool/version.

LCP is not final until the page is hidden or user input terminates candidate reporting. A fixed wait is a sampling convention, not a guarantee; state the wait and check late-loading pages separately.

## Measure the journey

For navigation or interaction complaints:

1. Load the starting state under the declared cache profile.
2. Locate the same control a user operates.
3. Start the relevant trace or marks immediately before interaction.
4. Click/type/submit through the browser, not by replacing the interaction with `page.goto()`.
5. Stop after the visible completion condition, not merely the `load` event.
6. Repeat under the same conditions.

For INP-like diagnosis, exercise representative interactions and inspect event timing/main-thread work. Do not report a synthetic interaction as field INP; label it interaction latency under the stated lab profile.

## Network bytes

Prefer browser network logs, a DevTools trace, or CDP network events that include the navigation document and cross-origin transfers. Record whether bytes are encoded transfer size or decoded body size.

Do not present `performance.getEntriesByType('resource')` totals as complete page weight:

- The navigation document is not in the resource-entry list.
- Cross-origin size attributes may be zero without appropriate timing exposure.
- Cache hits and service workers can change or obscure transfer accounting.
- Entries can include resources outside the visible critical path.

If Resource Timing is the only available source, add the navigation entry where valid, count zero-sized entries, and label the total as a lower bound.

## Counterfactual tests

Blocking a resource and remeasuring can show causal impact when:

- The resource is non-essential to the measured journey.
- Baseline and counterfactual use identical profiles and sample counts.
- Functional and visual regressions are checked.
- The report names exactly what was blocked.

Never casually block authentication, consent, payment, fraud prevention, monitoring required by policy, or security controls.

## Common interpretation traps

- Field and lab numbers represent different populations and periods.
- TTFB includes more than server execution.
- A single fast run does not disprove tail latency.
- Origin-level good metrics do not prove every page is good.
- A lab regression can matter to a specific segment even when aggregate CrUX is good.
- Console errors indicate failed behavior or wasted work only after their request and execution impact is verified.
