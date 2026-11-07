import os
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
CHECK_KEYS_SCRIPT = ROOT_DIR / "scripts" / "check_keys.py"


def test_check_keys_never_leaks_values(monkeypatch, tmp_path):
    """
    Asserts that check_keys.py prints only variable names and SET/UNSET,
    and NEVER prints any part of the actual secret value.
    """
    secret_value = "super_secret_test_key_xyz_12345"
    env_copy = os.environ.copy()
    env_copy["GROQ_API_KEY"] = secret_value

    result = subprocess.run(
        [sys.executable, str(CHECK_KEYS_SCRIPT)],
        capture_output=True,
        text=True,
        env=env_copy,
        cwd=str(ROOT_DIR),
    )

    stdout = result.stdout
    assert result.returncode == 0
    # Crucial security assertion: the secret string must never be anywhere in the output
    assert secret_value not in stdout
    # Ensure it reports SET for the configured key
    assert "GROQ_API_KEY" in stdout
    assert "SET" in stdout


def test_check_keys_file_parsing(tmp_path):
    from scripts.check_keys import get_key_status, print_key_status

    fake_env = tmp_path / ".env"
    secret_val = "hidden_val_in_env_file_98765"
    fake_env.write_text(f"NVIDIA_API_KEY={secret_val}\n", encoding="utf-8")

    status = get_key_status(env_path=fake_env)
    output = print_key_status(status)

    assert secret_val not in output
    assert "NVIDIA_API_KEY      : SET" in output
    assert "ANTHROPIC_API_KEY   : UNSET" in output
