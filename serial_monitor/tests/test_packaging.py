from pathlib import Path
import subprocess


def test_required_build_spec_is_present_and_not_ignored():
    root = Path(__file__).resolve().parents[2]
    spec = root / "serial_monitor/MyTools.spec"
    assert spec.is_file()
    compile(spec.read_text(encoding="utf-8"), str(spec), "exec")
    result = subprocess.run(["git", "-c", "core.excludesFile=", "check-ignore", "serial_monitor/MyTools.spec"], cwd=root, capture_output=True)
    assert result.returncode == 1, result.stdout + result.stderr
