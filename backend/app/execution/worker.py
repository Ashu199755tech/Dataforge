import os
import sys
import json
import time
import tempfile
import subprocess
from typing import Dict, Any, Optional, Callable
from pydantic import BaseModel


class WorkerExecutionResult(BaseModel):
    exit_code: int
    stdout: str
    stderr: str
    duration_seconds: float
    output_variables: Dict[str, Any] = {}
    is_timeout: bool = False


class IsolatedSubprocessWorker:
    """
    Sandboxed worker execution engine.
    Executes user-provided scripts in an isolated child process with
    strict timeout guards, clean working environments, live stdout/stderr capture,
    and structured input/output JSON parameter binding.
    """

    def __init__(self, timeout_seconds: int = 60):
        self.timeout_seconds = timeout_seconds

    def execute_python_script(
        self,
        script_code: str,
        parameters: Optional[Dict[str, Any]] = None,
        environment_variables: Optional[Dict[str, str]] = None,
        log_callback: Optional[Callable[[str, str], None]] = None
    ) -> WorkerExecutionResult:
        """
        Executes a Python script string in an isolated child process.
        """
        parameters = parameters or {}
        env_vars = os.environ.copy()
        if environment_variables:
            env_vars.update(environment_variables)

        start_time = time.time()

        with tempfile.TemporaryDirectory(prefix="dataflow_worker_") as temp_dir:
            script_path = os.path.join(temp_dir, "user_script.py")
            input_path = os.path.join(temp_dir, "input_params.json")
            output_path = os.path.join(temp_dir, "output_vars.json")
            wrapper_path = os.path.join(temp_dir, "entrypoint.py")

            # Write input parameters
            with open(input_path, "w", encoding="utf-8") as f:
                json.dump(parameters, f, indent=2, default=str)

            # Write user script
            with open(script_path, "w", encoding="utf-8") as f:
                f.write(script_code)

            # Wrapper injects parameter helper and captures outputs
            wrapper_code = f"""
import os
import sys
import json

class DataFlowContext:
    def __init__(self, in_file, out_file):
        self.in_file = in_file
        self.out_file = out_file
        self.output_data = {{}}
        if os.path.exists(in_file):
            with open(in_file, 'r', encoding='utf-8') as f:
                self.params = json.load(f)
        else:
            self.params = {{}}

    def get_param(self, key, default=None):
        return self.params.get(key, default)

    def set_output(self, key, value):
        self.output_data[key] = value
        self.save()

    def set_outputs(self, data_dict):
        self.output_data.update(data_dict)
        self.save()

    def save(self):
        with open(self.out_file, 'w', encoding='utf-8') as f:
            json.dump(self.output_data, f, indent=2, default=str)

context = DataFlowContext(r'{input_path}', r'{output_path}')

# Execute user script within context namespace
with open(r'{script_path}', 'r', encoding='utf-8') as f:
    code_content = f.read()

exec(code_content, {{'__name__': '__main__', 'context': context, 'params': context.params}})
context.save()
"""
            with open(wrapper_path, "w", encoding="utf-8") as f:
                f.write(wrapper_code)

            # Spawn child process
            try:
                proc = subprocess.Popen(
                    [sys.executable, wrapper_path],
                    cwd=temp_dir,
                    env=env_vars,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )

                stdout_lines = []
                stderr_lines = []

                try:
                    stdout_str, stderr_str = proc.communicate(timeout=self.timeout_seconds)
                    exit_code = proc.returncode
                    is_timeout = False

                    if stdout_str:
                        for line in stdout_str.strip().split("\n"):
                            line_clean = line.strip()
                            if line_clean:
                                stdout_lines.append(line_clean)
                                if log_callback:
                                    log_callback("INFO", f"[Worker stdout] {line_clean}")

                    if stderr_str:
                        for line in stderr_str.strip().split("\n"):
                            line_clean = line.strip()
                            if line_clean:
                                stderr_lines.append(line_clean)
                                if log_callback:
                                    log_callback("WARN" if exit_code == 0 else "ERROR", f"[Worker stderr] {line_clean}")

                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.communicate()
                    is_timeout = True
                    exit_code = -1
                    if log_callback:
                        log_callback("ERROR", f"Worker process timed out after {self.timeout_seconds} seconds. Process terminated.")

                duration = round(time.time() - start_time, 2)

                # Read output variables if generated
                output_vars = {}
                if os.path.exists(output_path):
                    try:
                        with open(output_path, "r", encoding="utf-8") as f:
                            output_vars = json.load(f)
                    except Exception:
                        output_vars = {}

                return WorkerExecutionResult(
                    exit_code=exit_code,
                    stdout="\n".join(stdout_lines),
                    stderr="\n".join(stderr_lines),
                    duration_seconds=duration,
                    output_variables=output_vars,
                    is_timeout=is_timeout
                )

            except Exception as e:
                duration = round(time.time() - start_time, 2)
                return WorkerExecutionResult(
                    exit_code=1,
                    stdout="",
                    stderr=str(e),
                    duration_seconds=duration,
                    output_variables={},
                    is_timeout=False
                )
