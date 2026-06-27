#!/usr/bin/env python3
"""Parse Claude.ai export JSON files into Obsidian markdown notes.

Usage:
    python3 parse_claude.py                     # Use default files (claude_conversations.json, etc)
    python3 parse_claude.py conv.json proj.json mem.json
    python3 parse_claude.py /path/to/claude_conversations.json /path/to/claude_projects.json /path/to/claude_memories.json

Default input files (from home directory):
    - claude_conversations.json
    - claude_projects.json
    - claude_memories.json

Default output directories:
    - Conversations: ~/ObsidianVault/08 Chat Archives/Claude
    - Projects: ~/ObsidianVault/08 Chat Archives/Claude/Projects
    - Memories: ~/ObsidianVault/06 Personal/Claude Memories.md
"""

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

HOME = Path.home()

# Defaults
DEFAULT_CONV_FILE     = HOME / "claude_conversations.json"
DEFAULT_PROJECTS_FILE = HOME / "claude_projects.json"
DEFAULT_MEMORIES_FILE = HOME / "claude_memories.json"

DEFAULT_CONV_DIR     = HOME / "ObsidianVault" / "08 Chat Archives" / "Claude"
DEFAULT_PROJECTS_DIR = HOME / "ObsidianVault" / "08 Chat Archives" / "Claude" / "Projects"
DEFAULT_MEMORIES_OUT = HOME / "ObsidianVault" / "06 Personal" / "Claude Memories.md"

TAG_KEYWORDS = {
    "biology": ["cell", "protein", "dna", "rna", "gene", "enzyme", "metabolism",
                 "biochem", "molecular", "organism", "tissue", "receptor"],
    "bioinformatics": ["bioinformatics", "sequence", "alignment", "blast", "genome",
                        "pipeline", "fastq", "bam", "vcf", "snp", "variant"],
    "python": ["python", "pandas", "numpy", "matplotlib", "sklearn", "pytorch",
                "tensorflow", "flask", "django", "jupyter", "pptxgenjs"],
    "linux": ["bash", "shell", "linux", "terminal", "command line", "debian",
               "systemd", "ssh", "apt", "proot", "termux"],
    "homelab": ["homelab", "server", "optiplex", "nas", "docker", "proxmox",
                 "network", "raspberry pi", "self-host"],
    "reverse-engineering": ["ghidra", "decompil", "binary", "hex", "patch",
                             "assembly", "asm", "ida", "dll", "exe", "wine"],
    "ai-ml": ["machine learning", "neural network", "deep learning", "llm", "gpt",
               "transformer", "embedding", "fine-tuning", "claude", "anthropic"],
    "writing": ["essay", "write", "edit", "grammar", "draft", "paragraph",
                 "thesis", "article", "report", "presentation", "slide"],
    "personal": ["family", "home", "house", "finances", "career", "resume"],
}


def sanitize_filename(name: str) -> str:
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", name)
    name = re.sub(r"\s+", " ", name).strip()
    return (name[:120] or "Untitled")


def parse_iso(ts: str) -> datetime:
    ts = ts.replace("Z", "+00:00")
    return datetime.fromisoformat(ts)


def date_str(ts: str) -> str:
    return parse_iso(ts).strftime("%Y-%m-%d")


def infer_tags(title: str, sample: str) -> list[str]:
    combined = (title + " " + sample).lower()
    return [t for t, kws in TAG_KEYWORDS.items() if any(k in combined for k in kws)][:5]


def frontmatter(title: str, date: str, source: str, tags: list[str]) -> str:
    tag_lines = "\n".join(f"  - {t}" for t in tags)
    tags_yaml = f"tags:\n{tag_lines}" if tag_lines else "tags: []"
    return (
        f"---\n"
        f'title: "{title.replace(chr(34), chr(39))}"\n'
        f"date: {date}\n"
        f"source: {source}\n"
        f"{tags_yaml}\n"
        f"---"
    )


# ---------------------------------------------------------------------------
# Conversations
# ---------------------------------------------------------------------------

def extract_message_text(msg: dict) -> str | None:
    """Extract displayable text from a chat_message, handling all content types."""
    # Top-level `text` is the plain-text rollup — good for human turns
    # and assistant turns without tool calls.
    top_text = (msg.get("text") or "").strip()

    content_blocks = msg.get("content") or []
    parts = []

    for block in content_blocks:
        btype = block.get("type", "")

        if btype == "text":
            t = (block.get("text") or "").strip()
            if t:
                parts.append(t)

        elif btype == "thinking":
            # Skip internal reasoning — it's verbose and internal
            pass

        elif btype == "tool_use":
            name = block.get("name", "tool")
            inp = block.get("input") or {}
            # Summarise input concisely
            if "url" in inp:
                detail = inp["url"]
            elif "command" in inp:
                detail = f"`{inp['command']}`"
            elif "query" in inp:
                detail = f'"{inp["query"]}"'
            elif inp:
                kv = ", ".join(f"{k}={str(v)[:60]}" for k, v in list(inp.items())[:3])
                detail = kv
            else:
                detail = ""
            note = f"> *[Tool: **{name}**{(' — ' + detail) if detail else ''}]*"
            parts.append(note)

        elif btype == "tool_result":
            # Skip — it's the raw tool response, usually very long
            pass

        elif btype in ("token_budget", "thinking_summary"):
            pass  # metadata, skip

    assembled = "\n\n".join(parts).strip()

    # If content blocks gave us nothing meaningful, fall back to top-level text
    if not assembled and top_text:
        return top_text

    # If assembled text is essentially the same as top_text (no tool annotations),
    # prefer assembled (same content, but we've already processed it).
    return assembled or None


def format_conversation(conv: dict) -> str | None:
    title   = conv.get("name") or "Untitled"
    created = conv.get("created_at", "")
    dt      = date_str(created) if created else "0000-00-00"

    messages = conv.get("chat_messages") or []
    sections = []
    sample_chunks = []

    for msg in messages:
        sender = msg.get("sender", "")
        if sender not in ("human", "assistant"):
            continue

        text = extract_message_text(msg)
        if not text:
            continue

        # Note attached files
        file_notes = []
        for f in (msg.get("files") or []):
            fname = f.get("file_name", "file")
            file_notes.append(f"> *[Attached file: `{fname}`]*")
        for a in (msg.get("attachments") or []):
            fname = a.get("file_name", "attachment")
            file_notes.append(f"> *[Attachment: `{fname}`]*")

        heading = "## Human" if sender == "human" else "## Assistant"
        body = "\n\n".join(filter(None, ["\n".join(file_notes) if file_notes else None, text]))
        sections.append(f"{heading}\n\n{body.strip()}")

        if len(sample_chunks) < 3:
            sample_chunks.append(text[:300])

    if not sections:
        return None

    tags = infer_tags(title, " ".join(sample_chunks))
    fm   = frontmatter(title, dt, "claude", tags)
    return fm + "\n\n" + "\n\n---\n\n".join(sections)


def process_conversations(conv_file: Path, conv_dir: Path) -> tuple[int, int, int, list]:
    conv_dir.mkdir(parents=True, exist_ok=True)
    processed = skipped = failed = 0
    failures = []

    try:
        with open(conv_file, encoding="utf-8") as f:
            conversations = json.load(f)
    except Exception as e:
        return 0, 0, 1, [(str(conv_file), str(e))]

    seen_uuids: set[str] = set()

    for conv in conversations:
        uid   = conv.get("uuid", "")
        title = conv.get("name") or "Untitled"

        if uid and uid in seen_uuids:
            skipped += 1
            continue
        if uid:
            seen_uuids.add(uid)

        created = conv.get("created_at", "")
        dt      = date_str(created) if created else "0000-00-00"
        fname   = f"{dt} — {sanitize_filename(title)}.md"
        out     = conv_dir / fname

        if out.exists():
            skipped += 1
            continue

        try:
            content = format_conversation(conv)
            if content is None:
                skipped += 1
                continue
            out.write_text(content, encoding="utf-8")
            processed += 1
        except Exception as e:
            failed += 1
            failures.append((fname, str(e)))

    return processed, skipped, failed, failures


# ---------------------------------------------------------------------------
# Projects
# ---------------------------------------------------------------------------

def format_project(proj: dict) -> str:
    title   = proj.get("name") or "Untitled Project"
    created = proj.get("created_at", "")
    dt      = date_str(created) if created else "0000-00-00"
    desc    = (proj.get("description") or "").strip()
    prompt  = (proj.get("prompt_template") or "").strip()
    docs    = proj.get("docs") or []

    sample  = (desc + " " + prompt)[:600]
    tags    = infer_tags(title, sample)
    fm      = frontmatter(title, dt, "claude", tags)

    sections = [fm]

    if desc:
        sections.append(f"## Description\n\n{desc}")

    if prompt:
        sections.append(f"## Project Instructions\n\n{prompt}")

    if docs:
        doc_lines = []
        for d in docs:
            dname = d.get("filename") or d.get("name") or "document"
            doc_lines.append(f"- `{dname}`")
        sections.append("## Documents\n\n" + "\n".join(doc_lines))

    return "\n\n".join(sections)


def process_projects(projects_file: Path, projects_dir: Path) -> tuple[int, int, int, list]:
    projects_dir.mkdir(parents=True, exist_ok=True)
    processed = skipped = failed = 0
    failures = []

    try:
        with open(projects_file, encoding="utf-8") as f:
            projects = json.load(f)
    except Exception as e:
        return 0, 0, 1, [(str(projects_file), str(e))]

    for proj in projects:
        title   = proj.get("name") or "Untitled Project"
        created = proj.get("created_at", "")
        dt      = date_str(created) if created else "0000-00-00"
        fname   = f"{dt} — {sanitize_filename(title)}.md"
        out     = projects_dir / fname

        if out.exists():
            skipped += 1
            continue

        try:
            content = format_project(proj)
            out.write_text(content, encoding="utf-8")
            processed += 1
        except Exception as e:
            failed += 1
            failures.append((fname, str(e)))

    return processed, skipped, failed, failures


# ---------------------------------------------------------------------------
# Memories
# ---------------------------------------------------------------------------

def process_memories(memories_file: Path, memories_out: Path, project_names: dict[str, str]) -> tuple[int, int, int, list]:
    memories_out.parent.mkdir(parents=True, exist_ok=True)

    if memories_out.exists():
        return 0, 1, 0, []

    try:
        with open(memories_file, encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        return 0, 0, 1, [(str(memories_file), str(e))]

    item = data[0] if isinstance(data, list) else data
    conv_mem    = (item.get("conversations_memory") or "").strip()
    proj_mems   = item.get("project_memories") or {}
    today       = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")

    tags = infer_tags("memories " + conv_mem[:200], conv_mem[:400])
    fm   = frontmatter("Claude Memories", today, "claude", tags)

    sections = [fm]

    if conv_mem:
        sections.append(f"## Conversation Memory\n\n{conv_mem}")

    for proj_uuid, mem_text in proj_mems.items():
        proj_title = project_names.get(proj_uuid, proj_uuid)
        sections.append(f"## Project Memory: {proj_title}\n\n{mem_text.strip()}")

    memories_out.write_text("\n\n".join(sections), encoding="utf-8")
    return 1, 0, 0, []


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Parse Claude.ai exports into Obsidian markdown notes",
        epilog="If no input files are specified, uses claude_conversations.json, claude_projects.json, and claude_memories.json from home directory."
    )
    parser.add_argument("input_files", nargs="*", help="Input JSON files: CONVERSATIONS PROJECTS MEMORIES (default: claude_*.json from home)")
    parser.add_argument("--conv-dir", type=Path, default=DEFAULT_CONV_DIR, help=f"Conversations output dir (default: {DEFAULT_CONV_DIR})")
    parser.add_argument("--proj-dir", type=Path, default=DEFAULT_PROJECTS_DIR, help=f"Projects output dir (default: {DEFAULT_PROJECTS_DIR})")
    parser.add_argument("--mem-out", type=Path, default=DEFAULT_MEMORIES_OUT, help=f"Memories output file (default: {DEFAULT_MEMORIES_OUT})")
    args = parser.parse_args()

    # Determine input files
    if args.input_files:
        if len(args.input_files) >= 3:
            conv_file, projects_file, memories_file = Path(args.input_files[0]), Path(args.input_files[1]), Path(args.input_files[2])
        elif len(args.input_files) == 2:
            conv_file, projects_file = Path(args.input_files[0]), Path(args.input_files[1])
            memories_file = DEFAULT_MEMORIES_FILE
        else:
            conv_file = Path(args.input_files[0])
            projects_file = DEFAULT_PROJECTS_FILE
            memories_file = DEFAULT_MEMORIES_FILE
    else:
        conv_file, projects_file, memories_file = DEFAULT_CONV_FILE, DEFAULT_PROJECTS_FILE, DEFAULT_MEMORIES_FILE

    # Convert relative paths to absolute (relative to home)
    conv_file = conv_file if conv_file.is_absolute() else HOME / conv_file
    projects_file = projects_file if projects_file.is_absolute() else HOME / projects_file
    memories_file = memories_file if memories_file.is_absolute() else HOME / memories_file

    # Load project names for memory cross-referencing
    project_names: dict[str, str] = {}
    try:
        with open(projects_file, encoding="utf-8") as f:
            for p in json.load(f):
                project_names[p.get("uuid", "")] = p.get("name") or p.get("uuid", "")
    except Exception:
        pass

    c_proc, c_skip, c_fail, c_errs = process_conversations(conv_file, args.conv_dir)
    p_proc, p_skip, p_fail, p_errs = process_projects(projects_file, args.proj_dir)
    m_proc, m_skip, m_fail, m_errs = process_memories(memories_file, args.mem_out, project_names)

    all_failures = c_errs + p_errs + m_errs
    total_fail   = c_fail + p_fail + m_fail

    print(f"\n{'='*55}")
    print(f"Claude Export → Obsidian Markdown")
    print(f"{'='*55}")
    print(f"  Conversations  → processed: {c_proc:3d}  skipped: {c_skip:3d}  failed: {c_fail}")
    print(f"  Projects       → processed: {p_proc:3d}  skipped: {p_skip:3d}  failed: {p_fail}")
    print(f"  Memories       → processed: {m_proc:3d}  skipped: {m_skip:3d}  failed: {m_fail}")
    print(f"{'─'*55}")
    print(f"  Total          → processed: {c_proc+p_proc+m_proc:3d}  skipped: {c_skip+p_skip+m_skip:3d}  failed: {total_fail}")
    print()
    print(f"  Output dirs:")
    print(f"    {args.conv_dir}")
    print(f"    {args.proj_dir}")
    print(f"    {args.mem_out}")

    if all_failures:
        print(f"\n  Failures:")
        for name, reason in all_failures:
            print(f"    - {name}: {reason}")

    print(f"{'='*55}\n")


if __name__ == "__main__":
    main()
