from typing import List, Dict, Any, Set, Optional
from collections import defaultdict, deque


class DAGValidationError(Exception):
    pass


class PipelineDAG:
    """
    DAG Parser and Topological Resolver for DataFlow Pipelines.
    Supports enterprise dependency conditions (ADF-style):
      - Succeeded: Executes when parent activity succeeds
      - Failed: Executes when parent activity fails (failure handling / alert)
      - Completed: Executes when parent activity completes (regardless of success/fail)
      - Skipped: Executes when parent activity was skipped
    """

    def __init__(self, activities: List[Dict[str, Any]]):
        self.activities = activities
        self.activity_map: Dict[str, Dict[str, Any]] = {a["id"]: a for a in activities}
        self.graph: Dict[str, List[Dict[str, Any]]] = defaultdict(list)  # parent -> list of child dependencies
        self.reverse_graph: Dict[str, List[Dict[str, Any]]] = defaultdict(list)  # child -> list of parents
        self._build_graphs()
        self.validate()

    def _build_graphs(self):
        for act in self.activities:
            act_id = act["id"]
            depends_on = act.get("depends_on", [])
            for dep in depends_on:
                parent_id = dep if isinstance(dep, str) else dep.get("activity_id")
                condition = "Succeeded" if isinstance(dep, str) else dep.get("condition", "Succeeded")

                if parent_id not in self.activity_map:
                    raise DAGValidationError(f"Activity '{act_id}' depends on non-existent activity '{parent_id}'")

                self.graph[parent_id].append({"activity_id": act_id, "condition": condition})
                self.reverse_graph[act_id].append({"activity_id": parent_id, "condition": condition})

    def validate(self):
        """Detects cycles using Kahn's algorithm."""
        in_degree = {act_id: len(self.reverse_graph[act_id]) for act_id in self.activity_map}
        queue = deque([act_id for act_id, deg in in_degree.items() if deg == 0])
        visited_count = 0

        while queue:
            node = queue.popleft()
            visited_count += 1
            for edge in self.graph[node]:
                child = edge["activity_id"]
                in_degree[child] -= 1
                if in_degree[child] == 0:
                    queue.append(child)

        if visited_count != len(self.activity_map):
            raise DAGValidationError("Cycle detected in pipeline activity dependencies! Pipelines must be a DAG.")

    def get_root_activities(self) -> List[str]:
        """Returns activities with no upstream dependencies."""
        return [act_id for act_id in self.activity_map if len(self.reverse_graph[act_id]) == 0]

    def is_activity_ready(self, activity_id: str, completed_activities: Dict[str, str]) -> bool:
        """
        Determines if an activity's upstream dependencies have been satisfied.
        completed_activities maps activity_id -> status ('Succeeded', 'Failed', 'Skipped')
        """
        parents = self.reverse_graph[activity_id]
        if not parents:
            return True

        for parent_edge in parents:
            parent_id = parent_edge["activity_id"]
            expected_condition = parent_edge.get("condition", "Succeeded")

            if parent_id not in completed_activities:
                return False  # Upstream parent has not finished yet

            parent_status = completed_activities[parent_id]
            if expected_condition == "Succeeded" and parent_status != "Succeeded":
                return False
            elif expected_condition == "Failed" and parent_status != "Failed":
                return False
            elif expected_condition == "Skipped" and parent_status != "Skipped":
                return False
            elif expected_condition == "Completed" and parent_status not in ("Succeeded", "Failed"):
                return False

        return True

    def is_activity_dead(self, activity_id: str, completed_activities: Dict[str, str]) -> bool:
        """
        Determines if an activity can never execute because at least one upstream parent
        terminated with a status that contradicts the condition required by this activity.
        Dead activities should automatically transition to 'Skipped'.
        """
        parents = self.reverse_graph[activity_id]
        for parent_edge in parents:
            parent_id = parent_edge["activity_id"]
            expected_condition = parent_edge.get("condition", "Succeeded")

            if parent_id in completed_activities:
                parent_status = completed_activities[parent_id]
                # If parent Succeeded but child expected Failed or Skipped -> dead
                if parent_status == "Succeeded" and expected_condition in ("Failed", "Skipped"):
                    return True
                # If parent Failed but child expected Succeeded or Skipped -> dead
                elif parent_status == "Failed" and expected_condition in ("Succeeded", "Skipped"):
                    return True
                # If parent was Skipped and child expected Succeeded, Failed, or Completed -> dead
                elif parent_status == "Skipped" and expected_condition in ("Succeeded", "Failed", "Completed"):
                    return True

        return False
