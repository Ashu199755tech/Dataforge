import os
import shutil
import zipfile
import tarfile
import time
from typing import Dict, Any, List, Optional
from backend.app.activities.base import BaseActivity, ActivityExecutionResult
from backend.app.execution.expressions import ExpressionEvaluator


class ArchiveActivity(BaseActivity):
    """
    Archive & Compression Activity:
    Compresses files/directories into .zip or .tar.gz archives,
    or extracts archive packages to a target destination directory.
    """

    def execute(self) -> ActivityExecutionResult:
        config = self.context.config
        action = config.get("action", "compress").lower()
        raw_source = config.get("source_path")
        raw_dest = config.get("destination_path")
        archive_format = config.get("format", "zip").lower()
        remove_source = bool(config.get("remove_source", False))

        if not raw_source or not raw_dest:
            raise ValueError("Both 'source_path' and 'destination_path' are required for ArchiveActivity.")

        evaluator = ExpressionEvaluator(
            parameters=self.context.pipeline_parameters,
            variables=self.context.pipeline_variables
        )
        source_path = evaluator.evaluate(raw_source)
        destination_path = evaluator.evaluate(raw_dest)

        if not os.path.exists(source_path):
            raise FileNotFoundError(f"Source path '{source_path}' does not exist.")

        start_time = time.time()
        self.log("INFO", f"Executing Archive action '{action}' on '{source_path}' -> '{destination_path}'")

        if action in ("compress", "zip", "archive"):
            parent_dir = os.path.dirname(destination_path)
            if parent_dir:
                os.makedirs(parent_dir, exist_ok=True)

            if archive_format in ("zip", "zipfile"):
                with zipfile.ZipFile(destination_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                    if os.path.isdir(source_path):
                        for root, _, files in os.walk(source_path):
                            for file in files:
                                full_p = os.path.join(root, file)
                                rel_p = os.path.relpath(full_p, source_path)
                                zipf.write(full_p, arcname=rel_p)
                    else:
                        zipf.write(source_path, arcname=os.path.basename(source_path))

            elif archive_format in ("tar", "tar.gz", "gztar", "tgz"):
                mode = "w:gz" if "gz" in archive_format or "tgz" in archive_format else "w"
                with tarfile.open(destination_path, mode) as tar:
                    tar.add(source_path, arcname=os.path.basename(source_path))
            else:
                raise ValueError(f"Unsupported archive format: '{archive_format}'")

            archive_size = os.path.getsize(destination_path)
            if remove_source:
                if os.path.isdir(source_path):
                    shutil.rmtree(source_path)
                else:
                    os.remove(source_path)
                self.log("INFO", f"Source '{source_path}' removed after archiving.")

            duration = round(time.time() - start_time, 2)
            self.log("INFO", f"Archive created: {destination_path} ({archive_size} bytes, {duration}s)")
            return ActivityExecutionResult(
                status="Succeeded",
                output_variables={
                    "archive_path": destination_path,
                    "archive_size_bytes": archive_size,
                    "duration_seconds": duration
                },
                metrics={"archive_size_bytes": archive_size, "duration_seconds": duration}
            )

        elif action in ("extract", "unzip", "decompress"):
            os.makedirs(destination_path, exist_ok=True)
            extracted_files: List[str] = []

            if zipfile.is_zipfile(source_path):
                with zipfile.ZipFile(source_path, "r") as zipf:
                    zipf.extractall(destination_path)
                    extracted_files = [os.path.join(destination_path, n) for n in zipf.namelist()]
            elif tarfile.is_tarfile(source_path):
                with tarfile.open(source_path, "r:*") as tar:
                    tar.extractall(destination_path)
                    extracted_files = [os.path.join(destination_path, n) for n in tar.getnames()]
            else:
                raise ValueError(f"File '{source_path}' is not a recognized zip or tar archive.")

            if remove_source:
                os.remove(source_path)
                self.log("INFO", f"Source archive '{source_path}' removed after extraction.")

            duration = round(time.time() - start_time, 2)
            self.log("INFO", f"Extracted {len(extracted_files)} files to {destination_path} ({duration}s)")
            return ActivityExecutionResult(
                status="Succeeded",
                output_variables={
                    "extracted_count": len(extracted_files),
                    "extracted_files": extracted_files,
                    "destination_path": destination_path,
                    "duration_seconds": duration
                },
                metrics={"extracted_count": len(extracted_files), "duration_seconds": duration}
            )

        else:
            raise ValueError(f"Unsupported archive action: '{action}'. Expected 'compress' or 'extract'.")
