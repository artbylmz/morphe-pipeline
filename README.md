# morphe-pipeline

Autobuild pipeline for [Morphe](https://github.com/MorpheApp/morphe-cli)-patched
Android APKs. Runs entirely on GitHub Actions (patching needs a JVM; this
never runs locally). Daily cron checks each configured app for a new upstream
version, patches it, and publishes a GitHub release.

## Add an app

Edit `config/apps.json`, one entry per app — no code changes needed:

```json
{
  "id": "brave",
  "name": "Brave Browser",
  "package": "com.brave.browser",
  "bundle": "https://github.com/kveld9/kveld-morphe-patches",
  "source": {
    "type": "github_release_asset",
    "repo": "brave/brave-browser",
    "asset_regex": "Bravemonoarm64\\.apk$",
    "tag_template": "v{version}"
  },
  "version": {
    "type": "readme_regex",
    "url": "https://raw.githubusercontent.com/kveld9/kveld-morphe-patches/main/README.md",
    "regex": "\\*\\*Current Target\\*\\*: `([0-9.]+)`"
  }
}
```

`bundle` is a patch-bundle repo URL (morphe-cli resolves the latest `.mpp`
itself). `source` says where to download the base APK from. `version` says
how to figure out which version the patch bundle currently targets.

## One-time setup

1. Run the `bootstrap` workflow (Actions tab → bootstrap → Run workflow). It
   generates a BKS signing keystore and uploads it as a build artifact.
2. Download the artifact, then set repo secrets:
   `KEYSTORE_BKS` (base64 contents of `morphe.keystore.b64`),
   `KEYSTORE_PASSWORD`, `KEYSTORE_ALIAS` (`morphe`), `KEYSTORE_ENTRY_PASSWORD`.
3. Delete the artifact/local keystore files once the secrets are set.

## Obtainium

Add the repo as an "App" source in Obtainium pointing at
`https://github.com/artbylmz/morphe-pipeline`, filtering releases by tag
prefix (e.g. `brave-`) if you track more than one app. Obtainium will pick up
new releases as the daily build publishes them.
