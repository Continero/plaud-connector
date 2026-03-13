"""Tests for the CLI module."""

from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from plaud_downloader.cli import cli


@patch("plaud_downloader.cli.PlaudClient")
def test_list_command(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_client.list_recordings.return_value = [
        {
            "id": "rec1",
            "filename": "My Meeting",
            "start_time": 1699963200000,  # 2023-11-14 12:00 UTC
            "duration": 300000,
        }
    ]

    runner = CliRunner(env={"PLAUD_EMAIL": "a@b.com", "PLAUD_PASSWORD": "pass"})
    result = runner.invoke(cli, ["list"])

    assert result.exit_code == 0
    assert "1 recordings" in result.output
    assert "My Meeting" in result.output
    assert "300s" in result.output


@patch("plaud_downloader.cli.PlaudClient")
def test_list_command_no_credentials(mock_client_cls):
    runner = CliRunner(env={"PLAUD_EMAIL": "", "PLAUD_PASSWORD": ""})
    result = runner.invoke(cli, ["list"])

    assert result.exit_code != 0
    assert "PLAUD_EMAIL" in result.output


@patch("plaud_downloader.cli.Exporter")
@patch("plaud_downloader.cli.PlaudClient")
def test_download_command(mock_client_cls, mock_exporter_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_client.list_recordings.return_value = [
        {"id": "rec1", "filename": "My Meeting", "start_time": 1699963200000, "duration": 300000}
    ]
    mock_client.get_tags.return_value = [{"id": "tag1", "name": "Work"}]
    mock_client.get_recording_details.return_value = [
        {
            "id": "rec1",
            "filename": "My Meeting",
            "start_time": 1699963200000,
            "duration": 300000,
            "trans_result": [],
            "ai_content": "",
        }
    ]

    mock_exporter = MagicMock()
    mock_exporter_cls.return_value = mock_exporter
    mock_exporter.export_recording.return_value = "exported"

    runner = CliRunner(env={"PLAUD_EMAIL": "a@b.com", "PLAUD_PASSWORD": "pass"})
    result = runner.invoke(cli, ["download", "-o", "test_output"])

    assert result.exit_code == 0
    assert "Exported: My Meeting" in result.output
    assert "Exported 1, skipped 0" in result.output
    mock_exporter.export_recording.assert_called_once()


@patch("plaud_downloader.cli.Exporter")
@patch("plaud_downloader.cli.PlaudClient")
def test_download_command_skips_existing(mock_client_cls, mock_exporter_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_client.list_recordings.return_value = [
        {"id": "rec1", "filename": "Old Meeting", "start_time": 1699963200000, "duration": 60000}
    ]
    mock_client.get_tags.return_value = []
    mock_client.get_recording_details.return_value = [
        {
            "id": "rec1",
            "filename": "Old Meeting",
            "start_time": 1699963200000,
            "duration": 60000,
            "trans_result": [],
            "ai_content": "",
        }
    ]

    mock_exporter = MagicMock()
    mock_exporter_cls.return_value = mock_exporter
    mock_exporter.export_recording.return_value = "skipped"

    runner = CliRunner(env={"PLAUD_EMAIL": "a@b.com", "PLAUD_PASSWORD": "pass"})
    result = runner.invoke(cli, ["download"])

    assert result.exit_code == 0
    assert "Exported 0, skipped 1" in result.output


@patch("plaud_downloader.cli.PlaudClient")
def test_download_batches(mock_client_cls):
    """Verify that file IDs are fetched in batches of 20."""
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client

    # 25 recordings to trigger two batches (20 + 5)
    recordings = [
        {"id": f"rec{i}", "filename": f"Meeting {i}", "start_time": 1699963200000, "duration": 1000}
        for i in range(25)
    ]
    mock_client.list_recordings.return_value = recordings
    mock_client.get_tags.return_value = []
    mock_client.get_recording_details.return_value = []

    runner = CliRunner(env={"PLAUD_EMAIL": "a@b.com", "PLAUD_PASSWORD": "pass"})
    result = runner.invoke(cli, ["download"])

    assert result.exit_code == 0
    assert mock_client.get_recording_details.call_count == 2
    first_call_ids = mock_client.get_recording_details.call_args_list[0][0][0]
    second_call_ids = mock_client.get_recording_details.call_args_list[1][0][0]
    assert len(first_call_ids) == 20
    assert len(second_call_ids) == 5
