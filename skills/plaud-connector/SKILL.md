---
name: plaud-connector
description: |
  Export transcripts and AI summaries from plaud.ai recordings.
  Use when user mentions Plaud, plaud.ai, meeting recordings export,
  or wants to download/sync transcripts from their Plaud device.
allowed-tools:
  - Bash
  - Write
  - Read
  - AskUserQuestion
---

# Plaud Connector: Export transcripts from plaud.ai

Download transcripts, speaker-labeled segments, and AI summaries from a Plaud account. Works with the unofficial plaud.ai web API.

## First: get credentials

Before doing anything, ask the user for their Plaud credentials. They need one of:

- **Bearer token** (most common, required for Google SSO users)
- **Email + password** (for users with a regular Plaud account)

If they don't know how to get a token, walk them through it:

1. Open [app.plaud.ai](https://app.plaud.ai) and sign in
2. Open DevTools (Cmd+Option+I on Mac, F12 on Windows) -> Network tab
3. Click any recording to trigger an API request
4. Find a request to `api.plaud.ai`, click it, copy the full `Authorization` header value

EU accounts use a different API host (`https://api-euc1.plaud.ai`). Ask the user if they're on an EU account, or check if their token came from `api-euc1.plaud.ai` in the network tab.

Once you have credentials, set them as environment variables before running any scripts:
```bash
export PLAUD_TOKEN="bearer eyJ..."
# OR
export PLAUD_EMAIL="user@example.com"
export PLAUD_PASSWORD="password"

# EU accounts only:
export PLAUD_API_BASE="https://api-euc1.plaud.ai"
```

## Two modes of operation

### Mode A: CLI (if plaud-connector is installed)

Check first:
```bash
which plaud 2>/dev/null && echo "CLI available" || echo "CLI not installed"
```

If installed, these commands do everything:
```bash
plaud sync -o output          # full sync: generate missing transcripts + download all
plaud list                    # list all recordings
plaud generate --dry-run      # preview what needs transcription
plaud generate --wait         # trigger transcription and wait
plaud download -o output      # download transcripts as JSON + Markdown
```

To install the CLI:
```bash
git clone https://github.com/Continero/plaud-connector.git
cd plaud-connector
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
```

### Mode B: Direct API (no installation)

If the CLI is not installed, write and run a Python script directly. Requires only the `requests` library.

```bash
pip install requests 2>/dev/null
```

Write the script to a temp file and execute it:

```bash
python3 /tmp/plaud_task.py
```

Use the API helper code and task recipes below to build the script.

## API helper code

Every script should start with this. Write it as part of `/tmp/plaud_task.py`:

```python
import json, os, random, re, time
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import urlencode
import requests

TOKEN = os.environ.get("PLAUD_TOKEN", "").removeprefix("bearer ").removeprefix("Bearer ")
EMAIL = os.environ.get("PLAUD_EMAIL", "")
PASSWORD = os.environ.get("PLAUD_PASSWORD", "")
BASE = os.environ.get("PLAUD_API_BASE", "https://api.plaud.ai").rstrip("/")

HEADERS = {
    "Accept": "*/*",
    "Origin": "https://app.plaud.ai",
    "Referer": "https://app.plaud.ai/",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15",
    "Sec-Fetch-Site": "same-site",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Dest": "empty",
    "app-platform": "web",
    "edit-from": "web",
}

session = requests.Session()
session.headers.update(HEADERS)

# Authenticate
if TOKEN:
    session.headers["Authorization"] = f"bearer {TOKEN}"
elif EMAIL and PASSWORD:
    resp = session.post(f"{BASE}/auth/access-token",
                        data={"username": EMAIL, "password": PASSWORD, "client_id": "web"})
    resp.raise_for_status()
    session.headers["Authorization"] = f"bearer {resp.json()['access_token']}"
else:
    raise SystemExit("Set PLAUD_TOKEN or PLAUD_EMAIL+PLAUD_PASSWORD environment variables")

def api_get(path, params=None):
    params = dict(params or {})
    params["r"] = random.random()
    resp = session.get(f"{BASE}{path}?{urlencode(params)}")
    resp.raise_for_status()
    return resp.json()

def list_recordings():
    all_files, skip = [], 0
    while True:
        data = api_get("/file/simple/web",
                       {"skip": skip, "limit": 200, "is_trash": 0,
                        "sort_by": "start_time", "is_desc": "true"})
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
        "extra_data": {"tranConfig": {
            "language": "auto", "type_type": "system",
            "type": "REASONING-NOTE", "diarization": 1, "llm": "auto"
        }}
    }).raise_for_status()
    resp = session.post(f"{BASE}/ai/transsumm/{file_id}", json={
        "is_reload": 1, "summ_type": "REASONING-NOTE", "summ_type_type": "system",
        "info": '{"language": "auto", "diarization": 1, "llm": "auto"}',
        "support_mul_summ": True,
    })
    resp.raise_for_status()
    return resp.json()

def poll_transcription(file_id):
    resp = session.post(f"{BASE}/ai/transsumm/{file_id}", json={
        "is_reload": 0, "summ_type": "REASONING-NOTE", "summ_type_type": "system",
        "info": '{"language": "auto", "diarization": 1, "llm": "auto"}',
        "support_mul_summ": True,
    })
    resp.raise_for_status()
    return resp.json()

def get_tags():
    return api_get("/filetag/").get("data_filetag_list", [])

def parse_ai_content(raw):
    if not raw or not raw.startswith("{"):
        return raw or ""
    try:
        p = json.loads(raw)
        return p.get("markdown") or (p.get("content", {}) or {}).get("markdown") or p.get("summary") or raw
    except (json.JSONDecodeError, TypeError, AttributeError):
        return raw

def fmt_duration(ms):
    s = ms // 1000
    return f"{s // 3600:02d}:{(s % 3600) // 60:02d}:{s % 60:02d}"
```

## Task recipes

Append one of these after the helper code in the script.

### List all recordings

```python
recordings = list_recordings()
print(f"{len(recordings)} recordings\n")
for r in recordings:
    dt = datetime.fromtimestamp(r["start_time"] / 1000, tz=timezone.utc)
    dur = r.get("duration", 0) // 1000
    has_trans = "yes" if r.get("is_trans") else "no"
    print(f"  {dt:%Y-%m-%d %H:%M}  {dur:>5}s  [transcript: {has_trans}]  {r.get('filename', '?')}")
```

### Download all transcripts (JSON + Markdown)

```python
OUTPUT = "output"
recordings = list_recordings()
tags = {t["id"]: t["name"] for t in get_tags()}
file_ids = [r["id"] for r in recordings]
exported, skipped = 0, 0

for i in range(0, len(file_ids), 20):
    for rec in get_details(file_ids[i:i+20]):
        tag_ids = rec.get("filetag_id_list") or []
        folder = next((tags[t] for t in tag_ids if t in tags), "Unsorted")
        dt = datetime.fromtimestamp(rec["start_time"] / 1000, tz=timezone.utc)
        safe = re.sub(r'[<>:"/\\|?*]', '-', rec["filename"])
        stem = f"{dt:%Y-%m-%d}_{safe}"
        out = Path(OUTPUT) / folder
        out.mkdir(parents=True, exist_ok=True)

        if (out / f"{stem}.json").exists():
            skipped += 1
            continue

        transcript = rec.get("trans_result") or []
        summary = parse_ai_content(rec.get("ai_content"))
        dur_ms = rec.get("duration", 0)

        (out / f"{stem}.json").write_text(json.dumps({
            "id": rec["id"], "filename": rec["filename"],
            "start_time": rec["start_time"], "duration_ms": dur_ms,
            "transcript": [{"speaker": s.get("speaker", "?"), "content": s.get("content", ""),
                           "start_time": s.get("start_time", 0), "end_time": s.get("end_time", 0)}
                          for s in transcript],
            "summary": summary,
        }, indent=2, ensure_ascii=False))

        lines = [f"# {rec['filename']}", "", f"**Date:** {dt:%Y-%m-%d %H:%M UTC}",
                 f"**Duration:** {fmt_duration(dur_ms)}", "", "## Transcript", ""]
        for s in transcript:
            ts = fmt_duration(s.get("start_time", 0))
            lines += [f"**{s.get('speaker', '?')}** [{ts}]: {s.get('content', '')}", ""]
        lines += ["## Summary", "", summary, ""]
        (out / f"{stem}.md").write_text("\n".join(lines))
        print(f"  + {rec['filename']}")
        exported += 1

print(f"\nDone! {exported} exported, {skipped} skipped (already exist)")
```

### Generate missing transcripts and wait

```python
recordings = list_recordings()
missing = [r for r in recordings if not r.get("is_trans") and r.get("duration", 0) // 1000 >= 10]

if not missing:
    print("All recordings already have transcripts!")
else:
    print(f"{len(missing)} recordings without transcripts:\n")
    for r in missing:
        dur = r.get("duration", 0) // 1000
        print(f"  {dur:>5}s  {r.get('filename', '?')}")
        start_transcription(r["id"])

    print(f"\nTriggered {len(missing)} transcriptions. Polling...")
    pending = {r["id"]: r.get("filename", "?") for r in missing}
    while pending:
        time.sleep(15)
        for fid in list(pending):
            if poll_transcription(fid).get("status") == 1:
                print(f"  Done: {pending.pop(fid)}")
        if pending:
            print(f"  Waiting on {len(pending)}...")
    print("\nAll transcriptions complete!")
```

## API reference

| Endpoint | Method | Body | Returns |
|----------|--------|------|---------|
| `/file/simple/web?skip=0&limit=200&is_trash=0&sort_by=start_time&is_desc=true` | GET | - | `{data_file_list: [...]}` basic recording list |
| `/file/list?support_mul_summ=true` | POST | JSON array of file IDs (max 20) | `{data_file_list: [...]}` full details with transcripts |
| `/file/{id}` | PATCH | JSON config object | Sets transcription config |
| `/ai/transsumm/{id}` | POST | `{is_reload: 1, ...}` | Starts transcription job |
| `/ai/transsumm/{id}` | POST | `{is_reload: 0, ...}` | Poll status: `0`=pending, `-111`=transcript done/summary in progress, `1`=complete |
| `/filetag/` | GET | - | `{data_filetag_list: [...]}` tag list |
| `/auth/access-token` | POST | form: `username`, `password`, `client_id=web` | `{access_token: "..."}` |

## Gotchas

- Authorization header uses lowercase `bearer` (not `Bearer`)
- EU accounts use `https://api-euc1.plaud.ai` instead of `https://api.plaud.ai`
- Tokens expire. If you get 401 errors, the user needs to grab a fresh token from their browser.
- Triggering transcription is two steps: PATCH sets config, then POST to `/ai/transsumm` with `is_reload=1` starts the job. PATCH alone does nothing.
- `ai_content` field can be plain markdown, or JSON containing `{"markdown": "..."}`, `{"content": {"markdown": "..."}}`, or `{"summary": "..."}`. The `parse_ai_content` helper handles all variants.
- Some transcript segments may lack `speaker` or `content` keys. Always use `.get()` with defaults.
- Don't send more than 20 IDs at once to `/file/list`.
- All GET requests need a random `r=` query parameter for cache busting.
