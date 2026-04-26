import pytest
from pathlib import Path
from unittest.mock import patch


def test_load_user_profile_returns_empty_when_file_missing(tmp_path):
    from backend.profile_extractor import load_user_profile
    assert load_user_profile(tmp_path / "missing.md") == ""


def test_load_user_profile_returns_empty_when_section_absent(tmp_path):
    from backend.profile_extractor import load_user_profile
    f = tmp_path / "notes.md"
    f.write_text("# Notes\n\nSome content\n")
    assert load_user_profile(f) == ""


def test_load_user_profile_returns_profile_content(tmp_path):
    from backend.profile_extractor import load_user_profile
    f = tmp_path / "notes.md"
    f.write_text(
        "# Notes\n\n---\n\n## Current Profile\n_Last updated: 2026-04-25_\n\n"
        "- Saves regularly\n- Dining out often\n\n---\n\n## Observations Log\n"
    )
    result = load_user_profile(f)
    assert "Saves regularly" in result
    assert "Dining out often" in result


def test_write_profile_and_log_creates_sections_when_absent(tmp_path):
    from backend.profile_extractor import _write_profile_and_log
    f = tmp_path / "notes.md"
    f.write_text("# Notes\n\nExisting content.\n")
    _write_profile_and_log("- New pattern", "First observation", f)
    content = f.read_text()
    assert "## Current Profile" in content
    assert "- New pattern" in content
    assert "## Observations Log" in content
    assert "First observation" in content


def test_write_profile_and_log_updates_existing_profile(tmp_path):
    from backend.profile_extractor import _write_profile_and_log
    f = tmp_path / "notes.md"
    f.write_text(
        "# Notes\n\n---\n\n## Current Profile\n_Last updated: 2026-04-24_\n\n"
        "- Old pattern\n\n---\n\n## Observations Log\n\n- **2026-04-24**: old entry\n"
    )
    _write_profile_and_log("- Updated pattern", "New entry today", f)
    content = f.read_text()
    assert "Updated pattern" in content
    assert "Old pattern" not in content
    assert "New entry today" in content
    assert "old entry" in content  # log is append-only


def test_write_profile_and_log_does_not_duplicate_heading(tmp_path):
    from backend.profile_extractor import _write_profile_and_log
    f = tmp_path / "notes.md"
    f.write_text(
        "# Notes\n\n---\n\n## Current Profile\n_Last updated: 2026-04-24_\n\n"
        "- Old pattern\n\n---\n\n## Observations Log\n\n- **2026-04-24**: old entry\n"
    )
    _write_profile_and_log("- Updated pattern", "New entry today", f)
    content = f.read_text()
    assert content.count("## Current Profile") == 1


def test_load_user_profile_with_second_heading_boundary(tmp_path):
    from backend.profile_extractor import load_user_profile
    f = tmp_path / "notes.md"
    f.write_text(
        "# Notes\n\n## Current Profile\n_Last updated: 2026-04-25_\n\n- Pattern A\n\n## Other Section\n\nOther content\n"
    )
    result = load_user_profile(f)
    assert "Pattern A" in result
    assert "Other Section" not in result
    assert "Other content" not in result


def test_write_profile_and_log_on_empty_file(tmp_path):
    from backend.profile_extractor import _write_profile_and_log
    f = tmp_path / "notes.md"
    f.write_text("")
    _write_profile_and_log("- First pattern", "First log entry", f)
    content = f.read_text()
    assert "## Current Profile" in content
    assert "- First pattern" in content
    assert "## Observations Log" in content
    assert "First log entry" in content
