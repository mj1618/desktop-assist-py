"""Tests for desktop_assist.browser – all AppleScript calls are mocked."""

from __future__ import annotations

import subprocess

import pytest

from desktop_assist import browser

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _force_macos(monkeypatch):
    """Make all tests behave as if running on macOS."""
    monkeypatch.setattr(browser, "_is_macos", lambda: True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_completed_process(stdout: str = "", returncode: int = 0):
    """Create a fake subprocess.CompletedProcess."""
    return subprocess.CompletedProcess(
        args=["osascript", "-e", "..."],
        returncode=returncode,
        stdout=stdout,
        stderr="",
    )


# Sample AppleScript outputs
TABS_OUTPUT = (
    "1|||1|||Google|||https://www.google.com\n"
    "1|||2|||GitHub|||https://github.com\n"
    "2|||1|||Apple|||https://www.apple.com\n"
)

ACTIVE_TAB_OUTPUT = "Google|||https://www.google.com"

LINKS_JSON = '[{"text":"Home","href":"https://example.com"},{"text":"About","href":"https://example.com/about"}]'

FORMS_JSON = '[{"index":0,"action":"https://example.com/search","method":"get","fields":[{"tag":"input","type":"text","name":"q","id":"search","placeholder":"Search...","value":""}]}]'


# ---------------------------------------------------------------------------
# list_tabs
# ---------------------------------------------------------------------------


class TestListTabs:
    def test_returns_tab_list(self, monkeypatch):
        monkeypatch.setattr(
            subprocess, "run",
            lambda *a, **kw: _make_completed_process(stdout=TABS_OUTPUT),
        )
        tabs = browser.list_tabs()
        assert len(tabs) == 3
        assert tabs[0] == {"window": 1, "tab": 1, "title": "Google", "url": "https://www.google.com"}
        assert tabs[1] == {"window": 1, "tab": 2, "title": "GitHub", "url": "https://github.com"}
        assert tabs[2] == {"window": 2, "tab": 1, "title": "Apple", "url": "https://www.apple.com"}

    def test_returns_empty_on_failure(self, monkeypatch):
        monkeypatch.setattr(
            subprocess, "run",
            lambda *a, **kw: _make_completed_process(returncode=1),
        )
        assert browser.list_tabs() == []

    def test_returns_empty_on_non_macos(self, monkeypatch):
        monkeypatch.setattr(browser, "_is_macos", lambda: False)
        assert browser.list_tabs() == []

    def test_returns_empty_on_empty_output(self, monkeypatch):
        monkeypatch.setattr(
            subprocess, "run",
            lambda *a, **kw: _make_completed_process(stdout=""),
        )
        assert browser.list_tabs() == []

    def test_uses_correct_browser_name(self, monkeypatch):
        captured: list[str] = []

        def fake_run(args, **kwargs):
            captured.append(args[2])
            return _make_completed_process(stdout="")

        monkeypatch.setattr(subprocess, "run", fake_run)
        browser.list_tabs(browser="Google Chrome")
        assert 'tell application "Google Chrome"' in captured[0]


# ---------------------------------------------------------------------------
# get_active_tab
# ---------------------------------------------------------------------------


class TestGetActiveTab:
    def test_returns_tab_info(self, monkeypatch):
        monkeypatch.setattr(
            subprocess, "run",
            lambda *a, **kw: _make_completed_process(stdout=ACTIVE_TAB_OUTPUT),
        )
        result = browser.get_active_tab()
        assert result is not None
        assert result["title"] == "Google"
        assert result["url"] == "https://www.google.com"

    def test_returns_none_on_failure(self, monkeypatch):
        monkeypatch.setattr(
            subprocess, "run",
            lambda *a, **kw: _make_completed_process(returncode=1),
        )
        assert browser.get_active_tab() is None

    def test_returns_none_on_non_macos(self, monkeypatch):
        monkeypatch.setattr(browser, "_is_macos", lambda: False)
        assert browser.get_active_tab() is None

    def test_returns_none_on_empty(self, monkeypatch):
        monkeypatch.setattr(
            subprocess, "run",
            lambda *a, **kw: _make_completed_process(stdout=""),
        )
        assert browser.get_active_tab() is None


# ---------------------------------------------------------------------------
# open_tab
# ---------------------------------------------------------------------------


class TestOpenTab:
    def test_returns_true_on_success(self, monkeypatch):
        monkeypatch.setattr(
            subprocess, "run",
            lambda *a, **kw: _make_completed_process(),
        )
        assert browser.open_tab("https://example.com") is True

    def test_returns_false_on_failure(self, monkeypatch):
        monkeypatch.setattr(
            subprocess, "run",
            lambda *a, **kw: _make_completed_process(returncode=1),
        )
        assert browser.open_tab("https://example.com") is False

    def test_returns_false_on_non_macos(self, monkeypatch):
        monkeypatch.setattr(browser, "_is_macos", lambda: False)
        assert browser.open_tab("https://example.com") is False

    def test_script_contains_url(self, monkeypatch):
        captured: list[str] = []

        def fake_run(args, **kwargs):
            captured.append(args[2])
            return _make_completed_process()

        monkeypatch.setattr(subprocess, "run", fake_run)
        browser.open_tab("https://example.com/search?q=test")
        assert "https://example.com/search?q=test" in captured[0]

    def test_escapes_url(self, monkeypatch):
        captured: list[str] = []

        def fake_run(args, **kwargs):
            captured.append(args[2])
            return _make_completed_process()

        monkeypatch.setattr(subprocess, "run", fake_run)
        browser.open_tab('https://example.com/page"with"quotes')
        assert 'https://example.com/page\\"with\\"quotes' in captured[0]


# ---------------------------------------------------------------------------
# close_tab
# ---------------------------------------------------------------------------


class TestCloseTab:
    def test_returns_true_on_success(self, monkeypatch):
        monkeypatch.setattr(
            subprocess, "run",
            lambda *a, **kw: _make_completed_process(stdout="ok"),
        )
        assert browser.close_tab(1, 1) is True

    def test_returns_false_on_error(self, monkeypatch):
        monkeypatch.setattr(
            subprocess, "run",
            lambda *a, **kw: _make_completed_process(stdout="err:not found"),
        )
        assert browser.close_tab(1, 1) is False

    def test_returns_false_on_non_macos(self, monkeypatch):
        monkeypatch.setattr(browser, "_is_macos", lambda: False)
        assert browser.close_tab(1, 1) is False

    def test_script_uses_correct_indices(self, monkeypatch):
        captured: list[str] = []

        def fake_run(args, **kwargs):
            captured.append(args[2])
            return _make_completed_process(stdout="ok")

        monkeypatch.setattr(subprocess, "run", fake_run)
        browser.close_tab(3, 2)
        assert "close tab 3 of window 2" in captured[0]


# ---------------------------------------------------------------------------
# switch_tab
# ---------------------------------------------------------------------------


class TestSwitchTab:
    def test_returns_true_on_success(self, monkeypatch):
        monkeypatch.setattr(
            subprocess, "run",
            lambda *a, **kw: _make_completed_process(stdout="ok"),
        )
        assert browser.switch_tab(2) is True

    def test_returns_false_on_error(self, monkeypatch):
        monkeypatch.setattr(
            subprocess, "run",
            lambda *a, **kw: _make_completed_process(stdout="err:index out of range"),
        )
        assert browser.switch_tab(99) is False

    def test_returns_false_on_non_macos(self, monkeypatch):
        monkeypatch.setattr(browser, "_is_macos", lambda: False)
        assert browser.switch_tab(1) is False

    def test_script_uses_correct_indices(self, monkeypatch):
        captured: list[str] = []

        def fake_run(args, **kwargs):
            captured.append(args[2])
            return _make_completed_process(stdout="ok")

        monkeypatch.setattr(subprocess, "run", fake_run)
        browser.switch_tab(3, 2)
        assert "set current tab of window 2 to tab 3 of window 2" in captured[0]


# ---------------------------------------------------------------------------
# navigate
# ---------------------------------------------------------------------------


class TestNavigate:
    def test_returns_true_on_success(self, monkeypatch):
        monkeypatch.setattr(
            subprocess, "run",
            lambda *a, **kw: _make_completed_process(stdout="ok"),
        )
        assert browser.navigate("https://example.com") is True

    def test_returns_false_on_error(self, monkeypatch):
        monkeypatch.setattr(
            subprocess, "run",
            lambda *a, **kw: _make_completed_process(stdout="err:no window"),
        )
        assert browser.navigate("https://example.com") is False

    def test_returns_false_on_non_macos(self, monkeypatch):
        monkeypatch.setattr(browser, "_is_macos", lambda: False)
        assert browser.navigate("https://example.com") is False

    def test_uses_current_tab_by_default(self, monkeypatch):
        captured: list[str] = []

        def fake_run(args, **kwargs):
            captured.append(args[2])
            return _make_completed_process(stdout="ok")

        monkeypatch.setattr(subprocess, "run", fake_run)
        browser.navigate("https://example.com")
        assert "current tab of window 1" in captured[0]

    def test_uses_specific_tab_when_given(self, monkeypatch):
        captured: list[str] = []

        def fake_run(args, **kwargs):
            captured.append(args[2])
            return _make_completed_process(stdout="ok")

        monkeypatch.setattr(subprocess, "run", fake_run)
        browser.navigate("https://example.com", window_index=2, tab_index=3)
        assert "tab 3 of window 2" in captured[0]


# ---------------------------------------------------------------------------
# go_back / go_forward / reload_page
# ---------------------------------------------------------------------------


class TestNavActions:
    def test_go_back(self, monkeypatch):
        monkeypatch.setattr(browser, "run_javascript", lambda s, **kw: "")
        assert browser.go_back() is True

    def test_go_back_returns_false_on_error(self, monkeypatch):
        monkeypatch.setattr(browser, "run_javascript", lambda s, **kw: None)
        assert browser.go_back() is False

    def test_go_forward(self, monkeypatch):
        monkeypatch.setattr(browser, "run_javascript", lambda s, **kw: "")
        assert browser.go_forward() is True

    def test_reload_page(self, monkeypatch):
        monkeypatch.setattr(browser, "run_javascript", lambda s, **kw: "")
        assert browser.reload_page() is True

    def test_go_back_non_macos(self, monkeypatch):
        monkeypatch.setattr(browser, "_is_macos", lambda: False)
        assert browser.go_back() is False

    def test_go_forward_non_macos(self, monkeypatch):
        monkeypatch.setattr(browser, "_is_macos", lambda: False)
        assert browser.go_forward() is False

    def test_reload_non_macos(self, monkeypatch):
        monkeypatch.setattr(browser, "_is_macos", lambda: False)
        assert browser.reload_page() is False


# ---------------------------------------------------------------------------
# get_page_text
# ---------------------------------------------------------------------------


class TestGetPageText:
    def test_returns_text(self, monkeypatch):
        monkeypatch.setattr(browser, "run_javascript", lambda s, **kw: "Hello World")
        assert browser.get_page_text() == "Hello World"

    def test_truncates_long_text(self, monkeypatch):
        long_text = "x" * 60_000
        monkeypatch.setattr(browser, "run_javascript", lambda s, **kw: long_text)
        result = browser.get_page_text()
        assert len(result) <= browser._MAX_PAGE_TEXT + 20
        assert result.endswith("... [truncated]")

    def test_returns_empty_on_error(self, monkeypatch):
        monkeypatch.setattr(browser, "run_javascript", lambda s, **kw: None)
        assert browser.get_page_text() == ""

    def test_returns_empty_on_non_macos(self, monkeypatch):
        monkeypatch.setattr(browser, "_is_macos", lambda: False)
        assert browser.get_page_text() == ""


# ---------------------------------------------------------------------------
# get_page_html
# ---------------------------------------------------------------------------


class TestGetPageHtml:
    def test_returns_html(self, monkeypatch):
        html = "<html><body>Hi</body></html>"
        monkeypatch.setattr(browser, "run_javascript", lambda s, **kw: html)
        assert browser.get_page_html() == "<html><body>Hi</body></html>"

    def test_returns_empty_on_error(self, monkeypatch):
        monkeypatch.setattr(browser, "run_javascript", lambda s, **kw: None)
        assert browser.get_page_html() == ""

    def test_returns_empty_on_non_macos(self, monkeypatch):
        monkeypatch.setattr(browser, "_is_macos", lambda: False)
        assert browser.get_page_html() == ""


# ---------------------------------------------------------------------------
# get_page_url / get_page_title
# ---------------------------------------------------------------------------


class TestGetPageUrl:
    def test_returns_url(self, monkeypatch):
        monkeypatch.setattr(
            subprocess, "run",
            lambda *a, **kw: _make_completed_process(stdout="https://example.com"),
        )
        assert browser.get_page_url() == "https://example.com"

    def test_returns_empty_on_failure(self, monkeypatch):
        monkeypatch.setattr(
            subprocess, "run",
            lambda *a, **kw: _make_completed_process(returncode=1),
        )
        assert browser.get_page_url() == ""

    def test_returns_empty_on_non_macos(self, monkeypatch):
        monkeypatch.setattr(browser, "_is_macos", lambda: False)
        assert browser.get_page_url() == ""


class TestGetPageTitle:
    def test_returns_title(self, monkeypatch):
        monkeypatch.setattr(
            subprocess, "run",
            lambda *a, **kw: _make_completed_process(stdout="Example Domain"),
        )
        assert browser.get_page_title() == "Example Domain"

    def test_returns_empty_on_failure(self, monkeypatch):
        monkeypatch.setattr(
            subprocess, "run",
            lambda *a, **kw: _make_completed_process(returncode=1),
        )
        assert browser.get_page_title() == ""

    def test_returns_empty_on_non_macos(self, monkeypatch):
        monkeypatch.setattr(browser, "_is_macos", lambda: False)
        assert browser.get_page_title() == ""


# ---------------------------------------------------------------------------
# run_javascript
# ---------------------------------------------------------------------------


class TestRunJavascript:
    def test_returns_result(self, monkeypatch):
        monkeypatch.setattr(
            subprocess, "run",
            lambda *a, **kw: _make_completed_process(stdout="My Page Title"),
        )
        assert browser.run_javascript("document.title") == "My Page Title"

    def test_returns_none_on_failure(self, monkeypatch):
        monkeypatch.setattr(
            subprocess, "run",
            lambda *a, **kw: _make_completed_process(returncode=1),
        )
        assert browser.run_javascript("document.title") is None

    def test_returns_none_on_js_error(self, monkeypatch):
        monkeypatch.setattr(
            subprocess, "run",
            lambda *a, **kw: _make_completed_process(
                stdout="__JS_ERROR__:ReferenceError: foo is not defined",
            ),
        )
        assert browser.run_javascript("foo.bar") is None

    def test_returns_none_on_non_macos(self, monkeypatch):
        monkeypatch.setattr(browser, "_is_macos", lambda: False)
        assert browser.run_javascript("document.title") is None

    def test_script_contains_do_javascript(self, monkeypatch):
        captured: list[str] = []

        def fake_run(args, **kwargs):
            captured.append(args[2])
            return _make_completed_process(stdout="result")

        monkeypatch.setattr(subprocess, "run", fake_run)
        browser.run_javascript("document.title")
        assert "do JavaScript" in captured[0]
        assert "document.title" in captured[0]
        assert "current tab of front window" in captured[0]

    def test_returns_none_on_timeout(self, monkeypatch):
        def raise_timeout(*a, **kw):
            raise subprocess.TimeoutExpired(cmd="osascript", timeout=10)

        monkeypatch.setattr(subprocess, "run", raise_timeout)
        assert browser.run_javascript("while(true){}") is None

    def test_escapes_javascript(self, monkeypatch):
        captured: list[str] = []

        def fake_run(args, **kwargs):
            captured.append(args[2])
            return _make_completed_process(stdout="result")

        monkeypatch.setattr(subprocess, "run", fake_run)
        browser.run_javascript('alert("hello")')
        # The double-quotes in the JS should be escaped for AppleScript
        assert '\\"hello\\"' in captured[0]


# ---------------------------------------------------------------------------
# get_links
# ---------------------------------------------------------------------------


class TestGetLinks:
    def test_returns_links(self, monkeypatch):
        monkeypatch.setattr(browser, "run_javascript", lambda s, **kw: LINKS_JSON)
        links = browser.get_links()
        assert len(links) == 2
        assert links[0]["text"] == "Home"
        assert links[0]["href"] == "https://example.com"
        assert links[1]["text"] == "About"

    def test_returns_empty_on_error(self, monkeypatch):
        monkeypatch.setattr(browser, "run_javascript", lambda s, **kw: None)
        assert browser.get_links() == []

    def test_returns_empty_on_bad_json(self, monkeypatch):
        monkeypatch.setattr(browser, "run_javascript", lambda s, **kw: "not json")
        assert browser.get_links() == []

    def test_returns_empty_on_non_macos(self, monkeypatch):
        monkeypatch.setattr(browser, "_is_macos", lambda: False)
        assert browser.get_links() == []


# ---------------------------------------------------------------------------
# get_forms
# ---------------------------------------------------------------------------


class TestGetForms:
    def test_returns_forms(self, monkeypatch):
        monkeypatch.setattr(browser, "run_javascript", lambda s, **kw: FORMS_JSON)
        forms = browser.get_forms()
        assert len(forms) == 1
        assert forms[0]["action"] == "https://example.com/search"
        assert forms[0]["fields"][0]["name"] == "q"

    def test_returns_empty_on_error(self, monkeypatch):
        monkeypatch.setattr(browser, "run_javascript", lambda s, **kw: None)
        assert browser.get_forms() == []

    def test_returns_empty_on_bad_json(self, monkeypatch):
        monkeypatch.setattr(browser, "run_javascript", lambda s, **kw: "not json")
        assert browser.get_forms() == []

    def test_returns_empty_on_non_macos(self, monkeypatch):
        monkeypatch.setattr(browser, "_is_macos", lambda: False)
        assert browser.get_forms() == []


# ---------------------------------------------------------------------------
# click_link
# ---------------------------------------------------------------------------


class TestClickLink:
    def test_returns_true_on_match(self, monkeypatch):
        monkeypatch.setattr(browser, "run_javascript", lambda s, **kw: "clicked")
        assert browser.click_link("About") is True

    def test_returns_false_on_no_match(self, monkeypatch):
        monkeypatch.setattr(browser, "run_javascript", lambda s, **kw: "not_found")
        assert browser.click_link("nonexistent") is False

    def test_returns_false_on_error(self, monkeypatch):
        monkeypatch.setattr(browser, "run_javascript", lambda s, **kw: None)
        assert browser.click_link("About") is False

    def test_returns_false_on_non_macos(self, monkeypatch):
        monkeypatch.setattr(browser, "_is_macos", lambda: False)
        assert browser.click_link("About") is False


# ---------------------------------------------------------------------------
# fill_field
# ---------------------------------------------------------------------------


class TestFillField:
    def test_returns_true_on_success(self, monkeypatch):
        monkeypatch.setattr(browser, "run_javascript", lambda s, **kw: "ok")
        assert browser.fill_field("input[name='q']", "flights to Tokyo") is True

    def test_returns_false_on_not_found(self, monkeypatch):
        monkeypatch.setattr(browser, "run_javascript", lambda s, **kw: "not_found")
        assert browser.fill_field("#nope", "value") is False

    def test_returns_false_on_error(self, monkeypatch):
        monkeypatch.setattr(browser, "run_javascript", lambda s, **kw: None)
        assert browser.fill_field("input", "value") is False

    def test_returns_false_on_non_macos(self, monkeypatch):
        monkeypatch.setattr(browser, "_is_macos", lambda: False)
        assert browser.fill_field("input", "value") is False

    def test_dispatches_input_event(self, monkeypatch):
        scripts: list[str] = []

        def capture_js(s, **kw):
            scripts.append(s)
            return "ok"

        monkeypatch.setattr(browser, "run_javascript", capture_js)
        browser.fill_field("input[name='q']", "test")
        assert "dispatchEvent" in scripts[0]
        assert "input" in scripts[0]
        assert "change" in scripts[0]


# ---------------------------------------------------------------------------
# submit_form
# ---------------------------------------------------------------------------


class TestSubmitForm:
    def test_returns_true_on_success(self, monkeypatch):
        monkeypatch.setattr(browser, "run_javascript", lambda s, **kw: "ok")
        assert browser.submit_form() is True

    def test_returns_false_on_not_found(self, monkeypatch):
        monkeypatch.setattr(browser, "run_javascript", lambda s, **kw: "not_found")
        assert browser.submit_form("#nope") is False

    def test_returns_false_on_error(self, monkeypatch):
        monkeypatch.setattr(browser, "run_javascript", lambda s, **kw: None)
        assert browser.submit_form() is False

    def test_returns_false_on_non_macos(self, monkeypatch):
        monkeypatch.setattr(browser, "_is_macos", lambda: False)
        assert browser.submit_form() is False

    def test_uses_default_form_selector(self, monkeypatch):
        scripts: list[str] = []

        def capture_js(s, **kw):
            scripts.append(s)
            return "ok"

        monkeypatch.setattr(browser, "run_javascript", capture_js)
        browser.submit_form()
        assert "querySelector('form')" in scripts[0]

    def test_uses_custom_selector(self, monkeypatch):
        scripts: list[str] = []

        def capture_js(s, **kw):
            scripts.append(s)
            return "ok"

        monkeypatch.setattr(browser, "run_javascript", capture_js)
        browser.submit_form("#my-form")
        assert "querySelector('#my-form')" in scripts[0]
