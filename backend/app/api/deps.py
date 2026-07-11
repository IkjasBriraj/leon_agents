"""
FastAPI dependency injection — shared dependencies for all routes.

Provides:
  - `get_db` — async DB session per request
  - `get_redis` — Redis client
  - `get_current_user` — authenticated user from JWT
  - `require_role` — role-based access control factory
"""

import uuid

import structlog
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db, get_redis
from app.models.user import User
from app.services.auth_service import AuthService, decode_token, has_role

log = structlog.get_logger()

# Re-export for convenience in route files
__all__ = ["get_db", "get_redis", "get_current_user", "require_role", "CurrentUser"]

security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    FastAPI dependency: extract and validate JWT from Authorization header.

    Returns the authenticated User ORM model.

    Raises:
        401 Unauthorized — missing, invalid, or expired token
        403 Forbidden    — account deactivated
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if not credentials:
        raise credentials_exception

    try:
        payload = decode_token(credentials.credentials)
        user_id: str | None = payload.get("sub")
        token_type: str | None = payload.get("type")

        if not user_id or token_type != "access":
            raise credentials_exception

    except JWTError:
        raise credentials_exception

    auth_service = AuthService(db)
    user = await auth_service.get_user_by_id(uuid.UUID(user_id))

    if user is None:
        raise credentials_exception
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated",
        )

    return user


# Type alias for dependency
CurrentUser = Depends(get_current_user)


def require_role(minimum_role: str):
    """
    Factory: returns a FastAPI dependency that enforces a minimum RBAC role.

    Example::

        @router.delete("/agents/{id}")
        async def delete_agent(
            user: User = Depends(require_role("admin"))
        ):
            ...
    """
    async def role_checker(
        current_user: User = Depends(get_current_user),
    ) -> User:
        if not has_role(current_user, minimum_role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires '{minimum_role}' role or higher",
            )
        return current_user

    return Depends(role_checker)
