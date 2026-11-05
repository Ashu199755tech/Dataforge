from typing import List, Optional
from fastapi import HTTPException, status, Depends
from sqlalchemy.orm import Session
from backend.app.core.database import get_db
from backend.app.models.user import User
from backend.app.models.security import WorkspaceMember
from backend.app.api.deps import get_current_user

# Role hierarchies
ROLE_HIERARCHY = {
    "Admin": 100,
    "Contributor": 75,
    "DataEngineer": 75,
    "Operator": 50,
    "Viewer": 25,
    "Reader": 25
}

WORKSPACE_ROLE_HIERARCHY = {
    "Owner": 100,
    "Contributor": 75,
    "Operator": 50,
    "Viewer": 25
}


def require_role(allowed_roles: List[str]):
    """FastAPI dependency to enforce global user role authorization."""
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        user_role = current_user.role or "Viewer"
        # Admin always has full access
        if user_role == "Admin":
            return current_user

        if user_role not in allowed_roles:
            user_level = ROLE_HIERARCHY.get(user_role, 0)
            required_min = min([ROLE_HIERARCHY.get(r, 0) for r in allowed_roles], default=100)
            if user_level < required_min:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Access denied. Required role in {allowed_roles}, your role is '{user_role}'."
                )
        return current_user
    return role_checker


def check_workspace_permission(
    workspace_id: str,
    min_role: str,
    user: User,
    db: Session
) -> bool:
    """Verifies user's permission level within a specific workspace."""
    if user.role == "Admin":
        return True

    member = db.query(WorkspaceMember).filter(
        WorkspaceMember.workspace_id == workspace_id,
        WorkspaceMember.user_id == user.id
    ).first()

    if not member:
        return False

    user_level = WORKSPACE_ROLE_HIERARCHY.get(member.role, 0)
    required_level = WORKSPACE_ROLE_HIERARCHY.get(min_role, 100)
    return user_level >= required_level
