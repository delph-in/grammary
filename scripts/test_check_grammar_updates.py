"""Unit tests for scripts/check_grammar_updates.py."""

from __future__ import annotations

from unittest import mock

from scripts import check_grammar_updates as cgu


def test_resolve_revision_dispatches_git() -> None:
    # Arrange
    with mock.patch.object(cgu, "resolve_git", return_value="abc123") as m:
        # Act
        kind, rev = cgu.resolve_revision("git clone https://example.com/g.git")
    # Assert
    assert kind == "git"
    assert rev == "abc123"
    m.assert_called_once_with("https://example.com/g.git")


def test_resolve_revision_dispatches_svn() -> None:
    with mock.patch.object(cgu, "resolve_svn", return_value="42") as m:
        kind, rev = cgu.resolve_revision("svn co http://svn.example.com/trunk/g")
    assert kind == "svn"
    assert rev == "42"
    m.assert_called_once_with("http://svn.example.com/trunk/g")


def test_resolve_revision_dispatches_http_wget() -> None:
    with mock.patch.object(cgu, "resolve_http", return_value="ETag:x") as m:
        kind, rev = cgu.resolve_revision("wget https://example.com/g.tgz")
    assert kind == "http"
    assert rev == "ETag:x"
    m.assert_called_once_with("https://example.com/g.tgz")


def test_resolve_revision_unknown_format() -> None:
    kind, rev = cgu.resolve_revision("rsync://example.com/g")
    assert kind == "unknown"
    assert rev is None


def test_render_report_no_drift() -> None:
    # Arrange
    current = {"erg": "sha1", "jacy": "sha2"}
    baseline = {"erg": "sha1", "jacy": "sha2"}
    # Act
    report, drift = cgu.render_report(current, baseline)
    # Assert
    assert drift is False
    assert "up to date" in report


def test_render_report_changed_and_new() -> None:
    # Arrange: norsyg moved, yue is brand new, erg unchanged
    current = {"erg": "sha1", "norsyg": "new", "yue": "fresh"}
    baseline = {"erg": "sha1", "norsyg": "old"}
    # Act
    report, drift = cgu.render_report(current, baseline)
    # Assert
    assert drift is True
    assert "| norsyg | `old` | `new` |" in report
    assert "yue" in report  # listed as a new grammar
    assert "erg" not in report  # unchanged, not reported


def test_render_report_ignores_disappeared_baseline_entries() -> None:
    # A grammar present only in the baseline (removed from the toml) is not drift.
    current = {"erg": "sha1"}
    baseline = {"erg": "sha1", "retired": "old"}
    report, drift = cgu.render_report(current, baseline)
    assert drift is False
