# Desktop operation workflows

All three apps keep their existing industrial Qt theme. This document describes
how pane and configuration controls behave after the UI workflow review.

| Scenario | Expected operation |
| --- | --- |
| Add panes | Existing serial connections and terminal sessions keep running; new terminal panes start their own shells. |
| Remove panes | Only removed panes stop. Removing an active session asks for confirmation; Cancel restores the count selector. |
| Change terminal layout orientation | Retained panes move into the new layout with their sessions and screen state intact. |
| Edit a shell start path | The path applies when Restart opens a new shell. Changing the text alone does not move an existing shell. |
| Save | Writes the active configuration shown in the window title, even if another config is selected in the dropdown. Success is shown in the status bar. |
| Save As | Creates and activates a named configuration. Replacing a different existing config asks first. |
| Load | Applies the selected saved config. Active sessions require confirmation before replacement; unreadable configs keep current sessions intact. |
| Load another terminal config | Loaded paths and history replace the previous config's cached state. History from another config does not carry over. |
| Temporarily hide terminal panes | Start paths and history remain available when those pane IDs are added again, including after Save and a fresh launch. |
| Serial device disconnects | The pane reports the error, closes its resources, and restores Connect and port/baud controls. A late error from an old connection cannot close a new one. |
| Close Serial Monitor | Serial connections close and an in-progress scan receives a stop request. |
| Long serial output | The UI keeps the latest 10,000 text blocks; full received output is still written to rotating log files. |
| Open a log | Uses the platform's default file handler through Qt. |
| Scan | The interface selector is locked while scanning and an activity indicator is shown. Stop remains available; errors restore the controls. |
| Scan finds nothing | The status explains that no devices were found and suggests checking the interface and device connection. |
| Open discovered device | Select an identified device and use Open Web UI, or double-click it. Unknown devices do not enable that action. |

## Verification

Workflow tests live in each app's `tests/test_ui_workflows.py`. Run tests from
the corresponding app directory with `uv run pytest tests`. The Serial Monitor
suite mocks serial hardware and network access. MultiTerminal's live POSIX
backend needs macOS; Windows rendering/logic checks with mocked POSIX calls
are not a substitute for that integration test.

Before/after rendered screenshots are local QA output under each app's
ignored `build/ui-review/` directory. They use temporary configurations and
mocked devices/shell output rather than private user sessions.
