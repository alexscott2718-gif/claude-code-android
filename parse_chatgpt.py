#!/usr/bin/env python3
"""Parse ChatGPT export JSON files into Obsidian markdown notes.

Usage:
    python3 parse_chatgpt.py                    # Use default files (conversations-000.json through 005.json)
    python3 parse_chatgpt.py conversations-000.json conversations-001.json
    python3 parse_chatgpt.py /path/to/export.json

Default output directory: ~/ObsidianVault/08 Chat Archives/ChatGPT
All input files default to home directory if relative paths are given.
"""

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

HOME = Path.home()
DEFAULT_INPUT_FILES = [HOME / f"conversations-{i:03d}.json" for i in range(6)]
DEFAULT_OUTPUT_DIR = HOME / "ObsidianVault" / "08 Chat Archives" / "ChatGPT"

TAG_KEYWORDS = {
    "biology": ["cell", "protein", "dna", "rna", "gene", "enzyme", "metabolism",
                 "biochem", "molecular", "organism", "tissue", "receptor"],
    "bioinformatics": ["bioinformatics", "sequence", "alignment", "blast", "genome",
                        "pipeline", "fastq", "bam", "vcf", "snp", "variant"],
    "python": ["python", "pandas", "numpy", "matplotlib", "sklearn", "pytorch",
                "tensorflow", "flask", "django", "jupyter"],
    "javascript": ["javascript", "typescript", "react", "node", "npm", "html", "css",
                   "webpack", "vue", "angular"],
    "linux": ["bash", "shell", "linux", "terminal", "command line", "grep", "awk",
               "sed", "chmod", "systemd"],
    "statistics": ["statistics", "regression", "p-value", "hypothesis", "anova",
                    "distribution", "confidence interval", "correlation"],
    "ai-ml": ["machine learning", "neural network", "deep learning", "llm", "gpt",
               "transformer", "embedding", "fine-tuning", "training"],
    "writing": ["essay", "write", "edit", "grammar", "draft", "paragraph", "thesis",
                 "article", "report"],
}


def sanitize_filename(name: str) -> str:
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", name)
    name = re.sub(r"\s+", " ", name).strip()
    name = name[:120]  # cap length
    return name or "Untitled"


def infer_tags(title: str, text_sample: str) -> list[str]:
    combined = (title + " " + text_sample).lower()
    tags = []
    for tag, keywords in TAG_KEYWORDS.items():
        if any(kw in combined for kw in keywords):
            tags.append(tag)
    return tags[:5]  # cap at 5 tags


def extract_text_from_part(part) -> str:
    if isinstance(part, str):
        return part
    if isinstance(part, dict):
        # image or file attachment — note it but don't crash
        if part.get("content_type") in ("image_asset_pointer", "image_url"):
            return "[image]"
        if "text" in part:
            return part["text"]
    return ""


def extract_message_text(message: dict) -> str | None:
    content = message.get("content")
    if not content:
        return None

    ct = content.get("content_type", "text")
    parts = content.get("parts", [])

    if ct in ("text", "multimodal_text"):
        chunks = [extract_text_from_part(p) for p in parts]
        text = "\n".join(c for c in chunks if c).strip()
        return text or None

    if ct == "code":
        code_text = "\n".join(p for p in parts if isinstance(p, str)).strip()
        if code_text:
            lang = content.get("language", "")
            return f"```{lang}\n{code_text}\n```"
        return None

    if ct == "execution_output":
        out = "\n".join(p for p in parts if isinstance(p, str)).strip()
        return f"```\n{out}\n```" if out else None

    if ct in ("tether_quote", "tether_browsing_display"):
        domain = content.get("domain", "")
        url = content.get("url", "")
        text = content.get("text", "")
        title_str = content.get("title", "")
        lines = []
        if title_str:
            lines.append(f"> **{title_str}**")
        if domain or url:
            lines.append(f"> Source: {url or domain}")
        if text:
            lines.append(f"> {text[:500]}")
        return "\n".join(lines) if lines else None

    if ct == "reasoning_recap":
        summary = content.get("content", "")
        return f"*[Reasoning: {summary[:200]}]*" if summary else None

    if ct in ("thoughts", "computer_output", "system_error", "user_editable_context"):
        # Skip internal/tool content in main body
        return None

    return None


def get_active_message_chain(conv: dict) -> list[dict]:
    """Walk from current_node up to root, return messages in order."""
    mapping = conv.get("mapping", {})
    current_node_id = conv.get("current_node")

    if not current_node_id or current_node_id not in mapping:
        return []

    chain = []
    node_id = current_node_id
    visited = set()

    while node_id and node_id not in visited:
        visited.add(node_id)
        node = mapping.get(node_id)
        if not node:
            break
        msg = node.get("message")
        if msg:
            chain.append(msg)
        node_id = node.get("parent")

    chain.reverse()
    return chain


def format_conversation(conv: dict) -> str | None:
    title = conv.get("title") or "Untitled"
    create_time = conv.get("create_time") or 0
    date_str = datetime.fromtimestamp(create_time, tz=timezone.utc).strftime("%Y-%m-%d")

    messages = get_active_message_chain(conv)

    # Build body — only user and assistant turns
    body_parts = []
    text_sample_parts = []

    for msg in messages:
        role = msg.get("author", {}).get("role", "")
        if role not in ("user", "assistant"):
            continue

        text = extract_message_text(msg)
        if not text or not text.strip():
            continue

        heading = "## User" if role == "user" else "## Assistant"
        body_parts.append(f"{heading}\n\n{text.strip()}")

        if len(text_sample_parts) < 3:
            text_sample_parts.append(text[:300])

    if not body_parts:
        return None

    tags = infer_tags(title, " ".join(text_sample_parts))
    tag_yaml = "\n".join(f"  - {t}" for t in tags) if tags else ""
    tags_section = f"tags:\n{tag_yaml}" if tag_yaml else "tags: []"

    frontmatter = f"""---
title: "{title.replace('"', "'")}"
date: {date_str}
source: chatgpt
{tags_section}
---"""

    return frontmatter + "\n\n" + "\n\n---\n\n".join(body_parts)


def main():
    parser = argparse.ArgumentParser(
        description="Parse ChatGPT exports into Obsidian markdown notes",
        epilog="If no input files are specified, uses conversations-000.json through 005.json from home directory."
    )
    parser.add_argument("input_files", nargs="*", help="Input JSON files (default: conversations-{000..005}.json from home)")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT_DIR, help=f"Output directory (default: {DEFAULT_OUTPUT_DIR})")
    args = parser.parse_args()

    input_files = args.input_files if args.input_files else DEFAULT_INPUT_FILES
    output_dir = args.output

    # Convert relative paths to absolute (relative to home)
    input_files = [Path(f) if Path(f).is_absolute() else HOME / f for f in input_files]

    output_dir.mkdir(parents=True, exist_ok=True)

    processed = 0
    skipped = 0
    failed = 0
    failures = []

    seen_ids = set()

    for input_file in input_files:
        if not os.path.exists(input_file):
            print(f"[WARN] File not found: {input_file}", file=sys.stderr)
            continue

        try:
            with open(input_file, encoding="utf-8") as f:
                conversations = json.load(f)
        except Exception as e:
            print(f"[ERROR] Failed to load {input_file}: {e}", file=sys.stderr)
            failed += 1
            failures.append((input_file, str(e)))
            continue

        for conv in conversations:
            conv_id = conv.get("conversation_id") or conv.get("id", "")
            title = conv.get("title") or "Untitled"

            # Dedup by conversation_id
            if conv_id and conv_id in seen_ids:
                skipped += 1
                continue
            if conv_id:
                seen_ids.add(conv_id)

            create_time = conv.get("create_time") or 0
            date_str = datetime.fromtimestamp(create_time, tz=timezone.utc).strftime("%Y-%m-%d")
            safe_title = sanitize_filename(title)
            filename = f"{date_str} — {safe_title}.md"
            out_path = output_dir / filename

            # Skip if file already exists (idempotent re-runs)
            if out_path.exists():
                skipped += 1
                continue

            try:
                content = format_conversation(conv)
                if content is None:
                    skipped += 1
                    continue
                out_path.write_text(content, encoding="utf-8")
                processed += 1
            except Exception as e:
                failed += 1
                failures.append((filename, str(e)))

    print(f"\n{'='*50}")
    print(f"ChatGPT Export → Obsidian Markdown")
    print(f"{'='*50}")
    print(f"  Processed : {processed}")
    print(f"  Skipped   : {skipped}  (duplicates or empty)")
    print(f"  Failed    : {failed}")
    print(f"  Output dir: {output_dir}")

    if failures:
        print(f"\nFailures:")
        for name, reason in failures:
            print(f"  - {name}: {reason}")

    print(f"{'='*50}\n")


if __name__ == "__main__":
    main()
