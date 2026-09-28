#!/usr/bin/env python3
"""Crude v1 Morphe autobuild orchestrator.

For each app in config/apps.json:
  1. resolve target version (preferably `morphe-cli list-versions` against the
     released bundle; README regexes drift ahead of releases)
  2. skip if manifest.json says we already built that version
  3. fetch base APK from the configured source
  4. patch with morphe-cli (bundle given as repo URL — cli downloads the .mpp itself)
     and refuse to release if no patch was actually applied
  5. publish to a GitHub release (tag gets -r2, -r3… if it already exists), update manifest.json
  6. on GitHub Actions: open/update a `build-failure` issue per failing app with its
     (redacted) log, and auto-close it once that app builds or is up to date again

Everything is config-driven: adding an app = adding an entry, no code.
Swapping a bundle = editing the "bundle" URL. Nothing else.
"""

import argparse
import base64
import hashlib
import json
import os
import re
import subprocess
import sys
import traceback
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config" / "apps.json"
MANIFEST = ROOT / "manifest.json"
WORK = Path(os.environ.get("WORK_DIR", "/tmp/morphe-build"))
GH = os.environ.get("GH_TOKEN", "")
REPO = os.environ.get("GITHUB_REPOSITORY", "")

APKMIRROR_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"


def apkmirror_fetch(url, referer=None):
    req = urllib.request.Request(url, headers={"User-Agent": APKMIRROR_UA})
    if referer:
        req.add_header("Referer", referer)
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode(), r.geturl()


def fetch_apkmirror(release_url: str, dest: Path):
    """release_url -> release page -> /download/?key=... -> download.php?id=&key= -> 302 to CDN -> apk."""
    page, _ = apkmirror_fetch(release_url)
    m = re.search(r'class="[^"]*downloadButton[^"]*"\s+href="([^"]+)"', page)
    if not m:
        sys.exit(f"apkmirror: no downloadButton link on {release_url}")
    key_url = "https://www.apkmirror.com" + m.group(1)

    key_page, _ = apkmirror_fetch(key_url, referer=release_url)
    m = re.search(r'id="download-link"[^>]*href="([^"]+)"', key_page)
    if not m:
        sys.exit(f"apkmirror: no download-link on {key_url}")
    final_url = "https://www.apkmirror.com" + m.group(1)

    req = urllib.request.Request(final_url, headers={"User-Agent": APKMIRROR_UA, "Referer": key_url})
    with urllib.request.urlopen(req, timeout=300) as r:
        # APKMirror serves either a plain .apk or a split-APK .apkm bundle;
        # the real extension only shows up in the resolved CDN URL.
        suffix = Path(r.geturl().split("?")[0]).suffix or ".apk"
        actual = dest.with_suffix(suffix)
        with open(actual, "wb") as f:
            while chunk := r.read(1 << 20):
                f.write(chunk)
    print(f"  downloaded {actual.name} ({actual.stat().st_size // 1024} KB) via apkmirror")
    return actual


def apkmirror_pick_variant(release_page: str, arch: str) -> str:
    """Pick a download page from an APKMirror *release* page's variants table.
    Prefers a plain APK over a split BUNDLE, then an exact arch match over universal."""
    page, _ = apkmirror_fetch(release_page)
    rows = []
    for row in re.split(r'<div class="table-row headerFont">', page)[1:]:
        href = re.search(r'href="(/apk/[^"]+-android-apk-download/)"', row)
        kind = re.search(r'class="apkm-badge[^"]*"[^>]*>(APK|BUNDLE)<', row)
        cells = [c.strip() for c in re.findall(r'<div class="table-cell[^"]*">([^<]+)</div>', row)]
        if href and kind and cells:
            rows.append((kind.group(1), cells[0], href.group(1)))
    ok = [r for r in rows
          if r[1] in ("universal", "noarch") or arch in [a.strip() for a in r[1].split("+")]]
    if not ok:
        # RuntimeError (not sys.exit) so fetch_apk falls back to apkeep
        raise RuntimeError(f"no {arch}/universal variant on {release_page} (found: {rows})")
    ok.sort(key=lambda r: (r[0] != "APK", r[1] != arch))
    kind, variant_arch, href = ok[0]
    print(f"  apkmirror variant: {kind} {variant_arch} -> {href}")
    return "https://www.apkmirror.com" + href


def gh_api(url, raw=False):
    req = urllib.request.Request(url)
    if GH:
        req.add_header("Authorization", f"Bearer {GH}")
    with urllib.request.urlopen(req, timeout=60) as r:
        data = r.read()
    return data if raw else json.loads(data)


def download(url, dest: Path, headers=None):
    req = urllib.request.Request(url)
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    if GH and "github.com" in url and "raw.githubusercontent" not in url:
        req.add_header("Authorization", f"Bearer {GH}")
    with urllib.request.urlopen(req, timeout=300) as r, open(dest, "wb") as f:
        while chunk := r.read(1 << 20):
            f.write(chunk)
    print(f"  downloaded {dest.name} ({dest.stat().st_size // 1024} KB)")


def resolve_version(app, cli_jar: Path):
    spec = app["version"]
    if spec["type"] == "fixed":
        return spec["version"]
    if spec["type"] == "readme_regex":
        text = gh_api(spec["url"], raw=True).decode()
        m = re.search(spec["regex"], text)
        if not m:
            sys.exit(f"could not resolve version for {app['id']} — regex didn't match")
        return m.group(1)
    if spec["type"] == "cli_list_versions":
        out = run([
            "java", "-jar", cli_jar, "list-versions",
            "--patches", app["bundle"],
            "-f", app["package"],
        ])
        m = re.search(r"Most common compatible versions:\s*\n\s*([0-9]+(?:\.[0-9]+)*)", out)
        if not m:
            sys.exit(f"could not resolve version for {app['id']} — no version in list-versions output")
        return m.group(1)
    sys.exit(f"unknown version source type: {spec['type']}")


def find_apkeep(dest: Path):
    if dest.exists():
        return dest
    rel = gh_api("https://api.github.com/repos/EFForg/apkeep/releases/latest")
    for a in rel.get("assets", []):
        if a["name"] == "apkeep-x86_64-unknown-linux-gnu":
            download(a["browser_download_url"], dest)
            dest.chmod(0o755)
            return dest
    sys.exit("no linux x86_64 asset in apkeep latest release")


def fetch_apk(app, version, dest: Path):
    """Returns the actual downloaded file path (may differ from dest's extension
    for apkeep, which can hand back a split-APK bundle: .xapk/.apkm/.apks)."""
    src = app["source"]
    if src["type"] == "github_release_asset":
        tag = src["tag_template"].format(version=version)
        rel = gh_api(f"https://api.github.com/repos/{src['repo']}/releases/tags/{tag}")
        for a in rel.get("assets", []):
            if re.search(src["asset_regex"], a["name"]):
                download(a["browser_download_url"], dest)
                return dest
        sys.exit(f"no asset matching {src['asset_regex']} in {src['repo']}@{tag}")
    if src["type"] == "apkeep":
        return fetch_apkeep(app, version, dest)
    if src["type"] == "apkmirror":
        try:
            if "release_page" in src:  # version-templated release page -> pick variant
                page = src["release_page"].format(version=version, version_dashed=version.replace(".", "-"))
                return fetch_apkmirror(apkmirror_pick_variant(page, app.get("arch", "arm64-v8a")), dest)
            return fetch_apkmirror(src["release_url"], dest)
        except Exception as e:
            print(f"  apkmirror failed ({e}), falling back to apkeep/apk-pure")
            return fetch_apkeep(app, version, dest)
    sys.exit(f"unknown source type: {src['type']}")


def fetch_apkeep(app, version, dest: Path):
    apkeep_bin = find_apkeep(WORK / "apkeep")
    out_dir = dest.parent / "apkeep-out"
    out_dir.mkdir(exist_ok=True)
    run([apkeep_bin, "-a", f"{app['package']}@{version}", "-d", "apk-pure", out_dir])
    found = sorted(out_dir.glob(f"{app['package']}@{version}.*"))
    if not found:
        sys.exit(f"apkeep produced no output for {app['id']}@{version}")
    final = dest.with_suffix(found[-1].suffix)
    found[-1].rename(final)
    return final


def find_morphe_cli(dest: Path):
    rel = gh_api("https://api.github.com/repos/MorpheApp/morphe-cli/releases/latest")
    for a in rel.get("assets", []):
        if a["name"].endswith(".jar"):
            download(a["browser_download_url"], dest)
            return dest
    sys.exit("no .jar asset in morphe-cli latest release")


# Secrets that must never reach an issue body (issues on a public repo are not
# masked the way Actions logs are). KEYSTORE_ALIAS is left out on purpose: it's
# "morphe" (see bootstrap.yml) and masking it would mangle every path in the log.
SECRET_ENV = ("KEYSTORE_PASSWORD", "KEYSTORE_ENTRY_PASSWORD", "KEYSTORE_BKS", "GH_TOKEN", "GITHUB_TOKEN")


def redact(text: str) -> str:
    for k in SECRET_ENV:
        v = os.environ.get(k, "").strip()
        if len(v) >= 6:
            text = text.replace(v, f"<{k}>")
    return text


class Tee:
    """stdout wrapper: everything printed also lands in the current app's buffer."""
    def __init__(self, stream):
        self.stream, self.buf = stream, None

    def write(self, s):
        if self.buf is not None:
            self.buf.append(s)
        return self.stream.write(s)

    def __getattr__(self, name):
        return getattr(self.stream, name)


def run(cmd, cwd=None, on_line=None):
    """Run a command, streaming stdout+stderr live through sys.stdout (so it is
    captured for failure reports). Returns the full output; raises
    CalledProcessError with that output on a non-zero exit."""
    print(f"  $ {redact(' '.join(map(str, cmd)))[:160]}", flush=True)
    proc = subprocess.Popen([str(c) for c in cmd], cwd=cwd, text=True, errors="replace",
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    lines = []
    for line in proc.stdout:
        sys.stdout.write(line)
        lines.append(line)
        if on_line:
            on_line(line)
    sys.stdout.flush()
    out = "".join(lines)
    if proc.wait():
        raise subprocess.CalledProcessError(proc.returncode, cmd, output=out)
    return out


APPLIED_RE = re.compile(r"INFO: Applied: ")


def run_patch(cmd, cwd):
    """Run `morphe-cli patch` and return how many patches it reported as applied.
    morphe-cli exits 0 even when every patch was skipped as incompatible (it then
    just re-signs the stock APK), so the exit code alone can't tell a patched
    build from a vanilla one."""
    applied = 0

    def count(line):
        nonlocal applied
        if APPLIED_RE.search(line):
            applied += 1
    run(cmd, cwd=cwd, on_line=count)
    return applied


def repo_slug():
    return REPO or "artbylmz/morphe-pipeline"


def release_exists(tag: str) -> bool:
    r = subprocess.run(["gh", "release", "view", tag, "--repo", repo_slug(), "--json", "tagName"],
                       capture_output=True, text=True)
    return r.returncode == 0


def free_release_label(app, version) -> str:
    """`<version>` if tag <id>-v<version> is free, else `<version>-r2`, `-r3`, …
    (a rebuild forced by dropping the manifest entry must not die on
    'a release with the same tag name already exists')."""
    label = version
    n = 1
    while release_exists(f"{app['id']}-v{label}"):
        n += 1
        label = f"{version}-r{n}"
    return label


def build_app(app, cli_jar: Path):
    work = WORK / app["id"]
    work.mkdir(parents=True, exist_ok=True)
    version = resolve_version(app, cli_jar)

    manifest = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {}
    prev = manifest.get(app["id"], {})
    # Entries written before "package" was recorded count as the same package.
    if prev.get("version") == version and prev.get("package", app["package"]) == app["package"]:
        print(f"[{app['id']}] {version} already built — skipping")
        return "up to date"

    label = free_release_label(app, version)
    print(f"[{app['id']}] building {app['name']} {version} (release {app['id']}-v{label})")
    apk = fetch_apk(app, version, work / f"{app['id']}-{version}.apk")

    ks_b64 = os.environ.get("KEYSTORE_BKS", "")
    if not ks_b64:
        sys.exit("KEYSTORE_BKS secret not set — run bootstrap workflow first")
    keystore = work / "sign.keystore"
    keystore.write_bytes(base64.b64decode(ks_b64))

    out = work / f"{app['id']}-{label}-morphe.apk"
    applied = run_patch([
        "java", "-jar", cli_jar, "patch",
        "-p", app["bundle"],
        "-o", out,
        "--keystore", keystore,
        "--keystore-password", os.environ["KEYSTORE_PASSWORD"],
        "--keystore-entry-alias", os.environ["KEYSTORE_ALIAS"],
        "--keystore-entry-password", os.environ["KEYSTORE_ENTRY_PASSWORD"],
        "--striplibs", app.get("arch", "arm64-v8a"),
        *[x for name in app.get("disable_patches", []) for x in ("-d", name)],
        apk,
    ], cwd=work)

    # Never publish an unpatched APK: that's what shipped as tiktok-v47.1.3
    # (bundle README bumped to 47.1.3 before the released .mpp did, so all 50
    # patches were skipped as incompatible and the stock app got released).
    min_applied = app.get("min_patches_applied", 1)
    print(f"  {applied} patch(es) applied (minimum {min_applied})", flush=True)
    if applied < min_applied:
        sys.exit(f"only {applied} patch(es) applied to {version} (need >= {min_applied}) — "
                 f"bundle probably doesn't support this version yet; refusing to release a vanilla APK")

    run(["gh", "release", "create", f"{app['id']}-v{label}", out,
         "--title", f"{app['name']} {label} (morphe)",
         "--notes", f"Bundle: {app['bundle']}\nVersion: {version}\nPatches applied: {applied}",
         "--repo", repo_slug()])

    manifest[app["id"]] = {"version": version, "bundle": app["bundle"], "package": app["package"]}
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"[{app['id']}] done → release {app['id']}-v{label}")
    return f"built {app['id']}-v{label} ({applied} patches)"


ISSUE_LABEL = "build-failure"
LOG_TAIL_LINES = 250
ISSUE_BODY_MAX = 60000  # GitHub caps issue/comment bodies at 65536 chars


def run_url():
    rid = os.environ.get("GITHUB_RUN_ID")
    server = os.environ.get("GITHUB_SERVER_URL", "https://github.com")
    return f"{server}/{repo_slug()}/actions/runs/{rid}" if rid else "(local run)"


def gh_quiet(*args):
    return subprocess.run(["gh", *args, "--repo", repo_slug()], capture_output=True, text=True)


def open_failure_issue(title):
    r = gh_quiet("issue", "list", "--label", ISSUE_LABEL, "--state", "open",
                 "--limit", "100", "--json", "number,title")
    if r.returncode:
        raise RuntimeError(f"gh issue list failed: {r.stderr.strip()}")
    return next((i["number"] for i in json.loads(r.stdout) if i["title"] == title), None)


def issue_title(app_id):
    return f"[build-failure] {app_id}"


def report_failure(app_id, summary, log):
    """Open (or comment on) one issue per failing app. Repeats of the same error
    are not re-commented, so a daily failure doesn't spam notifications."""
    sig = hashlib.sha1(re.sub(r"/tmp/\S+", "", summary).encode()).hexdigest()[:12]
    marker = f"<!-- failure-sig:{sig} -->"
    tail = "".join(log).splitlines()[-LOG_TAIL_LINES:]
    text = redact("\n".join(tail)).replace("```", "``\u200b`")
    body = (f"{marker}\n**App:** `{app_id}`\n**Run:** {run_url()}\n\n"
            f"**Error:** {redact(summary)}\n\n"
            f"<details><summary>Last {len(tail)} log lines</summary>\n\n```\n{{LOG}}\n```\n</details>\n\n"
            f"_Opened automatically by build.py; closed automatically once `{app_id}` builds again._")
    room = ISSUE_BODY_MAX - len(body)
    body = body.replace("{LOG}", text[-room:] if len(text) > room else text)

    title = issue_title(app_id)
    num = open_failure_issue(title)
    if num is None:
        gh_quiet("label", "create", ISSUE_LABEL, "--color", "B60205",
                 "--description", "Opened automatically when a pipeline build fails", "--force")
        r = gh_quiet("issue", "create", "--title", title, "--label", ISSUE_LABEL, "--body", body)
        print(f"  opened issue: {r.stdout.strip() or r.stderr.strip()}")
        return
    r = gh_quiet("issue", "view", str(num), "--json", "body,comments")
    seen = json.loads(r.stdout) if r.returncode == 0 else {"body": "", "comments": []}
    latest = (seen["comments"][-1]["body"] if seen["comments"] else seen["body"]) or ""
    if marker in latest:
        print(f"  issue #{num} already has this error — not commenting again")
        return
    gh_quiet("issue", "comment", str(num), "--body", body)
    print(f"  commented on issue #{num} (error changed)")


def resolve_failure(app_id, status):
    num = open_failure_issue(issue_title(app_id))
    if num is not None:
        gh_quiet("issue", "close", str(num), "--comment", f"Fixed: {status}. Run: {run_url()}")
        print(f"  closed issue #{num} ({app_id}: {status})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--app", default="all")
    ap.add_argument("--report", action="store_true",
                    default=os.environ.get("GITHUB_ACTIONS") == "true",
                    help="open/close GitHub issues for failures (default: on in GitHub Actions)")
    args = ap.parse_args()

    apps = json.loads(CONFIG.read_text())["apps"]
    if args.app != "all":
        apps = [a for a in apps if a["id"] == args.app]
        if not apps:
            sys.exit(f"no app with id {args.app!r}")

    tee = Tee(sys.stdout)
    sys.stdout = tee
    WORK.mkdir(parents=True, exist_ok=True)
    results = {}

    # Pipeline-level step (morphe-cli download); a failure here fails every app.
    tee.buf = []
    try:
        cli_jar = find_morphe_cli(WORK / "morphe-cli.jar")
    except BaseException as e:
        summary = f"could not fetch morphe-cli: {e}"
        print(traceback.format_exc())
        if args.report:
            report_failure("pipeline", summary, tee.buf)
        sys.exit(summary)
    if args.report:
        resolve_failure("pipeline", "morphe-cli fetched")

    for app in apps:
        tee.buf = []
        try:
            status = build_app(app, cli_jar) or "ok"
            results[app["id"]] = (True, status)
        except subprocess.CalledProcessError as e:
            cmd = redact(" ".join(map(str, e.cmd)))[:200]
            results[app["id"]] = (False, f"command failed (exit {e.returncode}): `{cmd}`")
        except SystemExit as e:
            results[app["id"]] = (False, str(e.code))
        except Exception as e:
            print(traceback.format_exc())
            results[app["id"]] = (False, f"{type(e).__name__}: {e}")
        ok, status = results[app["id"]]
        if not ok:
            print(f"[{app['id']}] FAILED: {status} — other apps continue")
        log = tee.buf
        tee.buf = None
        if args.report:
            try:
                (resolve_failure if ok else report_failure)(app["id"], status, *([] if ok else [log]))
            except Exception as e:  # reporting must never take the build down
                print(f"  (issue reporting for {app['id']} failed: {e})")

    print("\n== summary ==")
    for app_id, (ok, status) in results.items():
        print(f"  {'OK  ' if ok else 'FAIL'} {app_id}: {status}")
    failed = [a for a, (ok, _) in results.items() if not ok]
    if failed:
        # Non-zero so the run shows red; the workflow still commits the manifest.
        sys.exit(f"{len(failed)} app(s) failed: {', '.join(failed)}")


if __name__ == "__main__":
    main()
