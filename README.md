# plaud-downloader

Bulk export transcripts and AI summaries from [plaud.ai](https://plaud.ai). Also triggers transcription for unprocessed recordings.

Uses the unofficial plaud.ai web API (reverse-engineered from browser traffic). No official API exists yet.

## Install

```bash
git clone git@github.com:Continero/plaud-downloader.git
cd plaud-downloader
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Setup

Copy the example env file and add your credentials:

```bash
cp .env.example .env
```

### Authentication

**Option 1: Bearer token (Google SSO users)**

1. Go to [app.plaud.ai](https://app.plaud.ai) and sign in
2. Open DevTools (Cmd+Option+I / F12) -> Network tab
3. Find any request to `api.plaud.ai` -> copy the `Authorization` header value

```env
PLAUD_TOKEN=bearer eyJ...
```

**Option 2: Email/password**

```env
PLAUD_EMAIL=your@email.com
PLAUD_PASSWORD=your_password
```

**EU accounts** need a different API host:

```env
PLAUD_API_BASE=https://api-euc1.plaud.ai
```

## Usage

### List recordings

```bash
plaud list
```

```
Found 158 recordings:

  2026-03-13 09:02   1096s  Team standup
  2026-03-12 12:26   8220s  Project review
  ...
```

### Download transcripts and summaries

```bash
plaud download              # exports to ./output/
plaud download -o ~/plaud   # custom output directory
```

Each recording produces two files:

- `{date}_{name}.json` — structured data (transcript segments with speaker labels + timestamps, AI summary)
- `{date}_{name}.md` — human-readable markdown

Files are organized by Plaud tag/folder. Untagged recordings go to `Unsorted/`.

Running again skips already-exported files (incremental sync).

### Trigger transcription for unprocessed recordings

```bash
plaud generate --dry-run    # preview what would be triggered
plaud generate              # trigger transcription for all
plaud generate --wait       # trigger and poll until complete
plaud generate --min-duration 60  # skip recordings under 60s
```

After generation completes, run `plaud download` to fetch the new transcripts.

## Output format

### JSON

```json
{
  "id": "abc123",
  "filename": "Team standup",
  "start_time": 1700000000000,
  "duration_ms": 300000,
  "transcript": [
    {
      "speaker": "Alice",
      "content": "Good morning everyone.",
      "start_time": 0,
      "end_time": 3000
    }
  ],
  "summary": "# Meeting Summary\n\nTeam discussed project status."
}
```

### Markdown

```markdown
# Team standup

**Date:** 2023-11-14 12:00 UTC
**Duration:** 00:05:00

## Transcript

**Alice** [00:00:00]: Good morning everyone.

**Bob** [00:00:03]: Morning! Let's start.

## Summary

Team discussed project status.
```

## Disclaimer

This tool uses an unofficial, undocumented API reverse-engineered from the plaud.ai web app. It may break if Plaud changes their API. Use at your own risk.

## License

MIT
