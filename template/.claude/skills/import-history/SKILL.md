---
name: import-history
description: Converts an exported conversation history from another assistant (ChatGPT, Claude, a Gemini Takeout archive) into the vault's daily-log format so the compiler can ingest it. Use on "import history", "import my chats", "takeout", "chatgpt history", "load my old conversations into the brain".
---

# Import History

Feeds an old conversation archive into the brain's normal pipeline. The export file is read
locally, conversations are split by month, and written to `daily/import-YYYY-MM-part-NNN.md`
files. The evening compiler reads the contents of these files like any other daily log, and sends
them to Claude for summarization through the user's own Claude subscription. The export file
itself is never uploaded, and the data is never sent anywhere else.

Private or sensitive conversations are included in the import and the following compile unless
the user excludes them by date or keyword filter.

## Mandatory consent gate

The agent MUST complete the following steps in order. Opening the export file, parsing it, or
writing any file under `daily/` without the user's permission is FORBIDDEN.

1. The agent MUST state the data flow explicitly: the export is read locally, selected
   conversations are written to local `daily/` files, and the evening compiler sends the contents
   of those files to Claude for summarization through the user's own Claude subscription. Nothing
   is uploaded or sent anywhere else.
2. The agent MUST say that private and sensitive conversations are included by default. It MUST
   offer the user a start/end date bound and an exclude list of one or more keywords. Matching is
   case-insensitive and a matched conversation is skipped in its entirety.
3. The agent MUST ask the user for the export file's path and take it as plain text only. It may
   not guess the path or open the file yet. It then MUST ask for explicit permission to run a
   local, read-only preview scan, and wait for the answer. Without explicit permission it may not
   open the file. If permission is granted, it runs the script with `--preview` and the chosen
   filters. This mode writes no output file.
4. The agent MUST show the user the preview's count of conversations to be imported, the date
   range, and the counts skipped for date, keyword, empty content, or invalid record reasons.
5. The agent MUST also tell the user the honest ways to back out: never compile the imported
   files at all, or delete an unwanted monthly part file before the evening compile runs. If the
   user backs out, the process stops.
6. The agent MUST restate the chosen date range and keyword list and ask for this exact
   confirmation: `Yes, import with this preview and these filters.` Import and writing may not
   start until the user says yes explicitly. An ambiguous answer does not count as consent.

This consent instruction is for the agent. Do not add automatic approval, interactive approval, or
a flag that skips consent to the script.

## Steps

1. Complete the consent gate and use the export path the user gave you. Do not guess it.
2. Verify the file type.
   - ChatGPT: `conversations.json` inside the export zip. If the zip is not yet extracted, ask
     the user to extract it, or use `unzip` locally with explicit permission.
   - Claude: `conversations.json` inside the export.
   - Gemini: `My Activity/Gemini Apps/MyActivity.json` inside the Google Takeout archive.
3. Measure the file size (`os.path.getsize`, or `wc -c` in a shell). If it is over 50 MB, the
   script automatically limits itself to the most recent 12 calendar months. Say so in the
   preview. If the user's own date bound is narrower, the narrower one wins.
4. Write the appropriate script below to a temporary path such as
   `.claude/hooks/.state/import-chatgpt.py`. Run it with `--preview` first. Only after the second
   explicit confirmation, run it again with the same filters, without `--preview`.
5. Use a separate `--exclude-keyword` for each keyword. Dates are inclusive on both ends.
6. Run the script with the interpreter recorded in `.claude/settings.local.json`, never a bare
   `python3`: on Windows, `python3` on PATH is often a Microsoft Store stub that fails when run.
   Resolve it the same way the `doctor` skill does, falling back to `python3` then `python`:

```bash
PY=$(grep -o '"command":[[:space:]]*"[^"]*"' .claude/settings.local.json 2>/dev/null | head -1 | sed -E 's/.*"([^"]+)"$/\1/')
for candidate in "$PY" python3 python; do
  [ -n "$candidate" ] && "$candidate" -c "1" >/dev/null 2>&1 && { PY="$candidate"; break; }
done
```

```text
"$PY" .claude/hooks/.state/import-chatgpt.py conversations.json \
  --preview --start 2025-01-01 --end 2025-12-31 \
  --exclude-keyword "health" --exclude-keyword "private project"
```

6. Relay the script's summary output to the user verbatim. If a target file already exists, the
   script refuses to overwrite it. In that case ask the user to explicitly pick a new output
   folder or handle the existing files themselves. Do not delete, merge, or overwrite the file
   yourself.
7. Explain the compile plan from the "What happens next" section below.

## ChatGPT script

Each conversation in a ChatGPT export is a `mapping` tree. Where there are branches, every
reachable node is written once, in source order. System and tool messages are not written to the
daily file. Message and conversation text is never truncated. When a month's part file fills up,
conversations move to a new part file rather than being dropped. If a single conversation is
larger than the limit, that part is allowed to exceed it rather than lose content.

```python
#!/usr/bin/env python3
"""Convert a ChatGPT conversations.json export into local daily part files."""

import argparse
import datetime as dt
import json
import os
import sys

MAX_EXPORT_BYTES = 50 * 1024 * 1024
RECENT_MONTHS = 12
MAX_FILE_CHARS = 200000

# The export is someone else's writing and em dashes (U+2014) are close to
# certain in it. backup.sh refuses to commit any file containing one, and it
# refuses the whole staged change, not just that file: an import written
# today would silently stop every hourly backup from then on until someone
# went looking. Strip it here, at the one place text from the export becomes
# text on disk, the same way compile.py and flush.py strip it on their own
# write paths.
EM_DASH = chr(0x2014)  # the em dash, spelled without writing one


def strip_em_dash(text):
    return text.replace(EM_DASH, "-")


def iso_date(value):
    try:
        return dt.datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise argparse.ArgumentTypeError("date must be YYYY-MM-DD: %s" % value) from exc


def arguments():
    parser = argparse.ArgumentParser(description="Import ChatGPT history locally")
    parser.add_argument("source", help="conversations.json file, or the folder containing it")
    parser.add_argument("--preview", action="store_true", help="preview only, write nothing")
    parser.add_argument("--start", type=iso_date, help="inclusive start date, YYYY-MM-DD")
    parser.add_argument("--end", type=iso_date, help="inclusive end date, YYYY-MM-DD")
    parser.add_argument(
        "--exclude-keyword",
        action="append",
        default=[],
        help="skip a matching conversation, repeatable",
    )
    parser.add_argument("--out-dir", default="daily", help="output folder, default daily")
    args = parser.parse_args()
    if args.start and args.end and args.start > args.end:
        parser.error("start date cannot be after end date")
    return args


def load_export(path):
    if os.path.isdir(path):
        path = os.path.join(path, "conversations.json")
    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    if isinstance(data, dict):
        data = data.get("conversations", [])
    if not isinstance(data, list):
        raise ValueError("export is not a conversation list")
    return path, data


def content_parts(message):
    if not isinstance(message, dict):
        return []
    content = message.get("content") or {}
    if content.get("content_type") not in ("text", "multimodal_text", None):
        return []
    texts = []
    for part in content.get("parts") or []:
        if isinstance(part, str) and part.strip():
            texts.append(part)
        elif isinstance(part, dict) and isinstance(part.get("text"), str):
            if part["text"].strip():
                texts.append(part["text"])
    return texts


def message_text(message):
    if not isinstance(message, dict):
        return None, None
    role = (message.get("author") or {}).get("role")
    if role not in ("user", "assistant"):
        return None, None
    metadata = message.get("metadata") or {}
    if metadata.get("is_visually_hidden_from_conversation"):
        return None, None
    parts = content_parts(message)
    if not parts:
        return None, None
    return role, "\n".join(parts)


def walk_nodes(mapping):
    roots = [
        node_id
        for node_id, node in mapping.items()
        if isinstance(node, dict) and not node.get("parent")
    ]
    seeds = roots + [node_id for node_id in mapping if node_id not in roots]
    seen = set()
    for seed in seeds:
        stack = [seed]
        while stack:
            node_id = stack.pop()
            if node_id in seen:
                continue
            seen.add(node_id)
            node = mapping.get(node_id)
            if not isinstance(node, dict):
                continue
            yield node
            children = node.get("children") or []
            for child in reversed(children):
                stack.append(child)


def conversation_turns(mapping):
    turns = []
    for node in walk_nodes(mapping):
        role, text = message_text(node.get("message"))
        if role:
            turns.append((role, text))
    return turns


def conversation_time(conversation, mapping):
    stamp = conversation.get("create_time") or conversation.get("update_time")
    if isinstance(stamp, (int, float)) and stamp > 0:
        return float(stamp)
    for node in walk_nodes(mapping):
        message = node.get("message") or {}
        stamp = message.get("create_time")
        if isinstance(stamp, (int, float)) and stamp > 0:
            return float(stamp)
    return None


def searchable_text(conversation, mapping):
    values = [str(conversation.get("title") or "")]
    for node in walk_nodes(mapping):
        values.extend(content_parts(node.get("message")))
    return "\n".join(values).casefold()


def recent_cutoff(today):
    month_number = today.year * 12 + today.month - 1 - (RECENT_MONTHS - 1)
    year, month_index = divmod(month_number, 12)
    return dt.date(year, month_index + 1, 1)


def select_conversations(conversations, size, start, end, keywords):
    stats = {
        "source": len(conversations),
        "invalid": 0,
        "date": 0,
        "keyword": 0,
        "empty": 0,
    }
    automatic_start = None
    if size > MAX_EXPORT_BYTES:
        automatic_start = recent_cutoff(dt.datetime.now(dt.timezone.utc).date())
    effective_start = start
    if automatic_start and (effective_start is None or automatic_start > effective_start):
        effective_start = automatic_start
    folded_keywords = [word.casefold() for word in keywords if word.strip()]
    selected = []
    for conversation in conversations:
        if not isinstance(conversation, dict):
            stats["invalid"] += 1
            continue
        mapping = conversation.get("mapping") or {}
        if not isinstance(mapping, dict):
            stats["invalid"] += 1
            continue
        stamp = conversation_time(conversation, mapping)
        if stamp is None:
            stats["invalid"] += 1
            continue
        moment = dt.datetime.fromtimestamp(stamp, dt.timezone.utc)
        day = moment.date()
        if (effective_start and day < effective_start) or (end and day > end):
            stats["date"] += 1
            continue
        haystack = searchable_text(conversation, mapping)
        if any(word in haystack for word in folded_keywords):
            stats["keyword"] += 1
            continue
        turns = conversation_turns(mapping)
        if not turns:
            stats["empty"] += 1
            continue
        selected.append(
            {
                "title": str(conversation.get("title") or "untitled"),
                "moment": moment,
                "turns": turns,
            }
        )
    selected.sort(key=lambda item: item["moment"])
    return selected, stats, automatic_start, effective_start


def conversation_block(record):
    moment = record["moment"]
    title = strip_em_dash(record["title"].replace("\r", " ").replace("\n", " ").strip())
    heading = "### Session (%s UTC) ChatGPT: %s\n\n" % (
        moment.strftime("%Y-%m-%d %H:%M"),
        title or "untitled",
    )
    lines = []
    for role, text in record["turns"]:
        label = "**User:**" if role == "user" else "**Assistant:**"
        lines.append("%s %s\n" % (label, strip_em_dash(text)))
    return heading + "\n".join(lines)


def part_header(month, part_number):
    return (
        "# Daily Log: %s (import, part %03d)\n\n"
        "Source: ChatGPT export. This file was written by a machine.\n\n"
        "## Sessions\n\n" % (month, part_number)
    )


def build_parts(selected, out_dir):
    months = {}
    for record in selected:
        month = record["moment"].strftime("%Y-%m")
        months.setdefault(month, []).append(conversation_block(record))
    plans = []
    for month in sorted(months):
        part_number = 1
        header = part_header(month, part_number)
        blocks = []
        total = len(header)
        for block in months[month]:
            separator = "" if not blocks else "\n"
            if blocks and total + len(separator) + len(block) > MAX_FILE_CHARS:
                text = header + "\n".join(blocks)
                name = "import-%s-part-%03d.md" % (month, part_number)
                plans.append((os.path.join(out_dir, name), text, len(blocks)))
                part_number += 1
                header = part_header(month, part_number)
                blocks = []
                total = len(header)
                separator = ""
            blocks.append(block)
            total += len(separator) + len(block)
        if blocks:
            text = header + "\n".join(blocks)
            name = "import-%s-part-%03d.md" % (month, part_number)
            plans.append((os.path.join(out_dir, name), text, len(blocks)))
    return plans


def write_exclusive(plans):
    claimed = []
    try:
        for path, text, count in plans:
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            claimed.append([path, descriptor, text, count])
    except OSError:
        for path, descriptor, _text, _count in claimed:
            os.close(descriptor)
            os.unlink(path)
        raise
    try:
        for item in claimed:
            with os.fdopen(item[1], "w", encoding="utf-8", newline="\n") as handle:
                handle.write(item[2])
            item[1] = None
    except OSError:
        for path, descriptor, _text, _count in claimed:
            if descriptor is not None:
                try:
                    os.close(descriptor)
                except OSError:
                    pass
            try:
                os.unlink(path)
            except FileNotFoundError:
                pass
        raise


def print_selection(selected, stats, automatic_start, effective_start, preview):
    skipped = stats["invalid"] + stats["date"] + stats["keyword"] + stats["empty"]
    print("PREVIEW" if preview else "IMPORT")
    print("source conversations: %d" % stats["source"])
    print("conversations to write: %d" % len(selected))
    if selected:
        print(
            "date range: %s .. %s"
            % (selected[0]["moment"].date(), selected[-1]["moment"].date())
        )
    else:
        print("date range: none")
    print(
        "skipped conversations: %d (date: %d, keyword: %d, empty: %d, invalid: %d)"
        % (skipped, stats["date"], stats["keyword"], stats["empty"], stats["invalid"])
    )
    if automatic_start:
        print("50 MB limit: most recent 12 calendar months, automatic start %s" % automatic_start)
    if effective_start:
        print("effective start date: %s" % effective_start)


def main():
    args = arguments()
    try:
        path, conversations = load_export(args.source)
        size = os.path.getsize(path)
        selected, stats, automatic_start, effective_start = select_conversations(
            conversations, size, args.start, args.end, args.exclude_keyword
        )
        print_selection(selected, stats, automatic_start, effective_start, args.preview)
        if args.preview:
            print("no file written")
            return 0
        plans = build_parts(selected, args.out_dir)
        if not plans:
            print("files written: 0")
            return 0
        os.makedirs(args.out_dir, exist_ok=True)
        try:
            write_exclusive(plans)
        except FileExistsError as exc:
            print(
                "ERROR: did not overwrite existing import file: %s" % exc.filename,
                file=sys.stderr,
            )
            return 3
        print("files written: %d" % len(plans))
        print("conversations written: %d, conversations skipped: %d" % (
            sum(count for _path, _text, count in plans),
            stats["invalid"] + stats["date"] + stats["keyword"] + stats["empty"],
        ))
        for output, text, count in plans:
            print("  %s  %d conversations  %d characters" % (output, count, len(text)))
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print("ERROR: %s" % exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
```

## Claude script

The Claude export schema is flat. Reuse the same consent gate, `--preview`, date and keyword
filters, lossless chunking, and `write_exclusive` write path. Call the resolver below instead of
the ChatGPT-specific `conversation_turns`. Do not write system records.

```python
def claude_turns(conversation):
    turns = []
    for message in conversation.get("chat_messages") or []:
        role = {"human": "user", "assistant": "assistant"}.get(message.get("sender"))
        if not role:
            continue
        texts = []
        for block in message.get("content") or []:
            if isinstance(block, dict) and block.get("type") == "text":
                text = block.get("text")
                if isinstance(text, str) and text.strip():
                    texts.append(text)
        fallback = message.get("text")
        if not texts and isinstance(fallback, str) and fallback.strip():
            texts.append(fallback)
        if texts:
            turns.append((role, "\n".join(texts)))
    return turns
```

Resolve the timestamp with the standard library only, like this:

```python
created = str(conversation.get("created_at") or "")
moment = dt.datetime.fromisoformat(created.replace("Z", "+00:00"))
if moment.tzinfo is None:
    moment = moment.replace(tzinfo=dt.timezone.utc)
stamp = moment.timestamp()
```

## Gemini Takeout

The Takeout archive has a `My Activity/Gemini Apps/` folder. If JSON was selected,
`MyActivity.json` is a list of records. This format does not preserve conversation continuity,
each record is a single prompt. Write the Gemini import like a prompt log: group each day's
records into a single `### Session (YYYY-MM-DD) Gemini` block, and turn each record into a
`**User:**` line. The same consent, preview, filter, chunking, and collision rules apply. If
Takeout was exported as HTML, ask the user to re-export in JSON format.

## What happens next

Once the import is done, give the user an honest summary:

- Show the written and skipped conversation counts separately. Relay each part file's
  conversation and character count from the script's own output.
- `daily/import-*.md` files are local. The evening compiler sends their contents to Claude for
  summarization through the user's own Claude subscription. Nothing is sent anywhere else.
- The compiler runs one pass per evening and processes whatever changed in that pass. A large
  archive can spread across several evenings. Importing years of history at once means a lot of
  compile runs, and every run spends part of the user's Claude subscription; say this plainly
  rather than letting the user find out later.
- If the user does not want to wait, `"$PY" .claude/hooks/compile.py --dry-run` can be run first
  (with `$PY` resolved as in step 6 above), then `"$PY" .claude/hooks/compile.py` with explicit
  permission. Every pass spends part of the subscription's budget.
- If the user does not want the content sent to Claude at all, do not run the compiler, and delete
  the relevant monthly part files before the evening compile runs.
- If older archive content was skipped because of the 50 MB limit, say so explicitly and ask
  whether the user wants a second pass with a separate, earlier date range.

Imported files are ordinary daily logs once written: nothing marks them as special to the
compiler, so the next compile pass picks them up exactly like any log a normal session produced.
That also means the cost is the same per file: importing years of history at once is importing
years of compile runs, spread across as many evenings as it takes, each one spending part of the
subscription budget described above.

As a last step, suggest running the `doctor` skill. Compile status can be tracked from its
compile-status row.
