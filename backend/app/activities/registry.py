from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Type, Tuple, Callable
from sqlalchemy.orm import Session
from backend.app.activities.base import BaseActivity, ActivityExecutionContext


@dataclass
class ActivityMetadata:
    """
    Standardized enterprise metadata describing an activity's capabilities,
    schema contracts, inputs, outputs, and UI representation.
    """
    activity_type: str
    display_name: str
    category: str  # Move & Transform, Control Flow, Compute & External, File & Storage
    description: str
    version: str = "1.0.0"
    icon: str = "Layers"  # Lucide icon identifier
    config_schema: Dict[str, Any] = field(default_factory=dict)
    inputs: List[Dict[str, Any]] = field(default_factory=list)
    outputs: List[Dict[str, Any]] = field(default_factory=list)
    supports_retry: bool = True
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "activity_type": self.activity_type,
            "display_name": self.display_name,
            "category": self.category,
            "description": self.description,
            "version": self.version,
            "icon": self.icon,
            "config_schema": self.config_schema,
            "inputs": self.inputs,
            "outputs": self.outputs,
            "supports_retry": self.supports_retry,
            "tags": self.tags
        }


class ActivityRegistry:
    """
    Centralized, thread-safe Activity Registry.
    Allows dynamic registration, metadata introspection, schema validation,
    and executor instantiation without modifying core orchestration components.
    """

    def __init__(self):
        self._executors: Dict[str, Type[BaseActivity]] = {}
        self._metadata: Dict[str, ActivityMetadata] = {}
        self._aliases: Dict[str, str] = {}

    def register(
        self,
        metadata: ActivityMetadata,
        executor_cls: Type[BaseActivity],
        aliases: Optional[List[str]] = None
    ) -> None:
        """Registers an activity class and its associated enterprise metadata."""
        norm_key = metadata.activity_type.lower()
        self._executors[norm_key] = executor_cls
        self._metadata[norm_key] = metadata

        if aliases:
            for alias in aliases:
                self._aliases[alias.lower()] = norm_key

    def register_activity(
        self,
        activity_type: str,
        display_name: str,
        category: str,
        description: str,
        version: str = "1.0.0",
        icon: str = "Layers",
        config_schema: Optional[Dict[str, Any]] = None,
        inputs: Optional[List[Dict[str, Any]]] = None,
        outputs: Optional[List[Dict[str, Any]]] = None,
        supports_retry: bool = True,
        tags: Optional[List[str]] = None,
        aliases: Optional[List[str]] = None
    ) -> Callable[[Type[BaseActivity]], Type[BaseActivity]]:
        """Decorator for declarative activity registration."""
        def decorator(cls: Type[BaseActivity]) -> Type[BaseActivity]:
            meta = ActivityMetadata(
                activity_type=activity_type,
                display_name=display_name,
                category=category,
                description=description,
                version=version,
                icon=icon,
                config_schema=config_schema or {},
                inputs=inputs or [],
                outputs=outputs or [],
                supports_retry=supports_retry,
                tags=tags or []
            )
            self.register(meta, cls, aliases=aliases)
            return cls
        return decorator

    def resolve_type(self, activity_type: str) -> str:
        """Resolves case variations and aliases to the primary canonical activity type key."""
        norm = activity_type.lower()
        return self._aliases.get(norm, norm)

    def get_executor(self, activity_type: str) -> Optional[Type[BaseActivity]]:
        key = self.resolve_type(activity_type)
        return self._executors.get(key)

    def get_metadata(self, activity_type: str) -> Optional[ActivityMetadata]:
        key = self.resolve_type(activity_type)
        return self._metadata.get(key)

    def list_activities(self) -> List[Dict[str, Any]]:
        """Returns metadata for all registered activities."""
        return [meta.to_dict() for meta in self._metadata.values()]

    def validate_config(self, activity_type: str, config: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Validates configuration against declared required fields in config_schema."""
        meta = self.get_metadata(activity_type)
        if not meta:
            return False, f"Activity type '{activity_type}' is not registered."

        schema = meta.config_schema
        required_fields = schema.get("required", [])
        for field in required_fields:
            if field not in config or config[field] is None or config[field] == "":
                return False, f"Missing required configuration field: '{field}' for activity '{meta.display_name}'"

        return True, None

    def create_instance(self, context: ActivityExecutionContext, db: Session) -> BaseActivity:
        """Creates an instance of the registered executor class."""
        executor_cls = self.get_executor(context.activity_type)
        if not executor_cls:
            raise ValueError(f"Unknown or unsupported activity type: '{context.activity_type}'")
        return executor_cls(context, db)


# Global Singleton Registry Instance
activity_registry = ActivityRegistry()
