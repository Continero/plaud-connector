# Plaud Transcript Downloader Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Python CLI that authenticates with plaud.ai, downloads all transcripts + AI summaries, and saves them as JSON and markdown files organized by tag/folder.

**Architecture:** Single package with three modules — `client.py` (API wrapper with email/password auth), `exporter.py` (writes JSON + markdown to disk with skip-existing logic), `cli.py` (click-based CLI). Credentials from `.env` file.

**Tech Stack:** Python 3.10+, requests, click, python-dotenv

---

### Task 1: Project scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `src/plaud_downloader/__init__.py`
- Create: `.env.example`
- Create: `.gitignore`

**Step 1: Create pyproject.toml**

```toml
[project]
name = "plaud-downloader"
version = "0.1.0"
description = "Download transcripts and summaries from plaud.ai"
requires-python = ">=3.10"
dependencies = [
    "requests>=2.31",
    "click>=8.1",
    "python-dotenv>=1.0",
]

[project.scripts]
plaud = "plaud_downloader.cli:cli"

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.backends._legacy:_Backend"

[tool.setuptools.packages.find]
where = ["src"]
```

**Step 2: Create package init**

```python
# src/plaud_downloader/__init__.py
```

**Step 3: Create .env.example**

```
PLAUD_EMAIL=your@email.com
PLAUD_PASSWORD=your_password
# Optional: for EU accounts
# PLAUD_API_BASE=https://api-euc1.plaud.ai
```

**Step 4: Create .gitignore**

```
.env
__pycache__/
*.pyc
dist/
*.egg-info/
.venv/
output/
```

**Step 5: Install in dev mode**

```bash
cd /Users/fogl/Documents/PROJECTS/plaud-downloader
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

**Step 6: Commit**

```bash
git init
git add pyproject.toml src/plaud_downloader/__init__.py .env.example .gitignore
git commit -m "chore: project scaffolding"
```

---

### Task 2: API Client — Authentication

**Files:**
- Create: `src/plaud_downloader/client.py`
- Create: `tests/test_client.py`

**Step 1: Write the failing test**

```python
# tests/test_client.py
import json
from unittest.mock import patch, MagicMock
from plaud_downloader.client import PlaudClient


def test_authenticate_sends_correct_request():
    client = PlaudClient(email="test@example.com", password="secret")
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "status": 0,
        "access_token": "fake_jwt_token",
    }

    with patch("plaud_downloader.client.requests.post", return_value=mock_response) as mock_post:
        client.authenticate()

    mock_post.assert_called_once()
    call_kwargs = mock_post.call_args
    assert "auth/access-token" in call_kwargs[0][0]
    assert client.token == "fake_jwt_token"


def test_authenticate_raises_on_failure():
    client = PlaudClient(email="test@example.com", password="wrong")
    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_response.json.return_value = {"status": 1, "msg": "invalid credentials"}
    mock_response.raise_for_status.side_effect = Exception("401")

    with patch("plaud_downloader.client.requests.post", return_value=mock_response):
        try:
            client.authenticate()
            assert False, "Should have raised"
        except Exception:
            pass
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_client.py -v
```

Expected: FAIL — `ModuleNotFoundError`

**Step 3: Write the client with auth**

```python
# src/plaud_downloader/client.py
import random
import requests


DEFAULT_API_BASE = "https://api.plaud.ai"

HEADERS = {
    "Accept": "*/*",
    "Accept-Language": "en-GB,en-US;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Origin": "https://app.plaud.ai",
    "Referer": "https://app.plaud.ai/",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.6 Safari/605.1.15"
    ),
    "Sec-Fetch-Site": "same-site",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Dest": "empty",
    "app-platform": "web",
    "edit-from": "web",
}


class PlaudClient:
    def __init__(self, email: str, password: str, api_base: str = DEFAULT_API_BASE):
        self.email = email
        self.password = password
        self.api_base = api_base.rstrip("/")
        self.token: str | None = None
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    def _url(self, path: str) -> str:
        return f"{self.api_base}/{path.lstrip('/')}"

    def _add_cache_bust(self, params: dict | None = None) -> dict:
        params = params or {}
        params["r"] = random.random()
        return params

    def authenticate(self) -> None:
        resp = requests.post(
            self._url("/auth/access-token"),
            data={
                "username": self.email,
                "password": self.password,
                "client_id": "web",
            },
            headers={**HEADERS, "Content-Type": "application/x-www-form-urlencoded"},
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") != 0 and "access_token" not in data:
            raise Exception(f"Auth failed: {data.get('msg', 'unknown error')}")
        self.token = data["access_token"]
        self.session.headers["Authorization"] = f"bearer {self.token}"
```

**Step 4: Run tests**

```bash
pytest tests/test_client.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add src/plaud_downloader/client.py tests/test_client.py
git commit -m "feat: add PlaudClient with email/password authentication"
```

---

### Task 3: API Client — List Recordings + Tags

**Files:**
- Modify: `src/plaud_downloader/client.py`
- Modify: `tests/test_client.py`

**Step 1: Write failing tests**

Add to `tests/test_client.py`:

```python
def _authed_client():
    client = PlaudClient(email="test@example.com", password="secret")
    client.token = "fake_token"
    client.session.headers["Authorization"] = "bearer fake_token"
    return client


def test_list_recordings_returns_file_list():
    client = _authed_client()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "status": 0,
        "data_file_list": [
            {"id": "abc123", "filename": "Meeting", "start_time": 1700000000000}
        ],
    }

    with patch.object(client.session, "get", return_value=mock_response):
        files = client.list_recordings()

    assert len(files) == 1
    assert files[0]["id"] == "abc123"


def test_get_tags_returns_tag_list():
    client = _authed_client()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "status": 0,
        "data_filetag_list": [
            {"id": "tag1", "name": "Work"}
        ],
    }

    with patch.object(client.session, "get", return_value=mock_response):
        tags = client.get_tags()

    assert len(tags) == 1
    assert tags[0]["name"] == "Work"


def test_get_recording_details():
    client = _authed_client()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "status": 0,
        "data_file_list": [
            {
                "id": "abc123",
                "filename": "Meeting",
                "trans_result": [{"speaker": "S1", "content": "Hello"}],
                "ai_content": "# Summary",
            }
        ],
    }

    with patch.object(client.session, "post", return_value=mock_response):
        details = client.get_recording_details(["abc123"])

    assert details[0]["trans_result"][0]["content"] == "Hello"
```

**Step 2: Run to verify failure**

```bash
pytest tests/test_client.py -v
```

**Step 3: Add methods to client.py**

Add to `PlaudClient` class:

```python
    def list_recordings(self, limit: int = 200) -> list[dict]:
        all_files = []
        skip = 0
        while True:
            resp = self.session.get(
                self._url("/file/simple/web"),
                params=self._add_cache_bust({
                    "skip": skip,
                    "limit": limit,
                    "is_trash": 0,
                    "sort_by": "start_time",
                    "is_desc": "true",
                }),
            )
            resp.raise_for_status()
            data = resp.json()
            files = data.get("data_file_list", [])
            if not files:
                break
            all_files.extend(files)
            if len(files) < limit:
                break
            skip += limit
        return all_files

    def get_recording_details(self, file_ids: list[str]) -> list[dict]:
        resp = self.session.post(
            self._url("/file/list"),
            params=self._add_cache_bust({"support_mul_summ": "true"}),
            json=file_ids,
        )
        resp.raise_for_status()
        return resp.json().get("data_file_list", [])

    def get_tags(self) -> list[dict]:
        resp = self.session.get(
            self._url("/filetag/"),
            params=self._add_cache_bust(),
        )
        resp.raise_for_status()
        return resp.json().get("data_filetag_list", [])
```

**Step 4: Run tests**

```bash
pytest tests/test_client.py -v
```

**Step 5: Commit**

```bash
git add src/plaud_downloader/client.py tests/test_client.py
git commit -m "feat: add recording listing, details, and tags endpoints"
```

---

### Task 4: Exporter — JSON + Markdown Output

**Files:**
- Create: `src/plaud_downloader/exporter.py`
- Create: `tests/test_exporter.py`

**Step 1: Write failing tests**

```python
# tests/test_exporter.py
import json
from pathlib import Path
from plaud_downloader.exporter import Exporter


SAMPLE_RECORDING = {
    "id": "abc123",
    "filename": "Team Standup",
    "start_time": 1700000000000,
    "duration": 300000,
    "filetag_id_list": ["tag1"],
    "trans_result": [
        {"speaker": "Alice", "content": "Good morning everyone.", "start_time": 0, "end_time": 3000},
        {"speaker": "Bob", "content": "Morning! Let's start.", "start_time": 3100, "end_time": 5500},
    ],
    "ai_content": "# Meeting Summary\n\nTeam discussed project status.",
}

TAGS = [{"id": "tag1", "name": "Work"}]


def test_export_creates_json_file(tmp_path):
    exporter = Exporter(output_dir=tmp_path, tags=TAGS)
    exporter.export_recording(SAMPLE_RECORDING)

    json_path = tmp_path / "Work" / "2023-11-14_Team-Standup.json"
    assert json_path.exists()
    data = json.loads(json_path.read_text())
    assert data["filename"] == "Team Standup"
    assert len(data["transcript"]) == 2


def test_export_creates_markdown_file(tmp_path):
    exporter = Exporter(output_dir=tmp_path, tags=TAGS)
    exporter.export_recording(SAMPLE_RECORDING)

    md_path = tmp_path / "Work" / "2023-11-14_Team-Standup.md"
    assert md_path.exists()
    content = md_path.read_text()
    assert "Alice" in content
    assert "Good morning everyone." in content
    assert "Meeting Summary" in content


def test_export_skips_existing(tmp_path):
    exporter = Exporter(output_dir=tmp_path, tags=TAGS)
    exporter.export_recording(SAMPLE_RECORDING)
    # Export again — should skip
    result = exporter.export_recording(SAMPLE_RECORDING)
    assert result == "skipped"


def test_export_untagged_goes_to_unsorted(tmp_path):
    recording = {**SAMPLE_RECORDING, "filetag_id_list": []}
    exporter = Exporter(output_dir=tmp_path, tags=TAGS)
    exporter.export_recording(recording)

    json_path = tmp_path / "Unsorted" / "2023-11-14_Team-Standup.json"
    assert json_path.exists()
```

**Step 2: Run to verify failure**

```bash
pytest tests/test_exporter.py -v
```

**Step 3: Implement exporter**

```python
# src/plaud_downloader/exporter.py
import json
import re
from datetime import datetime, timezone
from pathlib import Path


def _sanitize_filename(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', "-", name).strip().rstrip(".")


def _ms_to_timestamp(ms: int) -> str:
    s = ms // 1000
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def _parse_ai_content(raw: str | None) -> str:
    if not raw:
        return ""
    if raw.startswith("{"):
        try:
            parsed = json.loads(raw)
            if "markdown" in parsed:
                return parsed["markdown"]
            if "content" in parsed and isinstance(parsed["content"], dict):
                return parsed["content"].get("markdown", "")
            if "summary" in parsed:
                return parsed["summary"]
        except json.JSONDecodeError:
            pass
    return raw


class Exporter:
    def __init__(self, output_dir: Path, tags: list[dict]):
        self.output_dir = Path(output_dir)
        self.tag_map = {t["id"]: t["name"] for t in tags}

    def _get_folder(self, recording: dict) -> str:
        tag_ids = recording.get("filetag_id_list") or []
        for tid in tag_ids:
            if tid in self.tag_map:
                return _sanitize_filename(self.tag_map[tid])
        return "Unsorted"

    def _get_stem(self, recording: dict) -> str:
        ts = recording.get("start_time", 0)
        dt = datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
        date_str = dt.strftime("%Y-%m-%d")
        name = _sanitize_filename(recording.get("filename", "untitled"))
        return f"{date_str}_{name}"

    def export_recording(self, recording: dict) -> str:
        folder = self._get_folder(recording)
        stem = self._get_stem(recording)
        out_dir = self.output_dir / folder
        json_path = out_dir / f"{stem}.json"
        md_path = out_dir / f"{stem}.md"

        if json_path.exists():
            return "skipped"

        out_dir.mkdir(parents=True, exist_ok=True)

        transcript = recording.get("trans_result") or []
        summary = _parse_ai_content(recording.get("ai_content"))

        # JSON output
        json_data = {
            "id": recording["id"],
            "filename": recording.get("filename", ""),
            "start_time": recording.get("start_time"),
            "duration_ms": recording.get("duration"),
            "transcript": transcript,
            "summary": summary,
        }
        json_path.write_text(json.dumps(json_data, indent=2, ensure_ascii=False))

        # Markdown output
        lines = [
            f"# {recording.get('filename', 'Untitled')}",
            "",
            f"**Date:** {datetime.fromtimestamp(recording.get('start_time', 0) / 1000, tz=timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
            f"**Duration:** {_ms_to_timestamp(recording.get('duration', 0))}",
            "",
            "## Transcript",
            "",
        ]
        for seg in transcript:
            ts = _ms_to_timestamp(seg.get("start_time", 0))
            lines.append(f"**{seg.get('speaker', 'Unknown')}** [{ts}]: {seg.get('content', '')}")
            lines.append("")

        if summary:
            lines.append("## Summary")
            lines.append("")
            lines.append(summary)
            lines.append("")

        md_path.write_text("\n".join(lines), encoding="utf-8")
        return "exported"
```

**Step 4: Run tests**

```bash
pytest tests/test_exporter.py -v
```

**Step 5: Commit**

```bash
git add src/plaud_downloader/exporter.py tests/test_exporter.py
git commit -m "feat: add exporter with JSON and markdown output"
```

---

### Task 5: CLI

**Files:**
- Create: `src/plaud_downloader/cli.py`
- Create: `tests/test_cli.py`

**Step 1: Write failing test**

```python
# tests/test_cli.py
from unittest.mock import patch, MagicMock
from click.testing import CliRunner
from plaud_downloader.cli import cli


@patch("plaud_downloader.cli.PlaudClient")
def test_list_command(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_client.list_recordings.return_value = [
        {"id": "1", "filename": "Meeting", "start_time": 1700000000000, "duration": 60000}
    ]

    runner = CliRunner(env={"PLAUD_EMAIL": "a@b.com", "PLAUD_PASSWORD": "pass"})
    result = runner.invoke(cli, ["list"])

    assert result.exit_code == 0
    assert "Meeting" in result.output


@patch("plaud_downloader.cli.PlaudClient")
@patch("plaud_downloader.cli.Exporter")
def test_download_command(mock_exporter_cls, mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_client.list_recordings.return_value = [
        {"id": "1", "filename": "Meeting", "start_time": 1700000000000}
    ]
    mock_client.get_tags.return_value = []
    mock_client.get_recording_details.return_value = [
        {"id": "1", "filename": "Meeting", "start_time": 1700000000000, "trans_result": [], "ai_content": ""}
    ]
    mock_exporter = MagicMock()
    mock_exporter_cls.return_value = mock_exporter
    mock_exporter.export_recording.return_value = "exported"

    runner = CliRunner(env={"PLAUD_EMAIL": "a@b.com", "PLAUD_PASSWORD": "pass"})
    result = runner.invoke(cli, ["download", "--output", "/tmp/test_plaud"])

    assert result.exit_code == 0
    mock_exporter.export_recording.assert_called_once()
```

**Step 2: Run to verify failure**

```bash
pytest tests/test_cli.py -v
```

**Step 3: Implement CLI**

```python
# src/plaud_downloader/cli.py
import os
from datetime import datetime, timezone
from pathlib import Path

import click
from dotenv import load_dotenv

from plaud_downloader.client import PlaudClient
from plaud_downloader.exporter import Exporter


@click.group()
def cli():
    """Download transcripts and summaries from plaud.ai"""
    load_dotenv()


def _get_client() -> PlaudClient:
    email = os.environ.get("PLAUD_EMAIL")
    password = os.environ.get("PLAUD_PASSWORD")
    api_base = os.environ.get("PLAUD_API_BASE", "https://api.plaud.ai")
    if not email or not password:
        raise click.ClickException("Set PLAUD_EMAIL and PLAUD_PASSWORD in .env")
    client = PlaudClient(email=email, password=password, api_base=api_base)
    client.authenticate()
    return client


@cli.command()
def list():
    """List all recordings"""
    client = _get_client()
    recordings = client.list_recordings()
    click.echo(f"Found {len(recordings)} recordings:\n")
    for r in recordings:
        ts = r.get("start_time", 0)
        dt = datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
        dur = r.get("duration", 0) // 1000
        click.echo(f"  {dt.strftime('%Y-%m-%d %H:%M')}  {dur:>5}s  {r.get('filename', 'untitled')}")


@cli.command()
@click.option("--output", "-o", default="output", help="Output directory")
def download(output):
    """Download all transcripts and summaries"""
    client = _get_client()

    click.echo("Fetching recordings...")
    recordings = client.list_recordings()
    click.echo(f"Found {len(recordings)} recordings")

    click.echo("Fetching tags...")
    tags = client.get_tags()

    exporter = Exporter(output_dir=Path(output), tags=tags)

    file_ids = [r["id"] for r in recordings]

    # Batch details in chunks of 20
    batch_size = 20
    exported = 0
    skipped = 0
    for i in range(0, len(file_ids), batch_size):
        batch_ids = file_ids[i : i + batch_size]
        details = client.get_recording_details(batch_ids)
        for rec in details:
            result = exporter.export_recording(rec)
            if result == "exported":
                exported += 1
                click.echo(f"  Exported: {rec.get('filename', 'untitled')}")
            else:
                skipped += 1

    click.echo(f"\nDone! Exported {exported}, skipped {skipped} (already existed)")
```

**Step 4: Run all tests**

```bash
pytest tests/ -v
```

**Step 5: Commit**

```bash
git add src/plaud_downloader/cli.py tests/test_cli.py
git commit -m "feat: add CLI with list and download commands"
```

---

### Task 6: Integration test with real .env (manual)

**Step 1: Create .env with real credentials**

```bash
cp .env.example .env
# Edit .env with real email/password
```

**Step 2: Test list command**

```bash
plaud list
```

Expected: list of recordings with dates and names

**Step 3: Test download command**

```bash
plaud download -o output
```

Expected: JSON + MD files in `output/` organized by tag folders

**Step 4: Verify output**

```bash
find output -type f | head -20
cat output/*/$(ls output/*/*.md | head -1)
```

**Step 5: Final commit**

```bash
git add -A
git commit -m "chore: ready for first release"
```
