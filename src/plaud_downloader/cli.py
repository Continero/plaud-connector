"""CLI for plaud-downloader."""

from __future__ import annotations

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
