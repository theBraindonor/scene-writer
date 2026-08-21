import scene.gui.app as app_module


def test_main_builds_and_shows_window_then_runs_event_loop(monkeypatch):
    calls = []

    class FakeApplication:
        def __init__(self, argv):
            calls.append(("QApplication", argv))

        def exec(self):
            calls.append(("exec",))

    class FakeWindow:
        def show(self):
            calls.append(("show",))

    monkeypatch.setattr(app_module, "QApplication", FakeApplication)
    monkeypatch.setattr(app_module, "MainWindow", lambda: FakeWindow())

    app_module.main()

    assert [call[0] for call in calls] == ["QApplication", "show", "exec"]
