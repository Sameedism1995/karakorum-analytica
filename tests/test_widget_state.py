"""Widget session-state helper tests."""

from dashboard.widget_state import _RESETS_KEY, prepare_widgets, schedule_widget_reset


class _FakeSessionState(dict):
    def __getattr__(self, key):
        return self[key]

    def __setattr__(self, key, value):
        self[key] = value


def test_schedule_then_prepare_clears_widget_key(monkeypatch):
    state = _FakeSessionState()
    monkeypatch.setattr("dashboard.widget_state.st.session_state", state)

    schedule_widget_reset("x_watch_new_handle", "")
    assert state[_RESETS_KEY]["x_watch_new_handle"] == ""

    state["x_watch_new_handle"] = "old value"
    prepare_widgets({"x_watch_new_handle": "default"})
    assert state["x_watch_new_handle"] == ""
    assert _RESETS_KEY not in state
