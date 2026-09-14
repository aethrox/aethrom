# Aethrom Panel (optional)

A local, read-only web panel for an Aethrom vault. One home page answers "where did I leave
off, what is open, is the engine actually running":

- **Engine strip** - last compile, last flush, last backup, and the health file. If anything is
  stale or failing, the strip says so in a plain sentence instead of hiding it.
- **Active threads** - from `850-Companion/Threads.md`, with how long each has been open.
- **Last session** and where it stopped.
- **Recent daily logs**, the **knowledge index**, and **connections** between concepts.
- A **note browser** with live search, plus backlinks on every note.

It refreshes itself every 20 seconds without losing your scroll position, your open sections,
or what you typed into the search box. Light and dark, with a System/Light/Dark switch.

**It never writes into the vault.** Every code path is read-only.

## Run

```bash
python panel/panel.py --vault ~/Documents/MyVault
```

Then open http://127.0.0.1:8420/ and stop with Ctrl+C.

```bash
python panel/panel.py --port 9000 --vault ~/Documents/MyVault
```

Requires Python 3 and the `markdown` package. Everything else is the standard library: no
framework, no npm, no build step, no configuration file.

```bash
pip install markdown        # or: uv pip install markdown
```

## Finding the vault

In this order:

1. `--vault <path>`
2. the `AETHROM_VAULT` environment variable
3. the sibling directory `../Aethrom`

Running from inside this clone, the sibling rule will not find your vault, so pass `--vault`
or export `AETHROM_VAULT` once:

```bash
export AETHROM_VAULT=~/Documents/MyVault     # Linux and macOS
setx AETHROM_VAULT "%USERPROFILE%\Documents\MyVault"   # Windows, new shells only
```

If no vault is found the panel prints the path it tried and exits 1, rather than serving an
empty page.

## Why it lives outside the vault

A build pipeline and generated HTML have no business sitting in a notes vault that backs
itself up every hour. The panel reads the vault from outside and writes nothing into it, so
the vault stays a vault.

## Safety

- Read-only. No code path writes, moves, or deletes anything under the vault.
- Every `path=`/`dir=` query is resolved and checked against the vault root. `..`, absolute
  paths, and anything under `.claude/` are rejected with a 404, and the attempted path is
  never reflected back into the page.
- `.claude/settings.local.json` can hold a live API key and is never read by any route. The
  only `.claude/` reads happen internally, off a hardcoded path, for the gitignored status
  files under `.claude/hooks/.state/` that the engine strip reports on.
- It binds to `127.0.0.1` only.

## Tests

```bash
python panel/test_panel.py
```

Standard-library asserts against a real vault: thread parsing, frontmatter parsing, wikilink
resolution, backlinks, state-file reads, and the path guard.

## Limitations

- Verified on Windows 11 with Python 3.11. The code is plain `http.server` and `pathlib` with
  no platform-specific calls, but Linux and macOS are untested.
- Search reads every note on each query. That measures 15-21 ms for 135 notes, so there is no
  cache; a vault an order of magnitude larger would want one.
- The serif is whatever the system provides from the stack (Charter, then Sitka Text, then
  Georgia). No webfont is downloaded, so the page looks slightly different per machine.
- One page, one process, one viewer. It is a personal tool, not a server.
