---
name: web-performance-audit
description: Diagnose why a website is slow using real-user field data, transport-layer inspection, and real-browser measurement. Use when asked why a site or page is slow, to audit Core Web Vitals, to investigate TTFB or caching problems, or to produce an evidence-backed performance report. Covers CrUX/PageSpeed Insights field data, curl header and cache analysis, and Chromium measurement via playwright-cli.
allowed-tools: Bash(curl:*) Bash(python3:*) Bash(npm:*) Bash(npx:*) Bash(playwright-cli:*)
---

# Web Performance Audit

Three measurement layers, run in order. Each answers a question the others cannot.

| Layer | Tool | Answers | Blind to |
|---|---|---|---|
| **1. Field** | CrUX via PSI API | What do *real users* actually experience? Which metric is genuinely broken? | Why. No causal detail. |
| **2. Transport** | `curl` | Is it cached? Why not? What headers, cookies, redirects? | Rendering, execution, real bytes |
| **3. Browser** | `playwright-cli` (Chromium) | LCP element, CLS, TBT, real transfer sizes, console errors | Real-user variance |

## The order matters

Run field data **first**. It tells you which problem to solve before you spend effort
characterising problems nobody has.

This is not a stylistic preference. In a real audit, lab measurement flagged 566ms of
Total Blocking Time and a layout-shift concern as significant findings. Field data
then showed INP at 100ms (93% "Good") and CLS at 0.00 (97% "Good") — those two lab
findings were hurting nobody. Meanwhile field TTFB was **5x worse** than the same
metric measured synthetically. Lab-first would have optimised the wrong things.

**Field data can invert lab priorities, not merely supplement them.**

---

# Layer 1 — Field data (CrUX)

## 1.1 API key

Both Google endpoints **require a key**. There is no working anonymous access:

- PSI API without a key → HTTP 429, `quota_limit_value: "0"` (disabled, not
  throttled — retrying never helps)
- CrUX API without a key → HTTP 403, `Method doesn't allow unregistered callers`

**Create an API key — not an OAuth client ID, not a service account.** Both of those
exist to act on behalf of a user or workload accessing private data. PSI and CrUX
serve public data about public URLs: there is no user to impersonate and no consent
to obtain, so OAuth adds ceremony and zero capability.

Google Cloud Console → create/select a project → APIs & Services → **enable both the
PageSpeed Insights API and the Chrome UX Report API** → Credentials → Create
credentials → API key. No billing account needed. Free tier is ~25,000
requests/day.

Restrict the key immediately — it travels in the URL query string:

- **API restrictions** → limit to PageSpeed Insights API + Chrome UX Report API.
- **Application restrictions** → IP addresses for a fixed server; None for local CLI.

```bash
export PSI_API_KEY="PASTE_KEY_HERE"
```

Never hardcode the key into scripts or commit it. Note it also lands in shell
history and any proxy log that records full URLs. If a key leaks, rotate it in the
Cloud Console — there is no other revocation path.

> **Deprecation — enable the CrUX API, don't rely on PSI for field data.**
> Google's documentation states it plans to discontinue including Chrome UX Report
> field data in the PSI response. When that lands, `loadingExperience` and
> `originLoadingExperience` disappear and PSI returns Lighthouse lab data only —
> quietly, with no error. Since Layer 1 exists precisely to override lab findings,
> treat **§1.3 (CrUX API) as the primary field-data source** and §1.2's
> `loadingExperience` block as a convenience that will stop working. Build any
> recurring audit against the CrUX API from the start.

## 1.2 PageSpeed Insights — field + lab in one call

PSI returns CrUX field data (`loadingExperience`, `originLoadingExperience`) *and* a
Lighthouse lab run in a single response.

```bash
TARGET="https://example.com/"
for STRAT in MOBILE DESKTOP; do
  curl -s -m 180 -G "https://www.googleapis.com/pagespeedonline/v5/runPagespeed" \
    --data-urlencode "url=$TARGET" \
    --data-urlencode "strategy=$STRAT" \
    --data-urlencode "key=$PSI_API_KEY" \
    -d category=PERFORMANCE \
    -o "psi_${STRAT}.json" -w "$STRAT http:%{http_code}\n"
done
```

Parse with `python3` (do not assume `jq` exists — it frequently doesn't):

```bash
python3 - <<'EOF'
import json, glob
NICE = {
 'LARGEST_CONTENTFUL_PAINT_MS':'LCP', 'FIRST_CONTENTFUL_PAINT_MS':'FCP',
 'CUMULATIVE_LAYOUT_SHIFT_SCORE':'CLS', 'INTERACTION_TO_NEXT_PAINT':'INP',
 'EXPERIMENTAL_TIME_TO_FIRST_BYTE':'TTFB',
}
for f in sorted(glob.glob('psi_*.json')):
    d = json.load(open(f))
    if 'error' in d:
        print(f, 'ERROR', d['error'].get('message', '')[:120]); continue
    print('\n===', f, '| final URL:', d.get('id'))
    for scope in ('loadingExperience', 'originLoadingExperience'):
        exp = d.get(scope)
        if not exp or 'metrics' not in exp:
            print(f'  {scope}: no field data'); continue
        print(f'  {scope}: overall={exp.get("overall_category")}')
        for k, m in exp['metrics'].items():
            dist = m.get('distributions', [])
            pct = [round(x.get('proportion', 0) * 100, 1) for x in dist]
            print(f'    {NICE.get(k,k):5} p75={m["percentile"]:>7} {m["category"]:<18} good/ni/poor={pct}')
    lh = d.get('lighthouseResult', {})
    sc = lh.get('categories', {}).get('performance', {}).get('score')
    if sc is not None: print(f'  lab performance score: {round(sc*100)}')
    for a in ('server-response-time','largest-contentful-paint','total-blocking-time',
              'cumulative-layout-shift','speed-index','unused-javascript','uses-long-cache-ttl'):
        au = lh.get('audits', {}).get(a)
        if au and au.get('displayValue'):
            print(f'    {a}: {au["displayValue"]}')
EOF
```

**Reading it:**

- `loadingExperience` is **URL-level**; `originLoadingExperience` is **origin-level
  (all pages)**. Low-traffic URLs often have no URL-level data — that is normal, not
  an error. Fall back to origin.
- `percentile` is **p75**: a quarter of users have it *worse*. Never describe p75 as
  "typical".
- `distributions` is the good / needs-improvement / poor split. **The distribution
  matters more than the p75.** "79% of users in Poor" is a far stronger statement
  than "p75 = 5.2s" and lands better with non-technical stakeholders.
- `category` is Google's verdict: `FAST` / `AVERAGE` / `SLOW`.
- CrUX aggregates a **28-day rolling window**. It will not reflect a fix you shipped
  last week. Never use it to validate a recent change.

## 1.3 CrUX API — segmentation the PSI call can't give you

Use this when you need per-country, per-device, or historical trend data.

```bash
curl -s -m 60 -X POST \
  "https://chromeuxreport.googleapis.com/v1/records:queryRecord?key=$PSI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"origin":"https://example.com","formFactor":"PHONE"}' -o crux.json

python3 - <<'EOF'
import json
d = json.load(open('crux.json'))
if 'error' in d: print('ERROR', d['error']); raise SystemExit
r = d['record']
print('key:', r['key'], '| period:', r.get('collectionPeriod', {}).get('lastDate'))
for name, m in r['metrics'].items():
    p75 = m.get('percentiles', {}).get('p75')
    bins = [round(b.get('density', 0) * 100, 1) for b in m.get('histogram', [])]
    print(f'  {name:45} p75={p75!s:>8}  dist={bins}')
EOF
```

Request body options: `origin` **or** `url` (not both); `formFactor` of `PHONE`,
`DESKTOP`, `TABLET`, or omit for all; `metrics` to limit the response. For trends
over time use `.../v1/records:queryHistoryRecord` with the same body shape.

**Caveat, stated honestly:** the parsing above is written against Google's documented
response schema. Verify the field paths against your first live response before
relying on them — schemas drift, and an audit built on a mis-parsed field is worse
than no audit.

## 1.4 No key available?

Public CrUX dashboards render the same underlying dataset. They are client-side apps,
so `curl` returns an empty shell — load them in the browser from Layer 3:

```bash
playwright-cli open
playwright-cli goto "https://<crux-dashboard-service>/<domain>"
sleep 12
playwright-cli --raw run-code --filename=readtext.js   # returns document.body.innerText
```

Treat third-party dashboards as **provisional**. They are an intermediary between you
and the source. Say so in the report, and verify with the API before quoting figures
to a client or in a commercial proposal.

---

# Layer 2 — Transport (`curl`)

## 2.1 Baseline, three runs

```bash
TARGET="https://example.com/"
for i in 1 2 3; do
  curl -s -o /dev/null -w "dns:%{time_namelookup} connect:%{time_connect} tls:%{time_appconnect} ttfb:%{time_starttransfer} total:%{time_total} size:%{size_download} code:%{http_code}\n" -L "$TARGET"
done
```

High `ttfb` with small `total - ttfb` → server/CDN; continue here. The reverse →
payload; go to Layer 3.

## 2.2 Headers — highest value per keystroke

```bash
curl -s -D - -o /dev/null -L "$TARGET" | head -60
```

Read for:

| Header | Meaning |
|---|---|
| `cf-cache-status` / `x-cache` / `x-vercel-cache` / `age` | **`BYPASS` or `DYNAMIC` on HTML is the single most valuable header finding.** |
| `set-cookie` | Any cookie on an HTML response prevents shared CDN caching. `PHPSESSID`, `wordpress_*`, session IDs are the usual offenders. |
| `cache-control` | Compare what the origin *asks* (`s-maxage`) with what the CDN *did*. Large `s-maxage` beside `BYPASS` = right intent, something vetoing it. |
| `cf-polished` / `cf-bgj` / `x-image-*` | **Image optimisation is active.** Every byte figure you take from curl is now wrong unless you send a browser `Accept` header. See 2.6. |
| `vary` | Over-broad `Vary` fragments the cache into uselessness. |
| `server`, `x-powered-by`, `x-redirect-by` | Fingerprint the stack instead of guessing. |

## 2.3 Prove the cache never warms, then isolate why

```bash
for i in 1 2 3; do for p in /page-a /page-b; do
  curl -s -D - -o /dev/null "https://example.com$p" \
    | grep -i "cf-cache-status\|^age:" | tr -d '\r' | tr '\n' ' '; echo "<- $p"
done; done

# cookieless request — does the origin still start a session?
curl -s -D - -o /dev/null -H "Cookie:" "https://example.com/page" \
  | grep -iE "cf-cache-status|set-cookie" | tr -d '\r'
```

One `MISS` is normal. Six requests across two URLs with zero `HIT` is a configuration
fault. A cookie set on a request that sent none is the bug.

## 2.4 Dynamic vs static TTFB — the money shot

```bash
curl -s -o /dev/null -w "html   ttfb:%{time_starttransfer}\n" "https://example.com/page"
curl -s -o /dev/null -w "static ttfb:%{time_starttransfer}\n" "https://example.com/asset.css"
```

Same domain, same TLS session, same network path. The only variable is whether the
edge served it. A 10x+ gap quantifies exactly what fixing the cache is worth, in one
line a non-technical stakeholder understands immediately.

## 2.5 Redirect chains

```bash
curl -s -L -o /dev/null -w "hops:%{num_redirects} final:%{url_effective} total:%{time_total}\n" "https://example.com/"
curl -s -o /dev/null -w "%{http_code} -> %{redirect_url}\n" "https://example.com/some-path/"
```

Check the bare domain, `www` vs apex, and every locale root (`/uk/`, `/us/`, `/en/`).
Each uncached redirect is a full origin round trip.

This step catches a class of fault no performance tool reports: a redirect that is
**fast and wrong**. A locale root 301ing to an unrelated page is a conversion bug
that never shows up in a timing metric.

## 2.6 Asset sizes — only if you cannot run a browser

If image optimisation is active (2.2), curl without a browser `Accept` header
measures bytes **no real user receives**:

```bash
curl -s -o /dev/null -w "%{size_download} %{content_type}\n" "$IMG"
curl -s -o /dev/null -w "%{size_download} %{content_type}\n" \
  -H "Accept: image/avif,image/webp,image/apng,*/*" "$IMG"
```

A CDN re-encoding on the fly can make these differ by **20x**. Even with the right
header, enumerating URLs from HTML sums every `srcset` variant, though a browser
downloads one. **Prefer Layer 3's `transferSize` for all byte figures.** Use this
section only when no browser is available, and label the numbers as approximate.

## 2.7 Session-lock serialisation

```bash
SID=$(curl -s -D - -o /dev/null "https://example.com/page" \
      | grep -i "set-cookie: PHPSESSID" | sed 's/.*PHPSESSID=\([^;]*\).*/\1/' | tr -d '\r')
s=$(date +%s.%N); for i in 1 2 3 4 5; do curl -s -o /dev/null "https://example.com/page?x=$i" & done; wait
echo "independent: $(echo "$(date +%s.%N)-$s" | bc)"
s=$(date +%s.%N); for i in 1 2 3 4 5; do curl -s -o /dev/null -H "Cookie: PHPSESSID=$SID" "https://example.com/page?y=$i" & done; wait
echo "shared session: $(echo "$(date +%s.%N)-$s" | bc)"
```

PHP's default file session handler holds an exclusive lock, serialising concurrent
requests from one visitor. A browser sends the cookie on every request; bare curl
does not. **Report the result even when it is dull** — naming a non-cause as a
non-cause is what makes the named cause credible.

## 2.8 Static HTML structure

```bash
curl -s "https://example.com/page" -o page.html
python3 - <<'EOF'
import re
h = open('page.html', encoding='utf-8', errors='ignore').read()
cut = h.lower().find('</head>')
head, body = h[:cut], h[cut:]
print("HEAD %.1f KB | BODY %.1f KB" % (len(head)/1024, len(body)/1024))
for name, seg in (("HEAD", head), ("BODY", body)):
    tags = re.findall(r'<script[^>]*src=[^>]*>', seg)
    blocking = [s for s in tags if 'defer' not in s and 'async' not in s]
    print(f"{name}: {len(tags)} src scripts, {len(blocking)} render-blocking")
    for s in blocking[:10]:
        print("   ->", re.search(r'src=["\']([^"\']+)', s).group(1)[-80:])
for b in re.findall(r'<script[^>]*>(.*?)</script>', h, re.S):
    if len(b) > 5000:
        print("inline %.1f KB: %s" % (len(b)/1024, b.strip()[:80].replace('\n', ' ')))
EOF
```

A `<head>` that is most of the HTML must fully parse before first paint. Large inline
blocks usually reveal a plugin injecting payload where it doesn't belong — e-commerce
plugins shipping full country/address tables onto content pages is a common find.

---

# Layer 3 — Browser (`playwright-cli`)

## 3.1 Setup

```bash
npm install -g @playwright/cli@latest
export PATH="$PATH:$HOME/.npm-global/bin"
playwright-cli --version
```

**Running as root fails** (`Running as root without --no-sandbox is not supported`).
There is no `--no-sandbox` flag on `open`. Use a config file:

```bash
mkdir -p .playwright && cat > .playwright/cli.config.json <<'EOF'
{ "browser": { "launchOptions": { "args": ["--no-sandbox", "--disable-dev-shm-usage"] } } }
EOF
playwright-cli open
```

Two gotchas that cost real time:

- `playwright-cli eval "<js>"` breaks on multi-line scripts and element accessors.
  **Use `run-code --filename=script.js` for anything non-trivial.**
- Always pass `--raw`, or you get the snapshot and generated-code preamble wrapped
  around your JSON.

## 3.2 Install buffered observers *before* navigation

LCP, CLS and longtask entries are **not** retrievable after the fact via
`getEntriesByType`. They need `PerformanceObserver` with `buffered: true`, installed
through `addInitScript` so it runs before page scripts on every navigation.

`init.js`:

```js
async page => {
  await page.addInitScript(() => {
    window.__m = { lcp: null, cls: 0, shifts: 0, lt: [] };
    try {
      new PerformanceObserver(l => { const e = l.getEntries(); window.__m.lcp = e[e.length-1]; })
        .observe({ type: 'largest-contentful-paint', buffered: true });
      new PerformanceObserver(l => { for (const e of l.getEntries()) if (!e.hadRecentInput) { window.__m.cls += e.value; window.__m.shifts++; } })
        .observe({ type: 'layout-shift', buffered: true });
      new PerformanceObserver(l => { for (const e of l.getEntries()) window.__m.lt.push(e.duration); })
        .observe({ type: 'longtask', buffered: true });
    } catch (e) { window.__m.err = String(e); }
  });
  return 'installed';
}
```

## 3.3 Throttle, or your numbers are fiction

An unthrottled datacenter run flatters the site badly. In one audit, a warm local run
reported **TBT 0ms, zero long tasks**; the same page cold and throttled reported
**TBT 566ms across 6 long tasks**. Unthrottled, you conclude there is no JavaScript
problem when there is a serious one.

`cold.js`:

```js
async page => {
  const cdp = await page.context().newCDPSession(page);
  await cdp.send('Network.enable');
  await cdp.send('Network.setCacheDisabled', { cacheDisabled: true });
  await cdp.send('Network.emulateNetworkConditions', {
    offline: false, latency: 40,
    downloadThroughput: 10 * 1024 * 1024 / 8,
    uploadThroughput: 3 * 1024 * 1024 / 8
  });
  await cdp.send('Emulation.setCPUThrottlingRate', { rate: 4 });
  return 'cache off, 10Mbps/40ms, CPU 4x';
}
```

CPU 4x approximates a mid-range Android. **Match the profile to the field data's
device split** — if CrUX shows 70% mobile, audit mobile. State the profile in every
report; an unstated throttle makes numbers meaningless.

## 3.4 Read the vitals

`read.js`:

```js
async page => page.evaluate(() => {
  const m = window.__m || {}, lcp = m.lcp;
  return JSON.stringify({
    fcp_ms: Math.round((performance.getEntriesByType('paint').find(p=>p.name==='first-contentful-paint')||{}).startTime||0),
    lcp_ms: lcp ? Math.round(lcp.startTime) : null,
    lcp_element: lcp && lcp.element ? lcp.element.tagName : null,
    lcp_url: lcp ? (lcp.url || null) : null,
    cls: Math.round((m.cls||0)*1000)/1000,
    shift_events: m.shifts,
    long_tasks: (m.lt||[]).length,
    TBT_ms: Math.round((m.lt||[]).reduce((s,d)=>s+Math.max(0,d-50),0)),
    longest_task_ms: (m.lt||[]).length ? Math.round(Math.max(...m.lt)) : 0
  });
})
```

```bash
playwright-cli run-code --filename=init.js
playwright-cli run-code --filename=cold.js
playwright-cli goto "https://example.com/page"; sleep 8
playwright-cli --raw run-code --filename=read.js
```

**`lcp_url` is the highest-value single field in the entire audit** — it names the
exact asset gating perceived load. Nothing in Layers 1 or 2 can produce it.

## 3.5 Real bytes, real request count

`net.js`:

```js
async page => page.evaluate(() => {
  const r = performance.getEntriesByType('resource'), by = {};
  let total = 0, decoded = 0;
  for (const e of r) {
    const t = e.initiatorType || 'other';
    by[t] = by[t] || { n: 0, bytes: 0 };
    by[t].n++; by[t].bytes += e.transferSize || 0;
    total += e.transferSize || 0; decoded += e.decodedBodySize || 0;
  }
  const top = k => r.slice().sort((a,b)=>k(b)-k(a)).slice(0,8)
    .map(e => ({ kb: Math.round((e.transferSize||0)/1024), ms: Math.round(e.duration), u: e.name.slice(-70) }));
  return JSON.stringify({ requests: r.length, transferKB: Math.round(total/1024),
    decodedKB: Math.round(decoded/1024), by,
    heaviest: top(e => e.transferSize||0), slowest: top(e => e.duration) }, null, 1);
})
```

`transferSize` is what actually crossed the wire — post-compression, post-CDN-image-
optimisation, and post-`srcset` selection (one variant per image). **This is the only
defensible page-weight figure.** It supersedes Layer 2.6 entirely.

Check `by` for surprises. Fonts are routinely the heaviest single asset on a page and
routinely overlooked because everyone is busy blaming images.

## 3.6 Measure the actual complaint

If the user says "navigating via the menu is slow," measure that, not the homepage.

`nav.js`:

```js
async page => {
  const pages = ['/', '/products', '/about', '/contact'];   // edit per site
  const out = [];
  for (const p of pages) {
    const t0 = Date.now();
    await page.goto('https://example.com' + p, { waitUntil: 'domcontentloaded' });
    const dcl = Date.now() - t0;
    await page.waitForLoadState('load').catch(()=>{});
    const load = Date.now() - t0;
    const m = await page.evaluate(() => {
      const n = performance.getEntriesByType('navigation')[0];
      const fcp = performance.getEntriesByType('paint').find(x=>x.name==='first-contentful-paint');
      const r = performance.getEntriesByType('resource');
      return { ttfb: Math.round(n.responseStart), fcp: fcp?Math.round(fcp.startTime):null,
               req: r.length, kb: Math.round(r.reduce((s,e)=>s+(e.transferSize||0),0)/1024) };
    });
    out.push({ page: p, ...m, dcl_ms: dcl, load_ms: load });
  }
  return JSON.stringify(out, null, 1);
}
```

Produces the per-page table that actually answers the question asked.

## 3.7 Console — free findings

```bash
playwright-cli --raw console
```

Thirty seconds of effort. Routinely surfaces broken third-party integrations that
load, fail, and deliver nothing but cost.

## 3.8 Other capabilities worth knowing

| Command | Use |
|---|---|
| `route "**/vendor/**" --status=404` | **Counterfactual testing** — block a script and re-measure to *prove* its cost rather than assert it. The strongest evidence in any audit. |
| `open --mobile` / `--device="iphone 15"` | Mobile viewport and UA; often a different asset set entirely. |
| `tracing-start` / `tracing-stop` | Full trace for main-thread flame graphs. |
| `requests` / `request N` | Per-request headers when Resource Timing isn't enough. |
| `cookie-clear` then `goto` | True first-visit behaviour. |

---

# Synthesis and reporting

## Reconciling the layers

Compare field TTFB against synthetic TTFB explicitly. A large gap is itself a
finding, not noise:

- **Field ≫ lab** — the origin degrades under concurrency. Synthetic single requests
  hit an idle server; real traffic queues, and queueing is non-linear. Common when
  the CDN is bypassing HTML: every visitor hits the application server. A bypass
  costing 1s idle can cost 5s under load.
- **Field ≈ lab** — the bottleneck is structural, not load-dependent.
- **Field ≪ lab** — your throttling is too aggressive for the real audience.

## Rules

1. **Lead with the distribution, not the p75.** "79% of users in Poor" beats
   "p75 = 5.2s".
2. **Lead with contrast, not absolutes.** "1.0s vs 0.075s on the same domain" lands;
   "1.0s TTFB" doesn't.
3. **Compare metrics against each other.** If FCP ≈ TTFB, users spend nearly all
   their wait before the first byte and *every* front-end optimisation is rounding
   error. Say so plainly.
4. **Demote lab findings the field contradicts.** A throttled CLS or TBT problem that
   CrUX scores "Good" is not worth engineering time. Say which findings you are
   deprioritising and why.
5. **Quote offending headers verbatim.** Three raw lines beat a paragraph.
6. **Rank fixes by measured impact.** If one outweighs all others combined, say so.
7. **Include a "not the problem" section.** Credit what is configured correctly. It
   proves the audit was a search rather than a script, and stops spend on the wrong
   thing.
8. **State throttling profile, vantage point, and data window** before any number.
9. **When a later layer contradicts an earlier one, the later layer wins — and
   publish the correction prominently.** An audit that visibly self-corrects is more
   trustworthy than one that doesn't.

## Permanent limitations

State these in every report:

- **CrUX is a 28-day rolling window.** It cannot validate a recent fix, and it will
  not exist at all for low-traffic origins or most individual URLs.
- **p75 hides the tail.** A quarter of users are worse off than any figure quoted.
- **Lab runs are one machine, one location, one network profile, usually one sample.**
  For contested numbers, run 5x and report the median.
- **No origin visibility.** Application-server saturation, slow queries, cache hit
  rates, plugin-level profiling — all invisible from outside. "~1s of server time"
  stays a black box without server-side profiling or logs.
- **`longtask` under-reports cross-origin work.** Attribution is limited; use a trace
  for detail.

---

# Condensed prompt

> Diagnose why `<URL>` is slow, focusing on `<the specific journey complained about>`.
> Measure, don't speculate. Three layers, in this order.
>
> **Layer 1 — field data.** Use the PageSpeed Insights API with `$PSI_API_KEY` for
> mobile and desktop, and the CrUX API for country/device segmentation. Report p75
> *and* the good/needs-improvement/poor distribution for TTFB, FCP, LCP, INP, CLS.
> Note the device split and use it to pick the lab throttling profile. Both APIs
> require a key — there is no anonymous access. Parse with `python3`, not `jq`.
>
> **Layer 2 — curl.** Three-run baseline splitting DNS/TCP/TLS/TTFB/total; full
> header dump reading cache-status, `set-cookie`, `cache-control`, `vary`, and any
> image-optimisation headers; repeated requests across several URLs to prove whether
> the CDN cache ever warms, plus a cookieless request to isolate any bypass;
> dynamic-vs-static TTFB contrast on the same domain; redirect chains from the bare
> domain, `www`/apex and every locale root; a parallel-request test with and without
> a shared session cookie; head-vs-body split with render-blocking script counts.
>
> **Layer 3 — playwright-cli.** Install it, work around the root sandbox restriction
> via config file, use `run-code --filename=` with `--raw` rather than inline `eval`.
> Install buffered `PerformanceObserver`s via `addInitScript` before navigating.
> Throttle via CDP (cache disabled, 10Mbps/40ms, CPU 4x) — unthrottled runs falsely
> report zero blocking time. Capture FCP, LCP with element and URL, CLS, long tasks,
> TBT; real `transferSize` totals by initiator type; heaviest and slowest resources;
> console errors; and a per-page table for the journey named above.
>
> Take all byte figures from Layer 3, never Layer 2 — CDN image optimisation and
> `srcset` mean curl measures bytes no user receives.
>
> Reconcile the layers explicitly: if field TTFB far exceeds synthetic TTFB, say so
> and explain it as load-dependent origin degradation. Demote any lab finding the
> field data scores as "Good".
>
> Deliver a ranked list of causes with the measured cost of each, a section naming
> what you checked that turned out *not* to be the problem, and an explicit statement
> of throttling profile, vantage point, data window and remaining blind spots.
