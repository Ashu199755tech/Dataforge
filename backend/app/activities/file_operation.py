import os
import glob
import shutil
import time
from typing import Dict, Any, List, Optional
from backend.app.activities.base import BaseActivity, ActivityExecutionResult
from backend.app.execution.expressions import ExpressionEvaluator


class FileOperationActivity(BaseActivity):
    """
    File Operation Activity:
    Performs file system operations across local or mounted storage paths:
    copy, move, delete, rename, and file existence checking with glob pattern support.
    """

    def execute(self) -> ActivityExecutionResult:
        config = self.context.config
        operation = config.get("operation", "copy").lower()
        raw_source = config.get("source_path")
        raw_dest = config.get("destination_path")
        overwrite = bool(config.get("overwrite", True))

        if not raw_source:
            raise ValueError("'source_path' is required for FileOperationActivity.")

        evaluator = ExpressionEvaluator(
            parameters=self.context.pipeline_parameters,
            variables=self.context.pipeline_variables
        )
        source_pattern = evaluator.evaluate(raw_source)
        destination = evaluator.evaluate(raw_dest) if raw_dest else None

        self.log("INFO", f"Executing file operation '{operation}' on pattern '{source_pattern}'")
        start_time = time.time()

        # Handle file_exists operation
        if operation in ("file_exists", "exists"):
            matched_files = glob.glob(source_pattern, recursive=True)
            exists = len(matched_files) > 0
            size_bytes = sum(os.path.getsize(f) for f in matched_files if os.path.isfile(f))
            duration = round(time.time() - start_time, 2)
            self.log("INFO", f"File exists check: {exists} ({len(matched_files)} files matched)")
            return ActivityExecutionResult(
                status="Succeeded",
                output_variables={
                    "exists": exists,
                    "matched_count": len(matched_files),
                    "matched_files": matched_files,
                    "total_size_bytes": size_bytes,
                    "duration_seconds": duration
                },
                metrics={"matched_count": len(matched_files), "duration_seconds": duration}
            )

        matched_files = glob.glob(source_pattern, recursive=True)
        if not matched_files:
            if operation in ("copy", "move", "rename"):
                raise FileNotFoundError(f"No files matching '{source_pattern}' found for '{operation}' operation.")
            else:
                return ActivityExecutionResult(
                    status="Succeeded",
                    output_variables={"affected_count": 0, "affected_files": []},
                    metrics={"affected_count": 0}
                )

        affected_files = []

        if operation == "delete":
            for f in matched_files:
                if os.path.isdir(f):
                    shutil.rmtree(f)
                else:
                    os.remove(f)
                affected_files.append(f)
                self.log("INFO", f"Deleted: {f}")

        elif operation in ("copy", "move"):
            if not destination:
                raise ValueError(f"'destination_path' is required for '{operation}' operation.")

            # Create destination directory if destination ends in slash or multiple files
            if len(matched_files) > 1 or destination.endswith("/") or destination.endswith("\\") or os.path.isdir(destination):
                os.makedirs(destination, exist_ok=True)
                is_dir_dest = True
            else:
                is_dir_dest = False
                parent = os.path.dirname(destination)
                if parent:
                    os.makedirs(parent, exist_ok=True)

            for src in matched_files:
                if is_dir_dest:
                    target_file = os.path.join(destination, os.path.basename(src))
                else:
                    target_file = destination

                if os.path.exists(target_file) and not overwrite:
                    self.log("WARN", f"Skipping existing file '{target_file}' (overwrite=False)")
                    continue

                if operation == "copy":
                    if os.path.isdir(src):
                        if os.path.exists(target_file):
                            shutil.rmtree(target_file)
                        shutil.copytree(src, target_file)
                    else:
                        shutil.copy2(src, target_file)
                    affected_files.append(target_file)
                    self.log("INFO", f"Copied: {src} -> {target_file}")
                elif operation == "move":
                    if os.path.exists(target_file):
                        if os.path.isdir(target_file):
                            shutil.rmtree(target_file)
                        else:
                            os.remove(target_file)
                    shutil.move(src, target_file)
                    affected_files.append(target_file)
                    self.log("INFO", f"Moved: {src} -> {target_file}")

        elif operation == "rename":
            if not destination:
                raise ValueError("'destination_path' is required for 'rename' operation.")
            src = matched_files[0]
            parent = os.path.dirname(destination)
            if parent:
                os.makedirs(parent, exist_ok=True)
            if os.path.exists(destination) and overwrite:
                os.remove(destination)
            os.rename(src, destination)
            affected_files.append(destination)
            self.log("INFO", f"Renamed: {src} -> {destination}")

        else:
            raise ValueError(f"Unsupported file operation: '{operation}'")

        duration = round(time.time() - start_time, 2)
        return ActivityExecutionResult(
            status="Succeeded",
            output_variables={
                "operation": operation,
                "affected_count": len(affected_files),
                "affected_files": affected_files,
                "duration_seconds": duration
            },
            metrics={"affected_count": len(affected_files), "duration_seconds": duration}
        )
