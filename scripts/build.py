#!/usr/bin/env python3
"""Crude v1 Morphe autobuild orchestrator.

For each app in config/apps.json:
  1. resolve target version (regex against a bundle README, for now)
  2. skip if manifest.json says we already built that version
  3. fetch base APK from the configured source
  4. patch with morphe-cli (bundle given as repo URL — cli downloads the .mpp itself)
  5. publish to a GitHub release, update manifest.json

Everything is config-driven: adding an app = adding an entry, no code.
Swapping a bundle = editing the "bundle" URL. Nothing else.
"""

import argparse
import base64
import json
import os
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config" / "apps.json"
MANIFEST = ROOT / "manifest.json"
WORK = Path(os.environ.get("WORK_DIR", "/tmp/morphe-build"))
GH = os.environ.get("GH_TOKEN", "")
REPO = os.environ.get("GITHUB_REPOSITORY", "")


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
        ], capture_output=True, text=True)
        m = re.search(r"\d+(?:\.\d+){1,3}", out.stdout)
        if not m:
            sys.exit(f"could not resolve version for {app['id']} — no version in list-versions output:\n{out.stdout}")
        return m.group(0)
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
    src = app["source"]
    if src["type"] == "github_release_asset":
        tag = src["tag_template"].format(version=version)
        rel = gh_api(f"https://api.github.com/repos/{src['repo']}/releases/tags/{tag}")
        for a in rel.get("assets", []):
            if re.search(src["asset_regex"], a["name"]):
                download(a["browser_download_url"], dest)
                return
        sys.exit(f"no asset matching {src['asset_regex']} in {src['repo']}@{tag}")
    if src["type"] == "apkeep":
        apkeep_bin = find_apkeep(WORK / "apkeep")
        out_dir = dest.parent / "apkeep-out"
        out_dir.mkdir(exist_ok=True)
        run([apkeep_bin, "-a", f"{app['package']}@{version}", "-d", "apk-pure", out_dir])
        apks = sorted(out_dir.glob("*.apk"))
        if not apks:
            sys.exit(f"apkeep produced no .apk for {app['id']}@{version}")
        apks[-1].rename(dest)
        return
    sys.exit(f"unknown source type: {src['type']}")


def find_morphe_cli(dest: Path):
    rel = gh_api("https://api.github.com/repos/MorpheApp/morphe-cli/releases/latest")
    for a in rel.get("assets", []):
        if a["name"].endswith(".jar"):
            download(a["browser_download_url"], dest)
            return dest
    sys.exit("no .jar asset in morphe-cli latest release")


def run(cmd, **kw):
    print(f"  $ {' '.join(map(str, cmd))[:160]}")
    return subprocess.run([str(c) for c in cmd], check=True, **kw)


def build_app(app, cli_jar: Path):
    work = WORK / app["id"]
    work.mkdir(parents=True, exist_ok=True)
    version = resolve_version(app, cli_jar)

    manifest = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {}
    if manifest.get(app["id"], {}).get("version") == version:
        print(f"[{app['id']}] {version} already built — skipping")
        return

    print(f"[{app['id']}] building {app['name']} {version}")
    apk = work / f"{app['id']}-{version}.apk"
    fetch_apk(app, version, apk)

    ks_b64 = os.environ.get("KEYSTORE_BKS", "")
    if not ks_b64:
        sys.exit("KEYSTORE_BKS secret not set — run bootstrap workflow first")
    keystore = work / "sign.keystore"
    keystore.write_bytes(base64.b64decode(ks_b64))

    out = work / f"{app['id']}-{version}-morphe.apk"
    run([
        "java", "-jar", cli_jar, "patch",
        "-p", app["bundle"],
        "-o", out,
        "--keystore", keystore,
        "--keystore-password", os.environ["KEYSTORE_PASSWORD"],
        "--keystore-entry-alias", os.environ["KEYSTORE_ALIAS"],
        "--keystore-entry-password", os.environ["KEYSTORE_ENTRY_PASSWORD"],
        "--striplibs", app.get("arch", "arm64-v8a"),
        apk,
    ], cwd=work)

    run(["gh", "release", "create", f"{app['id']}-v{version}", out,
         "--title", f"{app['name']} {version} (morphe)",
         "--notes", f"Bundle: {app['bundle']}\nVersion: {version}"] + (["--repo", REPO] if REPO else ["--repo", "artbylmz/morphe-pipeline"]))

    manifest[app["id"]] = {"version": version, "bundle": app["bundle"]}
    MANIFEST.write_text(json.dumps(manifest, indent=2))
    print(f"[{app['id']}] done → release {app['id']}-v{version}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--app", default="all")
    args = ap.parse_args()

    apps = json.loads(CONFIG.read_text())["apps"]
    if args.app != "all":
        apps = [a for a in apps if a["id"] == args.app]
        if not apps:
            sys.exit(f"no app with id {args.app!r}")

    WORK.mkdir(parents=True, exist_ok=True)
    cli_jar = find_morphe_cli(WORK / "morphe-cli.jar")
    for app in apps:
        try:
            build_app(app, cli_jar)
        except subprocess.CalledProcessError as e:
            print(f"[{app['id']}] FAILED (exit {e.returncode}) — other apps continue", file=sys.stderr)


if __name__ == "__main__":
    main()
