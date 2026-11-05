import concurrent.futures
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from backend.app.core.database import SessionLocal
from backend.app.activities.base import BaseActivity, ActivityExecutionContext, ActivityExecutionResult
from backend.app.execution.expressions import ExpressionEvaluator


class ForEachActivity(BaseActivity):
    """
    ForEach Activity:
    Iterates over an array of items and executes a nested sub-activity graph
    either sequentially or concurrently in parallel worker threads.
    Provides @item() expression access to each iteration's payload.
    """

    def execute(self) -> ActivityExecutionResult:
        config = self.context.config
        raw_items = config.get("items", [])
        is_sequential = bool(config.get("is_sequential", False))
        batch_count = max(1, min(int(config.get("batch_count", 4)), 50))
        sub_activities = config.get("activities", [])

        # Evaluate items expression if passed as string
        if isinstance(raw_items, str):
            evaluator = ExpressionEvaluator(
                parameters=self.context.pipeline_parameters,
                variables=self.context.pipeline_variables
            )
            items = evaluator.evaluate(raw_items)
        else:
            items = raw_items

        if not isinstance(items, list):
            items = [items] if items is not None else []

        total_items = len(items)
        self.log(
            "INFO",
            f"ForEach loop initialized with {total_items} items (mode={'sequential' if is_sequential else f'parallel (max {batch_count} threads)'})"
        )

        if total_items == 0:
            return ActivityExecutionResult(
                status="Succeeded",
                rows_written=0,
                output_variables={"item_count": 0, "succeeded_count": 0, "failed_count": 0},
                metrics={"total_iterations": 0}
            )

        succeeded_count = 0
        failed_count = 0
        errors = []

        def _execute_iteration(index: int, item_val: Any) -> bool:
            """Executes nested sub-activities for a single iteration item."""
            db: Session = SessionLocal()
            try:
                item_str = str(item_val)[:60]
                self.log("INFO", f"Iteration #{index + 1}/{total_items} started for item: {item_str}")

                # Lazily import to avoid circular dependency
                from backend.app.activities.factory import get_activity_instance

                for sub_act_cfg in sub_activities:
                    # Evaluate dynamic expressions using item context
                    evaluator = ExpressionEvaluator(
                        parameters=self.context.pipeline_parameters,
                        variables=self.context.pipeline_variables,
                        item=item_val,
                        pipeline_info={"RunId": self.context.pipeline_run_id}
                    )
                    resolved_sub_cfg = evaluator.evaluate(sub_act_cfg.get("config", {}))

                    sub_ctx = ActivityExecutionContext(
                        pipeline_run_id=self.context.pipeline_run_id,
                        activity_id=f"{self.context.activity_id}_iter{index}_{sub_act_cfg.get('id', 'sub')}",
                        activity_name=f"{sub_act_cfg.get('name', 'sub')} [Iter {index + 1}]",
                        activity_type=sub_act_cfg.get("type", "Wait"),
                        config=resolved_sub_cfg,
                        pipeline_parameters=self.context.pipeline_parameters,
                        pipeline_variables=self.context.pipeline_variables
                    )

                    executor = get_activity_instance(sub_ctx, db)
                    res = executor.execute()
                    if res.status == "Failed":
                        err_msg = f"Iteration #{index + 1} sub-activity '{sub_act_cfg.get('name')}' failed: {res.error_message}"
                        self.log("ERROR", err_msg)
                        return False

                self.log("INFO", f"Iteration #{index + 1}/{total_items} completed successfully.")
                return True
            except Exception as ex:
                self.log("ERROR", f"Iteration #{index + 1} fatal error: {str(ex)}")
                return False
            finally:
                db.close()

        # Execute either sequentially or in parallel thread pool
        if is_sequential or batch_count == 1:
            for idx, itm in enumerate(items):
                success = _execute_iteration(idx, itm)
                if success:
                    succeeded_count += 1
                else:
                    failed_count += 1
        else:
            with concurrent.futures.ThreadPoolExecutor(max_workers=batch_count) as pool:
                futures = {pool.submit(_execute_iteration, idx, itm): idx for idx, itm in enumerate(items)}
                for fut in concurrent.futures.as_completed(futures):
                    success = fut.result()
                    if success:
                        succeeded_count += 1
                    else:
                        failed_count += 1

        status = "Succeeded" if failed_count == 0 else "Failed"
        summary = f"ForEach completed: {succeeded_count}/{total_items} succeeded, {failed_count} failed."
        self.log("INFO" if status == "Succeeded" else "WARN", summary)

        return ActivityExecutionResult(
            status=status,
            rows_written=succeeded_count,
            error_message=None if status == "Succeeded" else f"{failed_count} iterations failed",
            output_variables={
                "item_count": total_items,
                "succeeded_count": succeeded_count,
                "failed_count": failed_count
            },
            metrics={
                "total_iterations": total_items,
                "succeeded_iterations": succeeded_count,
                "failed_iterations": failed_count
            }
        )
