"""Tests for the Exporter class."""

import json
from pathlib import Path

import pytest

from plaud_downloader.exporter import (
    Exporter,
    _ms_to_timestamp,
    _parse_ai_content,
    _sanitize_filename,
)

SAMPLE_RECORDING = {
    "id": "abc123",
    "filename": "Team Standup",
    "start_time": 1700000000000,  # 2023-11-14
    "duration": 300000,
    "filetag_id_list": ["tag1"],
    "trans_result": [
        {
            "speaker": "Alice",
            "content": "Good morning everyone.",
            "start_time": 0,
            "end_time": 3000,
        },
        {
            "speaker": "Bob",
            "content": "Morning! Let's start.",
            "start_time": 3100,
            "end_time": 5500,
        },
    ],
    "ai_content": "# Meeting Summary\n\nTeam discussed project status.",
}

TAGS = [{"id": "tag1", "name": "Work"}]


class TestSanitizeFilename:
    def test_replaces_forbidden_chars(self):
        assert _sanitize_filename('a<b>c:d"e/f\\g|h?i*j') == "a-b-c-d-e-f-g-h-i-j"

    def test_leaves_normal_chars(self):
        assert _sanitize_filename("hello world") == "hello world"


class TestMsToTimestamp:
    def test_zero(self):
        assert _ms_to_timestamp(0) == "00:00:00"

    def test_five_minutes(self):
        assert _ms_to_timestamp(300000) == "00:05:00"

    def test_hours(self):
        assert _ms_to_timestamp(3661000) == "01:01:01"


class TestParseAiContent:
    def test_plain_markdown(self):
        assert _parse_ai_content("# Hello") == "# Hello"

    def test_json_with_markdown_key(self):
        raw = json.dumps({"markdown": "summary text"})
        assert _parse_ai_content(raw) == "summary text"

    def test_json_with_nested_content_markdown(self):
        raw = json.dumps({"content": {"markdown": "nested summary"}})
        assert _parse_ai_content(raw) == "nested summary"

    def test_json_with_summary_key(self):
        raw = json.dumps({"summary": "fallback summary"})
        assert _parse_ai_content(raw) == "fallback summary"

    def test_none_input(self):
        assert _parse_ai_content(None) == ""

    def test_empty_string(self):
        assert _parse_ai_content("") == ""


class TestExporter:
    def test_export_creates_json_with_correct_structure(self, tmp_path):
        exporter = Exporter(output_dir=tmp_path, tags=TAGS)
        result = exporter.export_recording(SAMPLE_RECORDING)

        assert result == "exported"

        json_file = tmp_path / "Work" / "2023-11-14_Team Standup.json"
        assert json_file.exists()

        data = json.loads(json_file.read_text())
        assert data["id"] == "abc123"
        assert data["filename"] == "Team Standup"
        assert data["start_time"] == 1700000000000
        assert data["duration_ms"] == 300000
        assert len(data["transcript"]) == 2
        assert data["transcript"][0]["speaker"] == "Alice"
        assert "summary" in data

    def test_export_creates_markdown_with_speakers_and_timestamps(self, tmp_path):
        exporter = Exporter(output_dir=tmp_path, tags=TAGS)
        exporter.export_recording(SAMPLE_RECORDING)

        md_file = tmp_path / "Work" / "2023-11-14_Team Standup.md"
        assert md_file.exists()

        content = md_file.read_text()
        assert "# Team Standup" in content
        assert "**Date:**" in content
        assert "**Duration:** 00:05:00" in content
        assert "## Transcript" in content
        assert "**Alice** [00:00:00]:" in content
        assert "**Bob** [00:00:03]:" in content
        assert "## Summary" in content
        assert "Team discussed project status." in content

    def test_skip_existing_returns_skipped(self, tmp_path):
        exporter = Exporter(output_dir=tmp_path, tags=TAGS)
        assert exporter.export_recording(SAMPLE_RECORDING) == "exported"
        assert exporter.export_recording(SAMPLE_RECORDING) == "skipped"

    def test_untagged_recordings_go_to_unsorted(self, tmp_path):
        recording = {**SAMPLE_RECORDING, "filetag_id_list": []}
        exporter = Exporter(output_dir=tmp_path, tags=TAGS)
        exporter.export_recording(recording)

        json_file = tmp_path / "Unsorted" / "2023-11-14_Team Standup.json"
        assert json_file.exists()

    def test_untagged_recordings_none_tag_list(self, tmp_path):
        recording = {**SAMPLE_RECORDING, "filetag_id_list": None}
        exporter = Exporter(output_dir=tmp_path, tags=TAGS)
        exporter.export_recording(recording)

        json_file = tmp_path / "Unsorted" / "2023-11-14_Team Standup.json"
        assert json_file.exists()

    def test_forbidden_chars_in_filename(self, tmp_path):
        recording = {**SAMPLE_RECORDING, "filename": "meeting: recap?"}
        exporter = Exporter(output_dir=tmp_path, tags=TAGS)
        exporter.export_recording(recording)

        json_file = tmp_path / "Work" / "2023-11-14_meeting- recap-.json"
        assert json_file.exists()
