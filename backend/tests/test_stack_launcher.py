import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    ("host", "device"), [("Darwin", "mps"), ("Darwin", "cpu"), ("Linux", "cpu")]
)
def test_stack_starts_mac_bridge_and_container_worker(tmp_path: Path, host: str, device: str):
    log = tmp_path / "commands.log"
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    scripts = {
        "uname": '#!/bin/sh\nprintf "%s\\n" "$TEST_HOST"\n',
        "engine": '#!/bin/sh\nprintf "compose: %s\\n" "$*" >> "$TEST_LOG"\n',
        "python": (
            "#!/bin/sh\n"
            'printf "bridge-check: %s\\n" "$*" >> "$TEST_LOG"\n'
            'case "$2" in *"import torch"*) [ "$TEST_DEVICE" = mps ];; *) exit 0;; esac\n'
        ),
    }
    for name, body in scripts.items():
        path = fake_bin / name
        path.write_text(body)
        path.chmod(0o755)
    env = dict(os.environ)
    env.update(
        PATH=f"{fake_bin}:{env.get('PATH', '')}",
        CONTAINER_ENGINE=str(fake_bin / "engine"),
        MPS_WORKER_PYTHON=str(fake_bin / "python"),
        TEST_LOG=str(log),
        TEST_HOST=host,
        TEST_DEVICE=device,
        STORAGE__DIR=str(tmp_path / "data"),
    )
    # Neither test path starts containers or imports the model: both executables are mocked.
    result = subprocess.run(
        ["bash", str(ROOT / "scripts/run-stack.sh")],
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr
    commands = log.read_text()
    assert "compose up --build" in commands
    assert "--scale worker=0" not in commands
    if host == "Darwin":
        assert "bridge-check:" in commands
        if device == "cpu":
            assert "MPS is unavailable" in result.stderr
    else:
        assert "bridge-check:" not in commands
