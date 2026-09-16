# Morphe Patch Bundle Selection — Research Report

Research only, 2026-09-16. No repo, config, or workflow files in `morphe-pipeline` were
modified. Sources: `api.github.com` / `gitlab.com/api/v4` repo metadata and releases,
raw READMEs, `patches-list.json` manifests pulled from release tags (not always `main`
HEAD — see gotchas below), and the community index `nvbangg/awesome-morphe`
(`data/repos.json`), which confirmed all 17 candidate repos are known/legitimate bundles
(none fabricated or mislabeled as a different ecosystem). `Jman-Github/ReVanced-Patch-Bundles`
and `morphe-patches.software` were also checked but return no machine-readable per-bundle
data (JS-rendered / generic aggregator pages) — treated as inconclusive, not negative,
signals.

**One pre-existing artifact changed my analysis materially:** `docs/proton-audit.md`
already in this repo is a prior source-level (not just metadata-level) audit of the
Proton VPN and Proton Pass patches. I did not redo that work — I cite its conclusions
under Proton VPN / Proton Pass below rather than re-deriving them from GitHub metadata
alone, since it inspected actual patch bytecode/source, which is stronger evidence than
anything obtainable from the API.

## Action item found during research (not fixed — out of scope)

`config/apps.json`'s `telegram` entry sets `"package": "org.telegram.messenger"` — the
**regular/native** Telegram package. This task requires the **Web** variant,
`org.telegram.messenger.web`, and rushiranpise's own `patches-list.json` tracks these as
two distinct, independently-versioned packages (`versionCode 70382` for native vs
`70389` for Web — not an alias). The bundle choice for Telegram below (rushiranpise) is
correct; the configured package ID is wrong and should be corrected separately.
`proton-pass`'s configured package (`proton.android.pass`) is already correct — the
task brief's assumed `me.proton.android.pass` was wrong, not the config.

---

## Brave Browser

**Chosen: [kveld9/kveld-morphe-patches](https://github.com/kveld9/kveld-morphe-patches)** (confirms current pipeline choice)

kveld9 is the only Brave candidate with actual privacy/debloat scope: 9 Brave-specific
patches — Block Brave Telemetry (P3A analytics, Stats pings, crash uploads, Variations
seed fetch), In-Product & Commercial Notification Optimizer, Disable Background/Periodic
Sync, Disable Battery Status API (fingerprinting vector), Locale PAK Slimmer, Native
Bloat Slimmer (strips WireGuard VPN / Android XR / Vision AI binaries), Skip First Run,
Brave Startup Performance Optimization, and Brave Origin. Maintenance is the most active
of any bundle checked in this whole report: 46 releases in ~4 weeks, pushed within the
last day, 0 open issues, and a same-day SIGSEGV crash fix on the TikTok side shows fast
turnaround when something does break.

**Alternatives lost:**
- **heval99/Heval-Morphe-Patches** — exactly 1 Brave patch ("Brave Origin", a premium
  feature-toggle unlock, no options, no privacy value). Never cut a stable release — only
  2 dev prereleases (`v1.1.0-dev.1/.2`, both 28 days old). README links point to a
  mismatched/renamed repo slug. Open issue #11 "bundle could not be found" from 2 days
  before this report.
- **bufferk/morphe-patches** — same single non-privacy "Brave Origin" patch. Latest
  stable release is 60 days old with an unresolved, unaddressed version-bump request
  (#30, open since Aug 31) plus two more stale open Brave bug reports (#18, #28).
- **dh6k/morphe-patches** — same single non-privacy "Brave Origin" patch (documents
  Brave Beta/Nightly variants, which is a nice touch, but they carry no meaningful patch
  content either). The machine-readable manifest actually has `version: null`
  (unpinned) for `com.brave.browser` despite the README claiming "Tested on 1.92.140" —
  the pin isn't enforced the way it's documented. Repo description states patches are
  "primarily for personal use."

**Target version:** `1.95.101` (strict single-version pin).

**Risk notes:** repo is young (created 2026-08-20, ~4 weeks old) and single-maintainer
(`kveld9` + `semantic-release-bot`). Strict pin breaks on any Brave update past
1.95.101 until bumped — true of every Brave candidate, not unique to kveld9. Repo's
`homepage` metadata field points to a stale `kveld9/brave-patches` slug (cosmetic,
unverified whether it resolves).

## TikTok

**Chosen: [kveld9/kveld-morphe-patches](https://github.com/kveld9/kveld-morphe-patches)** (confirms current pipeline choice)

Only TikTok candidate supporting both the Global package (`com.zhiliaoapp.musically`)
and Asia package (`com.ss.android.ugc.trill`) — both pinned to `46.9.3`, the newest pin
of the three candidates. 18 patches with real privacy/debloat depth: Unified Telemetry &
Tracker Silencer (ByteDance AppLog, APM/Heimdallr, AppsFlyer, Firebase), Clean Share URL,
Device Privacy Guard, Feed Ad Blocker, Feed Bloat & Distraction Blocker, Instant Launch &
Splash Blocker, Disable Push Notifications, Update Prompt Suppressor. 0 open issues,
consistent stable-tag release cadence (not just dev prereleases). Already the chosen
bundle for Brave — reusing it here keeps the pipeline's upstream-repo surface smaller
(a real but secondary tiebreaker, not the deciding factor).

**Alternatives lost:**
- **SysAdminDoc/hushfeed** — the largest catalog by far (80 patches, incl. a dedicated
  privacy/diagnostics section) and very actively released (5 releases in the 3 days
  before this report). Genuinely promising, but the repo is only 11 days old with zero
  track record beyond that window, and its pin (`46.2.3`) is older than kveld9's
  (`46.9.3`). Worth re-evaluating in a few months once it has maintenance history —
  not a "loser," just not enough evidence yet to bet the pipeline on it.
- **icysymmetra/tiktok-patches-for-morphe** — the most established by age (346 stars,
  active since May) but has lost momentum: the last 6 releases are all dev prereleases,
  no stable tag cut recently, and it carries a 70-issue open backlog against only 30
  patches — a maintainer-strain signal.

**Target version:** `46.9.3` (both packages, strict single-version pin).

**Risk notes:** same single-maintainer/strict-pin caveats as Brave. The recent same-day
SIGSEGV crash-and-fix (v1.27.2) shows this bundle ships fast and occasionally breaks
before it's caught — acceptable given the fast turnaround, but worth watching build
failures in CI rather than assuming green.

## Duolingo

**Chosen: [hoo-dles/morphe-patches](https://github.com/hoo-dles/morphe-patches)** (sole candidate — confirmed fit only with a real caveat, not rubber-stamped)

It is the only candidate and it does functionally support Duolingo: 3 patches — "Enable
Premium" (Super/MAX paywall bypass, configurable variant option), "Disable dynamic app
icon," "Enable debug mode" — all pinned to `6.95.4`. **But none of these are privacy or
debloat patches.** They are a paywall bypass plus two cosmetic/debug tweaks. Contrast:
other apps in this exact same bundle (CamScanner, SoundCloud, SuperChinese) get an
explicit "Disable telemetry" patch; Duolingo does not. Per this task's own evaluation
criterion #3 ("whether they match a privacy/debloat use case"), this is a genuine
mismatch, not a pass — flagging it plainly rather than rubber-stamping the only option.

**Target version:** `6.95.4` (strict single-version pin).

**Risk notes:**
- **Real operational gotcha:** the `main`-branch `patches-list.json` is stale and
  silently missing Duolingo entirely (it's still at internal version `1.22.0` while the
  actual latest release is `v1.44.0`). Any automated tooling must pull the manifest from
  the release tag (`.../v1.44.0/patches-list.json`) or `patches-bundle.json`, never
  `main` HEAD directly, or it will get wrong/incomplete data.
- Two open bugs — #615 (video calls don't start) and #611 (Settings/Shop infinite
  loading without the debug patch) — show ongoing break/fix churn against Duolingo's
  release cadence.
- Single maintainer (`hoo-dles`); repo overall is active (v1.44.0 shipped 9 days before
  this report) so not at abandonment risk, but Duolingo specifically gets no privacy
  treatment.
- **Recommendation to the pipeline owner:** decide explicitly whether premium-unlock is
  in scope for Duolingo. If the mandate is strictly privacy/debloat, there is currently
  no fit candidate for this app and it should be dropped rather than kept for the wrong
  reason.

## Pinterest

**Chosen: [browzomje/browzomje-patches](https://github.com/browzomje/browzomje-patches)**

This is genuinely close against SouBryan — said plainly, not smoothed over. browzomje
wins on the criterion this task weighs second (maintenance health): latest stable
release is 13 days old vs. SouBryan's 38 days and binarymend's 142 days. It also has the
broadest current patch count (28 Pinterest patches) with strong tracker/ad coverage
(AppsFlyer, Google Engage, third-party trackers/AdMob/Bugsnag/Firebase, Advertising ID
neutralization, tracking-param link sanitizing) plus practical debloat/download
utilities SouBryan intentionally omits. Low open-issue count (2). Flexible 4-version pin
list (`14.23.0`, `14.28.0`, `14.32.0`, `14.34.0`).

**Alternatives lost:**
- **SouBryan/pinterest-morphed** — a very close second, and arguably better-engineered:
  Pinterest-exclusive by design, the deepest single-purpose privacy/tracker list (11
  distinct trackers/SDKs disabled: Privacy Sandbox, AppsFlyer, Bugsnag, Firebase
  Analytics/Crashlytics/Performance, Google Ads SDK, Google Engage), and the widest
  documented version coverage (11 discrete versions, `14.20.0`–`14.30.0`, explicitly
  engineered per its README for fingerprint stability across releases). It loses purely
  on maintenance recency (last stable tag 38 days old, though commits continued to
  2026-08-27 with no new tag cut since) and narrower feature scope (no download tools).
  **If maintenance-recency weren't weighted ahead of patch depth, this pick would flip
  to SouBryan — stated as the explicit tiebreaker.**
- **binarymend/morphe-patches** — clearly stale: last release 142 days old (~4.7
  months), Pinterest pin frozen at `14.11.0` while the other two track `14.2x`–`14.34.x`
  (multiple minor versions behind), highest open-issue count (31) against a small
  4-app/11-patch bundle, and an explicit maintainer-bandwidth disclaimer in its README
  ("that kind of dedicated work requires compensation"). Only 3 Pinterest patches, none
  covering AppsFlyer/Firebase/Engage that the other two handle.

**Target version:** pinned per-patch to one of `14.23.0` / `14.28.0` / `14.32.0` /
`14.34.0` (flexible enumerated list, not a semver range).

**Risk notes:** single maintainer. **`config/apps.json` currently has SouBryan
configured for Pinterest, not browzomje** — this recommendation is a live suggestion to
switch, not a confirmation of existing config.

## Proton Pass

**Chosen: [rushiranpise/morphe-patches](https://github.com/rushiranpise/morphe-patches)** (sole candidate, confirms current pipeline choice)

Only one patch, "Unlock Unlimited Plan" — a premium-paywall bypass (forges the `Plan`
tier/limits object), not a privacy patch. Same category mismatch as Duolingo: fit for
purpose only if premium unlock is accepted as in-scope. The task brief's assumed package
name (`me.proton.android.pass`) is **wrong** — the bundle's actual manifest and this
repo's own `config/apps.json` both correctly use `proton.android.pass`.

**Deeper risk (from `docs/proton-audit.md`, already in this repo, source-level not
metadata-level):** the patch is local-only with no network/exfiltration risk, but it's
implemented as a **hardcoded absolute bytecode instruction index** (index 1 of
`Plan.<init>`) rather than a fingerprint-relative match. That means when Proton Pass
ships past `1.40.3`, this patch has a materially higher chance of silently mis-patching
(corrupted constructor) than a normal fingerprint-match patch, which would just fail
cleanly and get skipped.

**Target version:** `1.40.3` (strict single-version pin) — unchanged across the three
releases checked (`v1.20.0` Aug 23 → `v1.22.0` Sep 15), and no add/bump commit for
Proton Pass is traceable in `CHANGELOG.md` or via commit search. Stale, though 0 open
issues currently report it broken (per AppBrain, `1.40.3` was still upstream's current
build as of this report, per `docs/proton-audit.md`).

**Risk notes:** single point of failure — sole candidate, sole maintainer, and the
repo's own README states patches are "AI-generated... tested enough to not explode :p."
No fallback bundle exists if this one goes stale or the maintainer stops.

## Proton VPN

**Chosen: [hoo-dles/morphe-patches](https://github.com/hoo-dles/morphe-patches)** (confirms current pipeline choice)

Broader and better-tended patch set for this specific app: 4 patches (remove
server-switch delay, unlock LAN connections, unlock custom DNS, unlock split tunneling)
vs. rushiranpise's single consolidated patch. Per the existing source-level audit
(`docs/proton-audit.md`), hoo-dles' four patches are rated **"RELIABLE"** — small,
local, client-side-only edits to features gated purely client-side, no faked
entitlements, no spoofing infrastructure. 0 open issues specific to Proton VPN.

**Alternatives lost:**
- **rushiranpise/morphe-patches** — functionally similar (unlocks the same paid
  features) via a materially higher-risk mechanism: it forges the account's
  subscription-tier object and forces paid-feature flags to `true`, while silently
  keeping real connections on free servers — the UI actively shows "Plus" while the
  account stays functionally free. Rated **"CAUTION"** in `docs/proton-audit.md` for
  this reason (NetShield specifically may or may not silently no-op on a free
  connection — unverified). Within rushiranpise's own 4-app bundle, Proton VPN is also
  the most neglected app: its pin (`5.19.78.0`) hasn't moved since it was first added on
  2026-06-21 (~3 months), while Telegram Web and Amazon Shopping in the same bundle get
  bumped every release.
- **Paresh-Maheshwari/paresh-patches (GitLab)** — eliminated outright. **Self-declared
  archived and no longer maintained as of 2026-09-01** ("No new patches, app-version
  updates, bug fixes... will be accepted"), last CI pipeline on `main` **failed**, 88
  open issues with no maintainer response forthcoming. Its checked-in
  `patches-list.json` on `main` even shows post-archival drift (Proton VPN's "Disable
  telemetry" patch silently dropped, version bumped to an untested/unreleased
  `5.19.78.0`) that was never released or CI-validated — don't trust even its "live"
  state.

**Target version:** `5.19.43.0` (strict single-version pin).

**Risk notes:** per `docs/proton-audit.md`, this pin is roughly 2 months stale against
real-world Proton VPN releases (upstream had reportedly moved to the `5.20.x` line as of
the audit date, per web search, not independently re-verified here) — flagged there as
the main real risk, not the patch mechanism itself. hoo-dles bumps Proton VPN's pin on a
slow, manual, non-automated cadence relative to other apps in the same bundle — don't
assume this repo self-updates quickly for this specific app. Same `main`-branch
`patches-list.json` staleness gotcha noted under Duolingo applies here (same repo, same
bug — pull from the release tag or `patches-bundle.json` instead).

## Amazon Shopping

**Chosen: [rushiranpise/morphe-patches](https://github.com/rushiranpise/morphe-patches)**

8 substantive patches with real privacy/debloat value: disable search-suggestion
tracking, disable video autoplay, hide the Rufus AI tab, remove ads, open external links
in the system browser instead of in-app WebView, plus dark mode and price-history
utilities. Version pin is actively bumped (`32.13.2.100` → `32.17.0.100` between the
Aug 23 and Sep 15 releases checked) — the best-tended app of rushiranpise's four
evaluated apps. Only one open issue, and it's a feature request, not a bug.

**Alternative lost:**
- **RookieEnough/De-Vanced** — ships exactly one trivial Amazon Shopping patch ("Always
  allow deep-linking," no version pin at all because there's nothing substantive to
  break) inside a 61-patch, 22-app bundle whose real focus has clearly moved elsewhere
  (the README explicitly redirects TikTok maintenance credit to a different maintainer,
  signaling narrow apps like Amazon aren't a priority). It also carries an open,
  unresolved, four-month-old sign-in-breaking bug report (#41, filed 2026-05-04,
  untouched since Aug 18) with no maintainer response — a functional break with no fix
  in sight.

**Target version:** `32.17.0.100` (strict single-version pin).

**Risk notes:** same single-maintainer/"AI-generated" caveat as the rest of
rushiranpise's bundle. Amazon Shopping had the most historical bug-report churn of
rushiranpise's four evaluated apps (closed reports: login failures, price-history
display, dark-mode patch failures) — these did get fixed, so it reads as active
maintenance under real-world friction rather than neglect, but it's the most
break-prone of the four.

## Telegram (Web — `org.telegram.messenger.web`)

**Chosen: [rushiranpise/morphe-patches](https://github.com/rushiranpise/morphe-patches)** (confirms current pipeline choice, but see the config bug flagged at the top of this report)

13 patches specifically for the Web variant with real privacy/debloat value: Remove ads,
Disable auto-update (also strips proxy-sponsor-channel insertion), Hide typing
indicator, Anti-screenshot notification, plus Bypass integrity check (needed just to log
into a re-signed APK at all). Confirmed to correctly and *distinctly* track
`org.telegram.messenger.web` (versionCode `70389`) separately from both the regular
`org.telegram.messenger` (versionCode `70382`) and a third `org.telegram.plus` fork also
in this bundle — these are independently pinned, not aliased. Most actively maintained
of rushiranpise's four evaluated apps: bumped every release checked (`12.9.2` →
`12.10.0` → `12.10.1`). 0 open issues currently (one prior "broke after update" issue
was filed and resolved within the normal release cadence).

**Alternatives lost:**
- **Paresh-Maheshwari/paresh-patches (GitLab)** — eliminated outright, same reason as
  under Proton VPN: self-declared archived/dead as of 2026-09-01. (It's worth noting
  Paresh's own GitLab issue #77 was the source that first confirmed "Telegram" in that
  repo meant the Web variant, not native — useful corroborating evidence, but the repo
  itself is dead.)
- **WZSE/aapam-patches** — correctly targets `org.telegram.messenger.web` (verified:
  zero occurrences of the regular `org.telegram.messenger` package anywhere in its
  manifest), and its one Telegram patch ("Anti-disappearing media") uses a flexible
  2-version pin (`12.8.3` and `12.10.1`) rather than a strict single version — a nice
  property. But it is exactly one patch with no ad-removal, telemetry, or other
  privacy/debloat value; the repo's real focus is Prime Video Android TV and ZEE5,
  Telegram is incidental. 1 patch vs. rushiranpise's 13 is not close.

**Target version:** `12.10.1` (strict single-version pin).

**Risk notes:** same single-maintainer/"AI-generated" caveat as the rest of
rushiranpise's bundle. The Bypass integrity check patch means Telegram login itself
depends on this patch continuing to work — a regression there breaks the app outright,
not just a feature. **Separately and regardless of bundle choice: `config/apps.json`
currently configures `"package": "org.telegram.messenger"` (native) instead of
`org.telegram.messenger.web` — this needs to be corrected for the pipeline to actually
target the Web variant this task asked for.**

---

## Summary

| App | Chosen bundle | Target version | Confidence |
|---|---|---|---|
| Brave Browser | [kveld9/kveld-morphe-patches](https://github.com/kveld9/kveld-morphe-patches) | `1.95.101` | High |
| TikTok | [kveld9/kveld-morphe-patches](https://github.com/kveld9/kveld-morphe-patches) | `46.9.3` | High (re-evaluate hushfeed in a few months) |
| Duolingo | [hoo-dles/morphe-patches](https://github.com/hoo-dles/morphe-patches) | `6.95.4` | Low — sole candidate, and its patches are premium-unlock, not privacy/debloat |
| Pinterest | [browzomje/browzomje-patches](https://github.com/browzomje/browzomje-patches) | `14.23.0`/`14.28.0`/`14.32.0`/`14.34.0` | Medium — genuinely close call vs. SouBryan, tiebreaker stated |
| Proton Pass | [rushiranpise/morphe-patches](https://github.com/rushiranpise/morphe-patches) | `1.40.3` | Medium — sole candidate, premium-unlock only, fragile patch mechanism per prior audit |
| Proton VPN | [hoo-dles/morphe-patches](https://github.com/hoo-dles/morphe-patches) | `5.19.43.0` | High |
| Amazon Shopping | [rushiranpise/morphe-patches](https://github.com/rushiranpise/morphe-patches) | `32.17.0.100` | High |
| Telegram (Web) | [rushiranpise/morphe-patches](https://github.com/rushiranpise/morphe-patches) | `12.10.1` | High for bundle choice — but `config/apps.json` package ID needs fixing (see action item) |
