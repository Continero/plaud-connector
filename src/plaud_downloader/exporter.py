"""Exporter — writes recording data as JSON and Markdown files."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

_FORBIDDEN_RE = re.compile(r'[<>:"/\\|?*]')


def _sanitize_filename(name: str) -> str:
    """Replace forbidden filename characters with hyphens."""
    return _FORBIDDEN_RE.sub("-", name)


def _ms_to_timestamp(ms: int) -> str:
    """Convert milliseconds to HH:MM:SS string."""
    total_seconds = ms // 1000
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def _parse_ai_content(raw: str | None) -> str:
    """Parse the ai_content field which may be plain markdown or JSON."""
    if not raw:
        return ""
    if not raw.startswith("{"):
        return raw
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return raw
    if "markdown" in parsed:
        return parsed["markdown"]
    if isinstance(parsed.get("content"), dict) and "markdown" in parsed["content"]:
        return parsed["content"]["markdown"]
    if "summary" in parsed:
        return parsed["summary"]
    return raw


class Exporter:
    """Export recording data to JSON and Markdown files on disk."""

    def __init__(self, output_dir: Path, tags: list[dict]) -> None:
        self.output_dir = Path(output_dir)
        self.tag_map: dict[str, str] = {t["id"]: t["name"] for t in tags}

    def export_recording(self, recording: dict) -> str:
        """Export a single recording. Returns 'exported' or 'skipped'."""
        # Determine folder from tag
        tag_ids = recording.get("filetag_id_list") or []
        folder_name = "Unsorted"
        for tid in tag_ids:
            if tid in self.tag_map:
                folder_name = self.tag_map[tid]
                break

        # Build filename stem
        start_ms = recording["start_time"]
        dt = datetime.fromtimestamp(start_ms / 1000, tz=timezone.utc)
        date_str = dt.strftime("%Y-%m-%d")
        safe_name = _sanitize_filename(recording["filename"])
        stem = f"{date_str}_{safe_name}"

        folder = self.output_dir / folder_name
        json_path = folder / f"{stem}.json"
        md_path = folder / f"{stem}.md"

        # Skip if already exported
        if json_path.exists():
            return "skipped"

        folder.mkdir(parents=True, exist_ok=True)

        transcript = recording.get("trans_result") or []
        summary = _parse_ai_content(recording.get("ai_content"))
        duration_ms = recording.get("duration", 0)

        # Write JSON
        json_data = {
            "id": recording["id"],
            "filename": recording["filename"],
            "start_time": start_ms,
            "duration_ms": duration_ms,
            "transcript": [
                {
                    "speaker": seg.get("speaker", "Unknown"),
                    "content": seg.get("content", ""),
                    "start_time": seg.get("start_time", 0),
                    "end_time": seg.get("end_time", 0),
                }
                for seg in transcript
            ],
            "summary": summary,
        }
        json_path.write_text(json.dumps(json_data, indent=2, ensure_ascii=False))

        # Write Markdown
        date_display = dt.strftime("%Y-%m-%d %H:%M UTC")
        duration_display = _ms_to_timestamp(duration_ms)

        lines = [
            f"# {recording['filename']}",
            "",
            f"**Date:** {date_display}",
            f"**Duration:** {duration_display}",
            "",
            "## Transcript",
            "",
        ]
        for seg in transcript:
            ts = _ms_to_timestamp(seg.get("start_time", 0))
            speaker = seg.get("speaker", "Unknown")
            content = seg.get("content", "")
            lines.append(f"**{speaker}** [{ts}]: {content}")
            lines.append("")

        lines.append("## Summary")
        lines.append("")
        lines.append(summary)
        lines.append("")

        md_path.write_text("\n".join(lines))

        return "exported"
