#!/usr/bin/env python3
"""Local read-only web panel for the Aethrom Obsidian vault.

Single file, stdlib http.server + markdown. Never writes into the vault: every
filesystem access below is a read. The vault is found in this order: --vault,
then $AETHROM_VAULT, then the sibling directory ../Aethrom (next to this
folder). If it's not there the panel refuses to start rather than serving an
empty shell.

Routes:
    /                       home page (engine status, threads, last session,
                             recent daily logs, knowledge index, browser entry)
    /note?path=<rel>        render one vault note
    /browse?dir=<rel>       list a folder (empty dir = vault root)
    /search?q=<term>        live substring search over title + body
    /connections            list knowledge/connections entries
    /partial?view=home      inner <main> HTML for home(), for live refresh
    /partial?view=search    just the results <ul>, for search-as-you-type
    /style.css              this folder's stylesheet

Usage:
    python panel.py
    python panel.py --vault D:/Aethrom
"""

from __future__ import annotations

import argparse
import datetime
import html
import http.server
import json
import os
import re
import sys
import time
import urllib.parse
from pathlib import Path

import markdown

HERE = Path(__file__).resolve().parent
PORT = 8420

WIKILINK = re.compile(r"\[\[([^\]|]+?)(?:\|([^\]]+))?\]\]")
MD_EXTENSIONS = ["tables", "fenced_code", "sane_lists", "attr_list"]

def top_folders(vault: Path) -> list:
    """Whatever folders the vault actually has. The optional ones (200-Goals, 400-Vault,
    700-Body, 800-Mind) are a per-install choice, so a fixed list would be wrong."""
    return sorted(
        (e.name for e in vault.iterdir() if e.is_dir() and not e.name.startswith(".")),
        key=lambda n: (n[0].isascii(), n.lower()),
    )


def memory_dir(vault: Path) -> Path | None:
    """The companion memory folder, found by globbing '🔮 850-*'.

    Never hardcode the companion name: install renames this folder to
    '🔮 850-<companion>', so a fixed name would break every vault but one.
    This mirrors memory_dir() in .claude/hooks/_common.py."""
    matches = sorted(vault.glob("🔮 850-*"))
    return matches[0] if matches else None


def resolve_vault(arg: str | None) -> Path:
    return Path(arg or os.environ.get("AETHROM_VAULT") or (HERE.parent / "Aethrom")).expanduser()


# ---------- path safety ----------

def safe_join(vault: Path, rel: str) -> Path | None:
    """Resolve a vault-relative path and refuse anything that escapes the vault
    or reaches into .claude/. Rejects '..', absolute/drive paths, unconditionally."""
    if rel is None:
        return None
    rel = rel.strip().replace("\\", "/")
    if not rel:
        return vault
    if rel.startswith("/") or ":" in rel:
        return None
    parts = [p for p in rel.split("/") if p not in ("", ".")]
    if any(p == ".." for p in parts):
        return None
    if parts and parts[0] == ".claude":
        return None
    vault_r = vault.resolve()
    target = vault_r.joinpath(*parts)
    try:
        resolved = target.resolve()
        resolved.relative_to(vault_r)
    except (ValueError, OSError):
        return None
    return resolved


# ---------- state files (.claude/hooks/.state/, not routed, gitignored, may be absent) ----------

def read_state(vault: Path, name: str) -> dict:
    p = vault / ".claude" / "hooks" / ".state" / name
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def read_state_text(vault: Path, name: str) -> str:
    p = vault / ".claude" / "hooks" / ".state" / name
    try:
        return p.read_text(encoding="utf-8").strip()
    except (FileNotFoundError, OSError):
        return ""


# ---------- parsing helpers ----------

def parse_frontmatter(text: str) -> tuple[dict, str]:
    meta: dict = {}
    if not text.startswith("---"):
        return meta, text
    end = text.find("\n---", 3)
    if end == -1:
        return meta, text
    block = text[3:end].strip("\n")
    body = text[end + 4:].lstrip("\n")
    for line in block.splitlines():
        if ": " not in line:
            continue
        key, _, value = line.partition(": ")
        value = value.strip()
        if value.startswith("[") and value.endswith("]"):
            value = [v.strip() for v in value[1:-1].split(",") if v.strip()]
        meta[key.strip()] = value
    return meta, body


def build_note_map(vault: Path) -> dict:
    """basename (lower, no extension) -> vault-relative path, one walk per request."""
    m: dict[str, str] = {}
    for root, dirs, files in os.walk(vault):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for f in files:
            if f.endswith(".md"):
                rel = os.path.relpath(os.path.join(root, f), vault).replace("\\", "/")
                m[f[:-3].lower()] = rel
    return m


def linkify(body: str, note_map: dict) -> str:
    def repl(m: re.Match) -> str:
        target = m.group(1).strip()
        alias = (m.group(2) or target).strip()
        hit = note_map.get(target.lower())
        if hit:
            href = "/note?path=" + urllib.parse.quote(hit)
            return '<a href="' + href + '">' + html.escape(alias) + "</a>"
        return '<span class="wikilink-missing">' + html.escape(alias) + "</span>"

    return WIKILINK.sub(repl, body)


def render_body(body: str, note_map: dict) -> str:
    return markdown.markdown(linkify(body, note_map), extensions=MD_EXTENSIONS)


def status_class(status_text: str) -> str:
    t = status_text.lower()
    if "blocked" in t or "🔴" in status_text:
        return "bad"
    if "open" in t or "🟡" in status_text or "paused" in t:
        return "warn"
    return "ok"


def status_label(status_text: str) -> str:
    """ACTIVE / OPEN / CLOSED. No emoji, no date tail - the days count says that."""
    head = status_text.split(" - ")[0]
    words = re.sub(r"[^A-Za-z]", " ", head).split()
    return words[0].upper() if words else "UNKNOWN"


DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")


def days_open(status_text: str) -> int | None:
    m = re.search(r"created (\d{4}-\d{2}-\d{2})", status_text)
    if not m:
        m = DATE_RE.search(status_text)
    if not m:
        return None
    try:
        d = datetime.date.fromisoformat(m.group(1))
    except ValueError:
        return None
    return (datetime.date.today() - d).days


def split_sections(text: str) -> dict:
    """Split on top-level '## ' headings into {heading: body}."""
    out: dict[str, str] = {}
    for part in re.split(r"\n## ", "\n" + text)[1:]:
        title, _, body = part.partition("\n")
        out[title.strip()] = body
    return out


def _parse_thread_blocks(body: str) -> list:
    items = []
    for block in re.split(r"\n### Thread: ", "\n" + body)[1:]:
        lines = block.split("\n")
        name = lines[0].strip()
        status_text = ""
        first_line = ""
        for line in lines[1:]:
            stripped = line.strip()
            if stripped.startswith("**Status:**"):
                status_text = stripped[len("**Status:**"):].strip()
            elif stripped and not first_line and not stripped.startswith("#"):
                first_line = stripped
        items.append({
            "name": name,
            "status": status_text,
            "status_class": status_class(status_text),
            "first_line": first_line,
            "days_open": days_open(status_text),
        })
    return items


def parse_threads(text: str) -> dict:
    sections = split_sections(text)
    active = _parse_thread_blocks(sections.get("Active Threads", ""))
    closed = _parse_thread_blocks(sections.get("Closed Threads", ""))
    return {"active": active, "closed": closed, "closed_count": len(closed)}


def parse_last_session(text: str) -> tuple[str, str]:
    title_m = re.search(r"^## Session: (.+)$", text, re.M)
    title = title_m.group(1).strip() if title_m else ""
    stop_m = re.search(r"## Where it stopped\n(.*?)(?:\n## Previous|\Z)", text, re.S)
    stop = stop_m.group(1).strip() if stop_m else ""
    return title, stop


def parse_daily(text: str) -> tuple[int, str]:
    sessions = len(re.findall(r"^### Session \(", text, re.M))
    todo = ""
    m = re.search(r"## To-Dos\n+(.*?)(?:\n##|\Z)", text, re.S)
    if m:
        todo = next((l.strip() for l in m.group(1).split("\n") if l.strip()), "")
    return sessions, todo


# ---------- home page sections ----------

def human_time(iso: str) -> str:
    """ISO timestamp to a readable one. Falls back to the raw string."""
    try:
        return datetime.datetime.fromisoformat(iso).strftime("%d %b %H:%M")
    except (ValueError, TypeError):
        return str(iso)


def render_engine_strip(health: dict, compile_state: dict, flush: dict,
                         backup_ok_text: str, backup_failed_text: str) -> str:
    bad = False
    lines = []
    now = time.time()

    if not health:
        bad = True
        lines.append("Health check has not run yet.")
    elif health.get("error") != "ok" or (now - health.get("ts", 0)) > 86400:
        bad = True
        lines.append("Health check is stale or reporting a problem: " + str(health.get("error", "unknown")) + ".")
    else:
        lines.append("Health: " + str(health.get("component", "?")) + " ok.")

    if compile_state:
        status = compile_state.get("last_status", "?")
        lines.append("Last compile: " + human_time(compile_state.get("last_run", "unknown")) + " (" + str(status) + ").")
        if status != "ok":
            bad = True
    else:
        bad = True
        lines.append("Compile has not run yet.")

    if flush:
        lines.append("Last flush: " + str(flush.get("detail", "?")) + ".")
    else:
        lines.append("No flush recorded yet.")

    if backup_failed_text:
        bad = True
        lines.append("Backup failing: " + backup_failed_text.splitlines()[0] + ".")
    elif backup_ok_text:
        lines.append("Last backup: " + backup_ok_text + ".")
    else:
        bad = True
        lines.append("No backup recorded yet.")

    cls = " bad" if bad else ""
    body = "".join("<p>" + html.escape(l) + "</p>" for l in lines)
    return '<div class="engine-strip' + cls + '">' + body + "</div>"


def render_thread(t: dict) -> str:
    days = "" if t["days_open"] is None else f' &middot; {t["days_open"]}d open'
    return (
        '<div class="thread"><p><b>' + html.escape(t["name"]) + '</b> - '
        + '<span class="status status-' + t["status_class"] + '">' + status_label(t["status"]) + '</span></p>'
        + '<p class="meta">' + html.escape(t["first_line"]) + days + '</p></div>'
    )


def render_threads(threads: dict) -> str:
    parts = [render_thread(t) for t in threads["active"]]
    closed = threads.get("closed", [])
    bad_closed = [t for t in closed if t["status_class"] == "bad"]
    rest_closed = [t for t in closed if t["status_class"] != "bad"]
    parts.extend(render_thread(t) for t in bad_closed)
    n = len(rest_closed)
    summary = str(n) + " closed thread" + ("" if n == 1 else "s")
    if rest_closed:
        parts.append('<details><summary>' + summary + '</summary>' + "".join(render_thread(t) for t in rest_closed) + '</details>')
    elif not bad_closed:
        parts.append('<p class="meta">' + summary + '.</p>')
    return "".join(parts)


def home_body(vault: Path) -> str:
    note_map = build_note_map(vault)

    health = read_state(vault, "health.json")
    compile_state = read_state(vault, "compile-state.json")
    flush = read_state(vault, "last-flush.json")
    backup_ok = read_state_text(vault, "backup_ok")
    backup_failed = read_state_text(vault, "backup_failed")
    engine_html = render_engine_strip(health, compile_state, flush, backup_ok, backup_failed)

    mem = memory_dir(vault)
    threads_path = (mem / "Threads.md") if mem else vault / "Threads.md"
    threads_html = ""
    if threads_path.is_file():
        threads_html = render_threads(parse_threads(threads_path.read_text(encoding="utf-8")))

    session_html = ""
    session_path = (mem / "Last-Session.md") if mem else vault / "Last-Session.md"
    if session_path.is_file():
        title, stop = parse_last_session(session_path.read_text(encoding="utf-8"))
        session_html = "<h3>" + html.escape(title) + "</h3>" + render_body(stop, note_map)

    daily_dir = vault / "daily"
    daily_html = ""
    if daily_dir.is_dir():
        files = sorted(daily_dir.glob("*.md"), reverse=True)[:7]
        rows = []
        for f in files:
            sessions, todo = parse_daily(f.read_text(encoding="utf-8"))
            href = "/note?path=" + urllib.parse.quote("daily/" + f.name)
            rows.append(
                '<p><a href="' + href + '">' + html.escape(f.stem) + "</a> &middot; "
                + str(sessions) + " session" + ("" if sessions == 1 else "s")
                + (" &middot; " + html.escape(todo[:90] + ("..." if len(todo) > 90 else "")) if todo else "")
                + "</p>"
            )
        visible, rest = rows[:2], rows[2:]
        daily_html = "".join(visible)
        if rest:
            n = len(rest)
            daily_html += (
                '<details><summary>' + str(n) + " more log" + ("" if n == 1 else "s") + '</summary>'
                + "".join(rest) + '</details>'
            )

    knowledge_html = ""
    index_path = vault / "knowledge" / "index.md"
    if index_path.is_file():
        _, body = parse_frontmatter(index_path.read_text(encoding="utf-8"))
        table_at = body.find(chr(10) + "| ")  # skip the title and preamble
        knowledge_html = render_body(body[table_at:] if table_at != -1 else body, note_map)

    folders_html = "".join(
        '<li><a href="/browse?dir=' + urllib.parse.quote(f) + '">' + html.escape(f) + "</a></li>"
        for f in top_folders(vault)
    )

    body = f"""
<h1>Aethrom Panel</h1>
<section id="engine-strip">{engine_html}</section>
<section id="threads"><h2>Active Threads</h2>{threads_html or '<p class="meta">No Threads.md found.</p>'}</section>
<section><h2>Last Session</h2>{session_html or '<p class="meta">No Last-Session.md found.</p>'}</section>
<section id="daily-logs"><h2>Recent Daily Logs</h2>{daily_html or '<p class="meta">No daily logs yet.</p>'}</section>
<section><h2>Knowledge Index</h2>{knowledge_html or '<p class="meta">No knowledge/index.md found.</p>'}</section>
<section>
  <h2>Vault</h2>
  <form action="/search" method="get">
    <input type="search" name="q" placeholder="Search notes" aria-label="Search notes">
  </form>
  <p><a href="/connections">Connections</a></p>
  <ul class="folders">{folders_html}</ul>
</section>
"""
    return body


def home(vault: Path) -> str:
    return page("Aethrom Panel", home_body(vault), home_link=False)


# ---------- note / browse / search pages ----------

def find_backlinks(vault: Path, target_rel: str, note_map: dict) -> list:
    """Notes whose wikilinks resolve to target_rel. Reuses WIKILINK and note_map."""
    out = []
    for root, dirs, files in os.walk(vault):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for f in files:
            if not f.endswith(".md"):
                continue
            p = Path(root) / f
            rel = str(p.relative_to(vault)).replace("\\", "/")
            if rel == target_rel:
                continue
            try:
                text = p.read_text(encoding="utf-8")
            except OSError:
                continue
            for m in WIKILINK.finditer(text):
                if note_map.get(m.group(1).strip().lower()) == target_rel:
                    meta, _ = parse_frontmatter(text)
                    out.append((meta.get("title") or p.stem, rel))
                    break
    return out


def note_page(vault: Path, rel: str) -> tuple[int, str]:
    target = safe_join(vault, rel)
    if target is None or not target.is_file() or not target.name.endswith(".md"):
        return 404, page("Not found", "<h1>Not found</h1>")
    note_map = build_note_map(vault)
    text = target.read_text(encoding="utf-8")
    meta, body = parse_frontmatter(text)
    title = meta.get("title") or target.stem
    body_html = render_body(body, note_map)
    rel_norm = str(target.relative_to(vault.resolve())).replace("\\", "/")
    crumb = " / ".join(html.escape(p) for p in rel_norm.split("/")[:-1])

    backlinks = find_backlinks(vault, rel_norm, note_map)
    if backlinks:
        items = "".join(
            '<li><a href="/note?path=' + urllib.parse.quote(r) + '">' + html.escape(t) + "</a></li>"
            for t, r in backlinks
        )
        backlinks_html = (
            '<details><summary>Backlinks (' + str(len(backlinks)) + ')</summary>'
            + '<ul class="browse-list">' + items + '</ul></details>'
        )
    else:
        backlinks_html = '<details><summary>Backlinks (0)</summary><p class="meta">No notes link here.</p></details>'

    return 200, page(title, "<h1>" + html.escape(title) + "</h1>" + body_html + backlinks_html, crumb)


def browse_page(vault: Path, rel: str) -> tuple[int, str]:
    target = safe_join(vault, rel)
    if target is None or not target.is_dir():
        return 404, page("Not found", "<h1>Not found</h1>")
    entries = sorted(target.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
    items = []
    vault_r = vault.resolve()
    for e in entries:
        if e.name.startswith("."):
            continue
        rel_e = str(e.relative_to(vault_r)).replace("\\", "/")
        if e.is_dir():
            items.append('<li><a href="/browse?dir=' + urllib.parse.quote(rel_e) + '">' + html.escape(e.name) + "/</a></li>")
        elif e.suffix == ".md":
            items.append('<li><a href="/note?path=' + urllib.parse.quote(rel_e) + '">' + html.escape(e.name) + "</a></li>")
    rel_norm = "" if target == vault_r else str(target.relative_to(vault_r)).replace("\\", "/")
    body = "<h1>" + html.escape(rel_norm or "Vault") + '</h1><ul class="browse-list">' + "".join(items) + "</ul>"
    return 200, page(rel_norm or "Vault", body)


def search_results(vault: Path, q: str) -> list:
    ql = q.lower()
    results = []
    for root, dirs, files in os.walk(vault):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for f in files:
            if not f.endswith(".md"):
                continue
            p = Path(root) / f
            try:
                text = p.read_text(encoding="utf-8")
            except OSError:
                continue
            meta, note_body = parse_frontmatter(text)
            title = meta.get("title") or p.stem
            if ql in title.lower() or ql in note_body.lower():
                rel = str(p.relative_to(vault)).replace("\\", "/")
                results.append((title, rel))
    return results


def highlight_match(title: str, q: str) -> str:
    """Escape title and wrap the (case-insensitive) matching substring of q in <mark>."""
    if not q:
        return html.escape(title)
    idx = title.lower().find(q.lower())
    if idx == -1:
        return html.escape(title)
    before, hit, after = title[:idx], title[idx:idx + len(q)], title[idx + len(q):]
    return html.escape(before) + "<mark>" + html.escape(hit) + "</mark>" + html.escape(after)


def render_search_results(results: list, q: str = "") -> str:
    items = "".join(
        '<li><a href="/note?path=' + urllib.parse.quote(rel) + '">' + highlight_match(title, q) + "</a></li>"
        for title, rel in results
    )
    return '<ul class="browse-list" id="search-results">' + items + "</ul>"


def search_page(vault: Path, q: str) -> str:
    q = q.strip()
    body = "<h1>Search</h1>"
    body += '<form action="/search" method="get"><input type="search" name="q" value="' \
            + html.escape(q, quote=True) + '" placeholder="Search notes"></form>'
    if not q:
        return page("Search", body + '<ul class="browse-list" id="search-results"></ul>')
    results = search_results(vault, q)
    n = len(results)
    body += "<p>" + str(n) + " result" + ("" if n == 1 else "s") + "</p>"
    body += render_search_results(results, q)
    return page("Search: " + q, body)


def connections_page(vault: Path) -> tuple[int, str]:
    note_map = build_note_map(vault)
    conn_dir = vault / "knowledge" / "connections"
    items = []
    if conn_dir.is_dir():
        for p in sorted(conn_dir.glob("*.md")):
            meta, body = parse_frontmatter(p.read_text(encoding="utf-8"))
            connects = meta.get("connects")
            if not isinstance(connects, list) or len(connects) < 2:
                continue
            key_idea = split_sections(body).get("Key Idea", "").strip()

            def link_for(name: str) -> str:
                hit = note_map.get(name.strip().lower())
                if hit:
                    return '<a href="/note?path=' + urllib.parse.quote(hit) + '">' + html.escape(name) + "</a>"
                return html.escape(name)

            items.append(
                "<li><p>" + link_for(connects[0]) + " &harr; " + link_for(connects[1]) + "</p>"
                + ('<p class="meta">' + html.escape(key_idea) + "</p>" if key_idea else "")
                + "</li>"
            )
    body = "<h1>Connections</h1><ul class=\"browse-list\">" + "".join(items) + "</ul>"
    return 200, page("Connections", body)


PAGE_SCRIPT = """
<script>
(function () {
  function debounce(fn, ms) {
    var t;
    return function () {
      var args = arguments, ctx = this;
      clearTimeout(t);
      t = setTimeout(function () { fn.apply(ctx, args); }, ms);
    };
  }

  function swap(id, newDoc) {
    var cur = document.getElementById(id);
    var next = newDoc.getElementById(id);
    if (!cur || !next) return;
    if (cur.querySelector("details[open]")) return;
    if (cur.textContent === next.textContent) return;
    cur.innerHTML = next.innerHTML;
    cur.classList.add("just-updated");
    setTimeout(function () { cur.classList.remove("just-updated"); }, 200);
  }

  if (document.getElementById("threads")) {
    setInterval(function () {
      if (document.hidden) return;
      if (document.activeElement && document.activeElement.tagName === "INPUT") return;
      fetch("/partial?view=home").then(function (r) { return r.text(); }).then(function (text) {
        var newDoc = new DOMParser().parseFromString(text, "text/html");
        ["engine-strip", "threads", "daily-logs"].forEach(function (id) { swap(id, newDoc); });
      }).catch(function () {});
    }, 20000);
  }

  var input = document.querySelector('input[name="q"]');
  var results = document.getElementById("search-results");
  if (input && results) {
    input.addEventListener("input", debounce(function () {
      fetch("/partial?view=search&q=" + encodeURIComponent(input.value)).then(function (r) { return r.text(); }).then(function (text) {
        var newDoc = new DOMParser().parseFromString(text, "text/html");
        var next = newDoc.getElementById("search-results");
        var old = document.getElementById("search-results");
        if (next && old) old.outerHTML = next.outerHTML;
      }).catch(function () {});
    }, 250));
  }

  document.addEventListener("keydown", function (e) {
    var box = document.querySelector('input[name="q"]');
    if (!box) return;
    var typing = document.activeElement && (document.activeElement.tagName === "INPUT" || document.activeElement.tagName === "TEXTAREA");
    if (e.key === "/" && !typing) { e.preventDefault(); box.focus(); }
    else if (e.key === "Escape" && document.activeElement === box) { box.blur(); }
  });
})();
</script>
"""


THEME_SCRIPT = """
<script>(function(){var t=localStorage.getItem('theme');if(t)document.documentElement.setAttribute('data-theme',t);})();</script>
"""

THEME_SWITCH_SCRIPT = """
<script>
(function () {
  var buttons = document.querySelectorAll(".theme-switch button");
  function current() { return localStorage.getItem("theme") || "system"; }
  function refresh() {
    var active = current();
    buttons.forEach(function (b) {
      b.classList.toggle("active", b.dataset.theme === active);
    });
  }
  buttons.forEach(function (b) {
    b.addEventListener("click", function () {
      var t = b.dataset.theme;
      if (t === "system") {
        localStorage.removeItem("theme");
        document.documentElement.removeAttribute("data-theme");
      } else {
        localStorage.setItem("theme", t);
        document.documentElement.setAttribute("data-theme", t);
      }
      refresh();
    });
  });
  refresh();
})();
</script>
"""

THEME_SWITCH_HTML = (
    '<p class="theme-switch">'
    '<button type="button" data-theme="system">System</button> &middot; '
    '<button type="button" data-theme="light">Light</button> &middot; '
    '<button type="button" data-theme="dark">Dark</button>'
    '</p>'
)


def page(title: str, body_html: str, crumb: str = "", home_link: bool = True) -> str:
    crumb_html = '<p class="crumb">' + crumb + "</p>" if crumb else ""
    home_html = '<p class="home-link"><a href="/">&larr; Aethrom Panel</a></p>' if home_link else ""
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
{THEME_SCRIPT}
<link rel="stylesheet" href="/style.css">
</head>
<body>
<main>
<div class="top-row">
<div>
{home_html}
{crumb_html}
</div>
{THEME_SWITCH_HTML}
</div>
{body_html}
</main>
{PAGE_SCRIPT}
{THEME_SWITCH_SCRIPT}
</body>
</html>
"""


# ---------- server ----------

class Handler(http.server.BaseHTTPRequestHandler):
    vault: Path

    def log_message(self, fmt, *args):
        pass

    def _send(self, status: int, body: str, content_type: str = "text/html; charset=utf-8"):
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(parsed.query)

        if parsed.path == "/style.css":
            css = (HERE / "style.css").read_text(encoding="utf-8")
            self._send(200, css, "text/css; charset=utf-8")
            return
        if parsed.path == "/":
            self._send(200, home(self.vault))
            return
        if parsed.path == "/note":
            status, body = note_page(self.vault, qs.get("path", [""])[0])
            self._send(status, body)
            return
        if parsed.path == "/browse":
            status, body = browse_page(self.vault, qs.get("dir", [""])[0])
            self._send(status, body)
            return
        if parsed.path == "/search":
            self._send(200, search_page(self.vault, qs.get("q", [""])[0]))
            return
        if parsed.path == "/connections":
            status, body = connections_page(self.vault)
            self._send(status, body)
            return
        if parsed.path == "/partial":
            view = qs.get("view", [""])[0]
            if view == "home":
                self._send(200, home_body(self.vault))
                return
            if view == "search":
                q = qs.get("q", [""])[0].strip()
                results = search_results(self.vault, q)
                self._send(200, render_search_results(results, q))
                return
            self._send(404, "Not found")
            return
        self._send(404, page("Not found", "<h1>Not found</h1>"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Local read-only web panel for the Aethrom vault.")
    parser.add_argument("--vault", help="path to the Aethrom vault (default: $AETHROM_VAULT, else ../Aethrom)")
    parser.add_argument("--port", type=int, default=PORT)
    args = parser.parse_args()

    vault = resolve_vault(args.vault)
    if not vault.is_dir():
        print("vault not found at " + str(vault), file=sys.stderr)
        print("point at it with --vault <path> or the AETHROM_VAULT variable", file=sys.stderr)
        return 1

    Handler.vault = vault
    server = http.server.ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print("serving " + str(vault) + " on http://127.0.0.1:" + str(args.port) + " , Ctrl+C to stop")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
