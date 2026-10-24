import platform
import subprocess
import sys
from typing import Dict


def _get_shell_cmd() -> list[str]:
    """Return the appropriate shell for the current platform."""
    if platform.system() == "Darwin" or platform.system() == "Linux":
        return ["/bin/bash", "-lc"]
    # Windows: use cmd.exe
    return ["cmd", "/c"]


class LocalController:
    """Minimal controller to execute bash and python code locally.

    WARNING: Executing arbitrary code is dangerous. Only enable/use this in trusted
    environments and with trusted inputs.
    """

    def run_bash_script(self, code: str, timeout: int = 30) -> Dict:
        shell_cmd = _get_shell_cmd()
        try:
            proc = subprocess.run(
                [*shell_cmd, code],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            output = (proc.stdout or "") + (proc.stderr or "")

            print("BASH OUTPUT =======================================")
            print(output)
            print("BASH OUTPUT =======================================")

            return {
                "status": "ok" if proc.returncode == 0 else "error",
                "returncode": proc.returncode,
                "output": output,
                "error": "",
            }
        except subprocess.TimeoutExpired as e:
            return {
                "status": "error",
                "returncode": -1,
                "output": e.stdout or "",
                "error": f"TimeoutExpired: {str(e)}",
            }
        except Exception as e:
            return {
                "status": "error",
                "returncode": -1,
                "output": "",
                "error": str(e),
            }

    def run_python_script(self, code: str) -> Dict:
        try:
            proc = subprocess.run(
                [sys.executable, "-c", code],
                capture_output=True,
                text=True,
            )
            print("PYTHON OUTPUT =======================================")
            print(proc.stdout or "")
            print("PYTHON OUTPUT =======================================")
            return {
                "status": "ok" if proc.returncode == 0 else "error",
                "return_code": proc.returncode,
                "output": proc.stdout or "",
                "error": proc.stderr or "",
            }
        except Exception as e:
            return {
                "status": "error",
                "return_code": -1,
                "output": "",
                "error": str(e),
            }


class LocalEnv:
    """Simple environment that provides a controller compatible with CodeAgent."""

    def __init__(self):
        self.controller = LocalController()
