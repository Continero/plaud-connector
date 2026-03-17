---
name: plaud-connector
description: |
  Export transcripts and AI summaries from plaud.ai recordings.
  Use when user mentions Plaud, plaud.ai, meeting recordings export,
  or wants to download/sync transcripts from their Plaud device.
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - Grep
  - Glob
  - AskUserQuestion
  - WebFetch
---

# Plaud Connector: Export transcripts from plaud.ai

Download transcripts, speaker-labeled segments, and AI summaries from a Plaud account. Works with the unofficial plaud.ai web API.

## Setup

Before doing anything, check if the user has credentials configured.

**Required:** One of these in a `.env` file or as environment variables:

```
# Bearer token (for Google SSO users or anyone)
# Get from browser: app.plaud.ai -> DevTools -> Network -> Authorization header
PLAUD_TOKEN=bearer eyJ...

# OR email/password
PLAUD_EMAIL=your@email.com
PLAUD_PASSWORD=your_password

# EU accounts need this:
PLAUD_API_BASE=https://api-euc1.plaud.ai
```

If the user doesn't have credentials yet, walk them through getting a bearer token:
1. Open [app.plaud.ai](https://app.plaud.ai) and sign in
2. Open DevTools (Cmd+Option+I / F12) -> Network tab
3. Click any recording
4. Find a request to `api.plaud.ai`, copy the `Authorization` header value

## Two modes

### Mode A: CLI (if plaud-connector is installed)

Check if the `plaud` command exists:
```bash
which plaud
```

If installed, use these commands:
```bash
plaud sync -o output          # full sync: generate + download
plaud list                    # list all recordings
plaud generate --dry-run      # preview what needs transcription
plaud generate --wait         # trigger and wait for transcription
plaud download -o output      # download transcripts
plaud download -o output --force  # re-download everything
```

If not installed and the user wants it:
```bash
git clone https://github.com/Continero/plaud-connector.git
cd plaud-connector
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
```

### Mode B: Direct API (no installation needed)

Use this inline Python script. It needs only the `requests` library (install with `pip install requests` if missing).

```python
import json, os, random, time
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import urlencode
import requests

# --- Config ---
TOKEN = os.environ.get("PLAUD_TOKEN", "").removeprefix("bearer ").removeprefix("Bearer ")
BASE = os.environ.get("PLAUD_API_BASE", "https://api.plaud.ai").rstrip("/")
OUTPUT = "output"

HEADERS = {
    "Accept": "*/*",
    "Origin": "https://app.plaud.ai",
    "Referer": "https://app.plaud.ai/",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.6 Safari/605.1.15",
    "Sec-Fetch-Site": "same-site",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Dest": "empty",
    "app-platform": "web",
    "edit-from": "web",
    "Authorization": f"bearer {TOKEN}",
}

session = requests.Session()
session.headers.update(HEADERS)

def api_get(path, params=None):
    params = dict(params or {})
    params["r"] = random.random()
    resp = session.get(f"{BASE}{path}?{urlencode(params)}")
    resp.raise_for_status()
    return resp.json()

def list_recordings():
    all_files, skip = [], 0
    while True:
        data = api_get("/file/simple/web", {"skip": skip, "limit": 200, "is_trash": 0, "sort_by": "start_time", "is_desc": "true"})
        page = data.get("data_file_list", [])
        all_files.extend(page)
        if len(page) < 200:
            break
        skip += 200
    return all_files

def get_details(file_ids):
    resp = session.post(f"{BASE}/file/list?support_mul_summ=true", json=file_ids)
    resp.raise_for_status()
    return resp.json().get("data_file_list", [])

def start_transcription(file_id):
    session.patch(f"{BASE}/file/{file_id}", json={
        "extra_data": {"tranConfig": {"language": "auto", "type_type": "system", "type": "REASONING-NOTE", "diarization": 1, "llm": "auto"}}
    }).raise_for_status()
    resp = session.post(f"{BASE}/ai/transsumm/{file_id}", json={
        "is_reload": 1, "summ_type": "REASONING-NOTE", "summ_type_type": "system",
        "info": '{"language": "auto", "diarization": 1, "llm": "auto"}', "support_mul_summ": True,
    })
    resp.raise_for_status()
    return resp.json()

def poll_transcription(file_id):
    resp = session.post(f"{BASE}/ai/transsumm/{file_id}", json={
        "is_reload": 0, "summ_type": "REASONING-NOTE", "summ_type_type": "system",
        "info": '{"language": "auto", "diarization": 1, "llm": "auto"}', "support_mul_summ": True,
    })
    resp.raise_for_status()
    return resp.json()

def get_tags():
    return api_get("/filetag/").get("data_filetag_list", [])
```

Adapt the script for whatever the user needs. Common tasks below.

## Common tasks

### List recordings
```python
recordings = list_recordings()
print(f"{len(recordings)} recordings")
for r in recordings:
    dt = datetime.fromtimestamp(r["start_time"] / 1000, tz=timezone.utc)
    dur = r.get("duration", 0) // 1000
    print(f"  {dt:%Y-%m-%d %H:%M}  {dur:>5}s  {r.get('filename', '?')}")
```

### Download all transcripts as JSON + Markdown
```python
recordings = list_recordings()
tags = {t["id"]: t["name"] for t in get_tags()}
file_ids = [r["id"] for r in recordings]

for i in range(0, len(file_ids), 20):
    batch = get_details(file_ids[i:i+20])
    for rec in batch:
        tag_ids = rec.get("filetag_id_list") or []
        folder = "Unsorted"
        for tid in tag_ids:
            if tid in tags:
                folder = tags[tid]
                break

        dt = datetime.fromtimestamp(rec["start_time"] / 1000, tz=timezone.utc)
        import re
        safe_name = re.sub(r'[<>:"/\\|?*]', '-', rec["filename"])
        stem = f"{dt:%Y-%m-%d}_{safe_name}"
        out = Path(OUTPUT) / folder
        out.mkdir(parents=True, exist_ok=True)

        if (out / f"{stem}.json").exists():
            continue

        transcript = rec.get("trans_result") or []
        ai_content = rec.get("ai_content") or ""
        # ai_content can be plain markdown or JSON with a "markdown" key
        if ai_content.startswith("{"):
            try:
                parsed = json.loads(ai_content)
                ai_content = parsed.get("markdown") or parsed.get("summary") or ai_content
            except json.JSONDecodeError:
                pass

        json_data = {
            "id": rec["id"], "filename": rec["filename"],
            "start_time": rec["start_time"], "duration_ms": rec.get("duration", 0),
            "transcript": [{"speaker": s.get("speaker", "?"), "content": s.get("content", ""),
                           "start_time": s.get("start_time", 0), "end_time": s.get("end_time", 0)} for s in transcript],
            "summary": ai_content,
        }
        (out / f"{stem}.json").write_text(json.dumps(json_data, indent=2, ensure_ascii=False))

        dur_s = rec.get("duration", 0) // 1000
        lines = [f"# {rec['filename']}", "", f"**Date:** {dt:%Y-%m-%d %H:%M UTC}",
                 f"**Duration:** {dur_s // 3600:02d}:{(dur_s % 3600) // 60:02d}:{dur_s % 60:02d}", "", "## Transcript", ""]
        for s in transcript:
            ts = s.get("start_time", 0) // 1000
            lines.append(f"**{s.get('speaker', '?')}** [{ts // 3600:02d}:{(ts % 3600) // 60:02d}:{ts % 60:02d}]: {s.get('content', '')}")
            lines.append("")
        lines += ["## Summary", "", ai_content, ""]
        (out / f"{stem}.md").write_text("\n".join(lines))
        print(f"  + {rec['filename']}")

print("Done!")
```

### Trigger transcription for unprocessed recordings
```python
recordings = list_recordings()
missing = [r for r in recordings if not r.get("is_trans") and r.get("duration", 0) // 1000 >= 10]
print(f"{len(missing)} recordings without transcripts")
for r in missing:
    start_transcription(r["id"])
    print(f"  Started: {r.get('filename', '?')}")

# Poll until done
pending = {r["id"]: r.get("filename", "?") for r in missing}
while pending:
    time.sleep(15)
    for fid in list(pending):
        if poll_transcription(fid).get("status") == 1:
            print(f"  Done: {pending.pop(fid)}")
    if pending:
        print(f"  Waiting on {len(pending)}...")
print("All done!")
```

## API reference

All requests need the browser-mimicking headers defined above. GET requests need a random `r=` cache-busting parameter.

| Endpoint | Method | Body | Returns |
|----------|--------|------|---------|
| `/file/simple/web?skip=0&limit=200&is_trash=0&sort_by=start_time&is_desc=true` | GET | - | `{data_file_list: [...]}` with basic recording info |
| `/file/list?support_mul_summ=true` | POST | JSON array of file IDs | `{data_file_list: [...]}` with full details (transcript, AI content) |
| `/file/{id}` | PATCH | JSON config (see start_transcription) | Sets transcription config |
| `/ai/transsumm/{id}` | POST | `{is_reload: 1, ...}` | Triggers transcription job |
| `/ai/transsumm/{id}` | POST | `{is_reload: 0, ...}` | Polls status: `0`=not started, `-111`=transcript done/summary pending, `1`=complete |
| `/filetag/` | GET | - | `{data_filetag_list: [...]}` with tag id/name |
| `/auth/access-token` | POST | form: `username`, `password`, `client_id=web` | `{access_token: "..."}` |

## Important details

- Authorization header uses lowercase `bearer` (not `Bearer`)
- EU accounts use `https://api-euc1.plaud.ai` instead of `https://api.plaud.ai`
- Bearer tokens expire after some time. If you get 401 errors, the user needs a fresh token from their browser.
- Triggering transcription is a two-step process: PATCH sets config, POST to `/ai/transsumm` with `is_reload=1` actually starts it. PATCH alone does nothing.
- The `ai_content` field can be plain markdown, or a JSON string containing `{"markdown": "..."}` or `{"content": {"markdown": "..."}}` or `{"summary": "..."}`. Parse accordingly.
- Some transcript segments may be missing `speaker` or `content` keys. Always use `.get()` with defaults.
- Fetching details works in batches. Don't send more than 20 IDs at once to `/file/list`.
