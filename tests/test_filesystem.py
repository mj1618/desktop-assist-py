"""Tests for desktop_assist.filesystem – uses tmp_path for real file system ops."""

from __future__ import annotations

import time

from desktop_assist import filesystem

# ---------------------------------------------------------------------------
# read_text
# ---------------------------------------------------------------------------


class TestReadText:
    def test_reads_file_content(self, tmp_path):
        f = tmp_path / "hello.txt"
        f.write_text("hello world", encoding="utf-8")
        assert filesystem.read_text(str(f)) == "hello world"

    def test_returns_none_for_missing_file(self, tmp_path):
        assert filesystem.read_text(str(tmp_path / "nope.txt")) is None

    def test_respects_encoding(self, tmp_path):
        f = tmp_path / "latin.txt"
        f.write_bytes("caf\xe9".encode("latin-1"))
        assert filesystem.read_text(str(f), encoding="latin-1") == "caf\xe9"


# ---------------------------------------------------------------------------
# write_text
# ---------------------------------------------------------------------------


class TestWriteText:
    def test_writes_file(self, tmp_path):
        f = tmp_path / "out.txt"
        assert filesystem.write_text(str(f), "content") is True
        assert f.read_text() == "content"

    def test_creates_parent_dirs(self, tmp_path):
        f = tmp_path / "a" / "b" / "c" / "deep.txt"
        assert filesystem.write_text(str(f), "deep") is True
        assert f.read_text() == "deep"

    def test_overwrites_existing(self, tmp_path):
        f = tmp_path / "overwrite.txt"
        f.write_text("old")
        assert filesystem.write_text(str(f), "new") is True
        assert f.read_text() == "new"


# ---------------------------------------------------------------------------
# append_text
# ---------------------------------------------------------------------------


class TestAppendText:
    def test_creates_file_if_missing(self, tmp_path):
        f = tmp_path / "log.txt"
        assert filesystem.append_text(str(f), "line1\n") is True
        assert f.read_text() == "line1\n"

    def test_appends_to_existing(self, tmp_path):
        f = tmp_path / "log.txt"
        f.write_text("line1\n")
        assert filesystem.append_text(str(f), "line2\n") is True
        assert f.read_text() == "line1\nline2\n"

    def test_creates_parent_dirs(self, tmp_path):
        f = tmp_path / "sub" / "dir" / "log.txt"
        assert filesystem.append_text(str(f), "data") is True
        assert f.read_text() == "data"


# ---------------------------------------------------------------------------
# list_dir
# ---------------------------------------------------------------------------


class TestListDir:
    def test_lists_all_entries(self, tmp_path):
        (tmp_path / "a.txt").write_text("a")
        (tmp_path / "b.txt").write_text("bb")
        (tmp_path / "subdir").mkdir()

        entries = filesystem.list_dir(str(tmp_path))
        names = [e["name"] for e in entries]
        assert "a.txt" in names
        assert "b.txt" in names
        assert "subdir" in names

    def test_pattern_filtering(self, tmp_path):
        (tmp_path / "report.csv").write_text("data")
        (tmp_path / "report.txt").write_text("text")
        (tmp_path / "other.csv").write_text("more")

        entries = filesystem.list_dir(str(tmp_path), pattern="*.csv")
        names = [e["name"] for e in entries]
        assert "report.csv" in names
        assert "other.csv" in names
        assert "report.txt" not in names

    def test_sort_by_name(self, tmp_path):
        (tmp_path / "banana.txt").write_text("")
        (tmp_path / "apple.txt").write_text("")
        (tmp_path / "cherry.txt").write_text("")

        entries = filesystem.list_dir(str(tmp_path), sort_by="name")
        names = [e["name"] for e in entries]
        assert names == ["apple.txt", "banana.txt", "cherry.txt"]

    def test_sort_by_size(self, tmp_path):
        (tmp_path / "small.txt").write_text("a")
        (tmp_path / "medium.txt").write_text("aaa")
        (tmp_path / "large.txt").write_text("aaaaa")

        entries = filesystem.list_dir(str(tmp_path), sort_by="size")
        names = [e["name"] for e in entries]
        assert names == ["small.txt", "medium.txt", "large.txt"]

    def test_sort_by_modified(self, tmp_path):
        f1 = tmp_path / "old.txt"
        f2 = tmp_path / "new.txt"
        f1.write_text("old")
        # Ensure different mtime
        import os

        old_time = time.time() - 100
        os.utime(str(f1), (old_time, old_time))
        f2.write_text("new")

        entries = filesystem.list_dir(str(tmp_path), sort_by="modified")
        names = [e["name"] for e in entries]
        assert names == ["old.txt", "new.txt"]

    def test_reverse_sort(self, tmp_path):
        (tmp_path / "a.txt").write_text("")
        (tmp_path / "b.txt").write_text("")
        (tmp_path / "c.txt").write_text("")

        entries = filesystem.list_dir(str(tmp_path), sort_by="name", reverse=True)
        names = [e["name"] for e in entries]
        assert names == ["c.txt", "b.txt", "a.txt"]

    def test_entry_has_expected_keys(self, tmp_path):
        (tmp_path / "file.txt").write_text("hello")
        entries = filesystem.list_dir(str(tmp_path))
        entry = entries[0]
        assert "name" in entry
        assert "path" in entry
        assert "is_dir" in entry
        assert "size" in entry
        assert "modified" in entry

    def test_returns_empty_for_missing_dir(self):
        assert filesystem.list_dir("/nonexistent/path/xyz") == []


# ---------------------------------------------------------------------------
# file_info
# ---------------------------------------------------------------------------


class TestFileInfo:
    def test_returns_metadata_for_file(self, tmp_path):
        f = tmp_path / "info.txt"
        f.write_text("hello")
        info = filesystem.file_info(str(f))
        assert info is not None
        assert info["name"] == "info.txt"
        assert info["is_dir"] is False
        assert info["size"] == 5
        assert "modified" in info
        assert "created" in info

    def test_returns_metadata_for_directory(self, tmp_path):
        d = tmp_path / "mydir"
        d.mkdir()
        info = filesystem.file_info(str(d))
        assert info is not None
        assert info["name"] == "mydir"
        assert info["is_dir"] is True

    def test_returns_none_for_missing_path(self):
        assert filesystem.file_info("/nonexistent/abc123") is None


# ---------------------------------------------------------------------------
# wait_for_file
# ---------------------------------------------------------------------------


class TestWaitForFile:
    def test_returns_true_when_file_already_exists(self, tmp_path):
        f = tmp_path / "ready.txt"
        f.write_text("done")
        result = filesystem.wait_for_file(
            str(f), timeout=5.0, poll_interval=0.05, stable_seconds=0.1
        )
        assert result is True

    def test_returns_false_on_timeout(self, tmp_path):
        result = filesystem.wait_for_file(
            str(tmp_path / "never.txt"),
            timeout=0.2,
            poll_interval=0.05,
            stable_seconds=0.05,
        )
        assert result is False

    def test_waits_for_file_to_stabilize(self, tmp_path):
        """Write to a file during polling and verify it waits for stability."""
        import threading

        f = tmp_path / "download.bin"

        def simulate_download():
            # Write in chunks to simulate an in-progress download
            for i in range(3):
                with open(str(f), "ab") as fh:
                    fh.write(b"x" * 100)
                time.sleep(0.05)

        t = threading.Thread(target=simulate_download)
        t.start()

        result = filesystem.wait_for_file(
            str(f), timeout=5.0, poll_interval=0.05, stable_seconds=0.2
        )
        t.join()
        assert result is True
        # File should have all 300 bytes
        assert f.stat().st_size == 300


# ---------------------------------------------------------------------------
# find_files
# ---------------------------------------------------------------------------


class TestFindFiles:
    def test_finds_files_recursively(self, tmp_path):
        (tmp_path / "a.csv").write_text("data")
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "b.csv").write_text("more")
        (sub / "c.txt").write_text("text")

        results = filesystem.find_files(str(tmp_path), "*.csv", recursive=True)
        basenames = [r.split("/")[-1] for r in results]
        assert "a.csv" in basenames
        assert "b.csv" in basenames
        assert "c.txt" not in basenames

    def test_non_recursive_stays_in_root(self, tmp_path):
        (tmp_path / "top.csv").write_text("top")
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "nested.csv").write_text("nested")

        results = filesystem.find_files(str(tmp_path), "*.csv", recursive=False)
        basenames = [r.split("/")[-1] for r in results]
        assert "top.csv" in basenames
        assert "nested.csv" not in basenames

    def test_max_results_cap(self, tmp_path):
        for i in range(10):
            (tmp_path / f"file_{i}.txt").write_text(f"content {i}")

        results = filesystem.find_files(str(tmp_path), "*.txt", max_results=3)
        assert len(results) == 3

    def test_sorted_by_mtime_newest_first(self, tmp_path):
        import os

        f1 = tmp_path / "old.txt"
        f2 = tmp_path / "new.txt"
        f1.write_text("old")
        old_time = time.time() - 100
        os.utime(str(f1), (old_time, old_time))
        f2.write_text("new")

        results = filesystem.find_files(str(tmp_path), "*.txt")
        assert results[0].endswith("new.txt")
        assert results[1].endswith("old.txt")

    def test_returns_empty_for_missing_dir(self):
        assert filesystem.find_files("/nonexistent/xyz", "*.txt") == []

    def test_excludes_directories(self, tmp_path):
        (tmp_path / "file.log").write_text("data")
        (tmp_path / "dir.log").mkdir()

        results = filesystem.find_files(str(tmp_path), "*.log", recursive=False)
        assert len(results) == 1
        assert results[0].endswith("file.log")


# ---------------------------------------------------------------------------
# ensure_dir
# ---------------------------------------------------------------------------


class TestEnsureDir:
    def test_creates_directory(self, tmp_path):
        d = tmp_path / "newdir"
        assert filesystem.ensure_dir(str(d)) is True
        assert d.is_dir()

    def test_creates_nested_directories(self, tmp_path):
        d = tmp_path / "a" / "b" / "c"
        assert filesystem.ensure_dir(str(d)) is True
        assert d.is_dir()

    def test_succeeds_if_already_exists(self, tmp_path):
        d = tmp_path / "existing"
        d.mkdir()
        assert filesystem.ensure_dir(str(d)) is True
        assert d.is_dir()
