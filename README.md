# plaud-downloader

CLI tool that bulk-exports transcripts and AI summaries from [plaud.ai](https://plaud.ai). Can also trigger transcription for unprocessed recordings.

Plaud doesn't have a public API, so this tool talks to the same endpoints their web app uses (reverse-engineered from browser traffic). It works today, but if they change their API, it might break.

## What it does

- Downloads all your recordings as JSON (structured transcript with speaker labels and timestamps) and Markdown (human-readable)
- Organizes files by your Plaud tags/folders
- Triggers transcription for recordings that haven't been processed yet
- Incremental sync: running it again only downloads new stuff

## Requirements

- Python 3.10+
- A plaud.ai account with recordings

## Installation

```bash
git clone https://github.com/Continero/plaud-connector.git
cd plaud-connector
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

After installation, the `plaud` command is available in your terminal (while the venv is active).

## Configuration

Copy the example config and fill in your credentials:

```bash
cp .env.example .env
```

Then edit `.env` with one of these auth methods:

### Option A: Bearer token (Google SSO users, or anyone)

If you signed up with Google, you don't have a password. Grab your token from the browser:

1. Open [app.plaud.ai](https://app.plaud.ai) and sign in
2. Open DevTools (Cmd+Option+I on Mac, F12 on Windows)
3. Go to the Network tab
4. Click any recording to trigger a request
5. Find a request to `api.plaud.ai`, click it, and copy the `Authorization` header value

```env
PLAUD_TOKEN=bearer eyJhbGciOi...
```

The token expires after some time. When it does, repeat the steps above to get a fresh one.

### Option B: Email and password

If you have a regular account with a password:

```env
PLAUD_EMAIL=your@email.com
PLAUD_PASSWORD=your_password
```

### EU accounts

If your account is on the EU instance (check your browser network tab, the requests go to `api-euc1.plaud.ai` instead of `api.plaud.ai`):

```env
PLAUD_API_BASE=https://api-euc1.plaud.ai
```

## Usage

### Quick start: sync everything

The `sync` command does it all in one go. It finds recordings without transcripts, triggers generation, waits for them to finish, and downloads everything.

```bash
plaud sync
```

```
╔══════════════════════════════════════════════╗
║  plaud-downloader                            ║
║  Bulk export transcripts from plaud.ai       ║
╚══════════════════════════════════════════════╝

Step 1/3  Fetching recordings from plaud.ai...
          165 recordings (188.5 hours total)
          162 with transcripts, 3 without

Step 2/3  Generating missing transcripts...
          Triggering transcription for 2 recordings:
            -> Team standup (3811s)
            -> Project review (1820s)

          Waiting for 2 transcriptions to complete...
            Done: Team standup
            Done: Project review

Step 3/3  Downloading transcripts and summaries...
            + Team standup
            + Project review

          2 new, 163 already up to date

══════════════════════════════════════════════
  Sync complete!
  165 recordings  |  2 exported  |  163 skipped
  Output: /Users/you/plaud-downloader/output/
══════════════════════════════════════════════
```

### Individual commands

If you prefer more control:

```bash
plaud list                        # show all recordings
plaud generate --dry-run          # preview what would be transcribed
plaud generate                    # trigger transcription (don't wait)
plaud generate --wait             # trigger and wait for completion
plaud download                    # download to ./output/
plaud download -o ~/plaud-export  # download to custom directory
plaud download --force            # re-download even if files exist
```

### Command options

```
plaud sync [OPTIONS]
  -o, --output TEXT       Output directory (default: output)
  --min-duration INT      Skip recordings shorter than N seconds (default: 10)
  --wait / --no-wait      Wait for transcription (default: --wait)

plaud generate [OPTIONS]
  --min-duration INT      Skip recordings shorter than N seconds (default: 10)
  --dry-run               Show what would be triggered, don't do it
  --wait / --no-wait      Wait for completion (default: --no-wait)

plaud download [OPTIONS]
  -o, --output TEXT       Output directory (default: output)
  --force                 Re-download even if files already exist
```

## Output format

Each recording produces two files, organized into folders matching your Plaud tags. Untagged recordings go to `Unsorted/`.

```
output/
  Work/
    2026-03-17_Team-standup.json
    2026-03-17_Team-standup.md
  Unsorted/
    2026-03-15_Quick-note.json
    2026-03-15_Quick-note.md
```

### JSON

Structured data with transcript segments (speaker, text, timestamps) and the AI-generated summary:

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
  "summary": "# Meeting summary\n\nTeam discussed project status."
}
```

### Markdown

Same content, readable in any text editor or note-taking app:

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

## Troubleshooting

**"Set PLAUD_TOKEN or PLAUD_EMAIL+PLAUD_PASSWORD in .env"** -- The tool can't find credentials. Make sure your `.env` file is in the directory where you run the command, or that the environment variables are set.

**Token expired / 401 errors** -- Bearer tokens expire. Grab a fresh one from your browser DevTools.

**Empty transcripts** -- Some very short recordings (under 10 seconds) don't produce transcripts. The `generate` command skips these by default.

**EU account not working** -- Add `PLAUD_API_BASE=https://api-euc1.plaud.ai` to your `.env`.

## Claude Code skill

If you use [Claude Code](https://claude.com/claude-code), you can add plaud-connector as a skill so Claude can work with your Plaud recordings directly. No CLI installation needed -- Claude will call the API itself.

Copy the `skill/SKILL.md` file to your Claude skills directory:

```bash
cp skill/SKILL.md ~/.claude/skills/plaud-connector/SKILL.md
```

Then set your Plaud credentials as environment variables (or in `.env`), and Claude will be able to list your recordings, download transcripts, trigger transcription, and more.

## Disclaimer

This is an unofficial tool. It uses undocumented API endpoints reverse-engineered from the plaud.ai web app. Plaud could change their API at any time, which would break this tool. Use at your own risk.

## License

MIT
