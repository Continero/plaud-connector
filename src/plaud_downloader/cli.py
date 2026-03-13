"""CLI for plaud-downloader."""

from __future__ import annotations

import os
import time
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
    token = os.environ.get("PLAUD_TOKEN")
    email = os.environ.get("PLAUD_EMAIL")
    password = os.environ.get("PLAUD_PASSWORD")
    base_url = os.environ.get("PLAUD_API_BASE", "https://api.plaud.ai")
    if token:
        return PlaudClient(token=token, base_url=base_url)
    if email and password:
        return PlaudClient(email=email, password=password, base_url=base_url)
    raise click.ClickException(
        "Set PLAUD_TOKEN or PLAUD_EMAIL+PLAUD_PASSWORD in .env"
    )


@cli.command("list")
def list_cmd():
    """List all recordings."""
    client = _get_client()
    recordings = client.list_recordings()
    click.echo(f"Found {len(recordings)} recordings:\n")
    for rec in recordings:
        start_ms = rec.get("start_time", 0)
        dt = datetime.fromtimestamp(start_ms / 1000, tz=timezone.utc)
        date_str = dt.strftime("%Y-%m-%d %H:%M")
        duration_s = rec.get("duration", 0) // 1000
        name = rec.get("filename", "Unknown")
        click.echo(f"  {date_str}   {duration_s}s  {name}")


@cli.command()
@click.option("--output", "-o", default="output", help="Output directory")
def download(output: str):
    """Download all recordings."""
    client = _get_client()
    recordings = client.list_recordings()
    tags = client.get_tags()
    exporter = Exporter(output_dir=Path(output), tags=tags)

    file_ids = [rec["id"] for rec in recordings]

    exported = 0
    skipped = 0

    # Fetch details in batches of 20
    for i in range(0, len(file_ids), 20):
        batch_ids = file_ids[i : i + 20]
        details = client.get_recording_details(batch_ids)
        for rec in details:
            result = exporter.export_recording(rec)
            name = rec.get("filename", "Unknown")
            if result == "exported":
                click.echo(f"Exported: {name}")
                exported += 1
            else:
                skipped += 1

    click.echo(f"\nDone! Exported {exported}, skipped {skipped}")


@cli.command()
@click.option("--min-duration", default=10, help="Skip recordings shorter than N seconds")
@click.option("--dry-run", is_flag=True, help="Show what would be generated without triggering")
@click.option("--wait/--no-wait", default=False, help="Wait and poll for completion")
def generate(min_duration: int, dry_run: bool, wait: bool):
    """Trigger transcription for recordings that don't have one yet."""
    client = _get_client()

    click.echo("Fetching recordings...")
    recordings = client.list_recordings()
    missing = [
        r for r in recordings
        if not r.get("is_trans")
        and r.get("duration", 0) // 1000 >= min_duration
    ]

    if not missing:
        click.echo("All recordings already have transcripts!")
        return

    click.echo(f"Found {len(missing)} recordings without transcripts (>= {min_duration}s):\n")
    for r in missing:
        dur = r.get("duration", 0) // 1000
        click.echo(f"  {dur:>5}s  {r.get('filename', 'Unknown')}")

    if dry_run:
        click.echo(f"\nDry run — would trigger {len(missing)} transcriptions.")
        return

    click.echo(f"\nTriggering transcription for {len(missing)} recordings...")
    triggered = []
    for r in missing:
        name = r.get("filename", "Unknown")
        try:
            client.start_transcription(r["id"])
            click.echo(f"  Started: {name}")
            triggered.append(r)
        except Exception as e:
            click.echo(f"  Failed: {name} — {e}")

    click.echo(f"\nTriggered {len(triggered)} transcriptions.")

    if not wait or not triggered:
        if triggered:
            click.echo("Run 'plaud download' later to fetch the results.")
        return

    click.echo("\nPolling for completion (Ctrl+C to stop)...")
    pending = {r["id"]: r.get("filename", "Unknown") for r in triggered}
    while pending:
        time.sleep(15)
        done_ids = []
        for fid, name in pending.items():
            try:
                result = client.poll_transcription(fid)
                if result.get("status") == 1:
                    click.echo(f"  Done: {name}")
                    done_ids.append(fid)
            except Exception:
                pass
        for fid in done_ids:
            del pending[fid]
        if pending:
            click.echo(f"  Still waiting on {len(pending)}...")

    click.echo("All transcriptions complete! Run 'plaud download' to fetch results.")
