"""
Auth Service — Custom JWT Authentication

Implements:
  - Password hashing with bcrypt
  - JWT access + refresh token generation/verification
  - User registration with org creation
  - Login with credential validation
  - RBAC role checks
"""

import uuid
from datetime import UTC, datetime, timedelta

import structlog
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.organization import Organization
from app.models.user import User
from app.schemas.auth import RegisterRequest, TokenResponse

log = structlog.get_logger()

# bcrypt context for password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ─── Password Utilities ────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    """Return bcrypt hash of the plaintext password."""
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plaintext password against its bcrypt hash."""
    return pwd_context.verify(plain, hashed)


# ─── JWT Utilities ────────────────────────────────────────────────────────────

def _create_token(data: dict, expire_delta: timedelta) -> str:
    """Create a signed JWT token with an expiry."""
    payload = data.copy()
    payload["exp"] = datetime.now(UTC) + expire_delta
    payload["iat"] = datetime.now(UTC)
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def create_access_token(user_id: str, org_id: str, role: str) -> str:
    """Create a short-lived JWT access token."""
    return _create_token(
        {"sub": user_id, "org_id": org_id, "role": role, "type": "access"},
        expire_delta=timedelta(minutes=settings.access_token_expire_minutes),
    )


def create_refresh_token(user_id: str) -> str:
    """Create a long-lived JWT refresh token."""
    return _create_token(
        {"sub": user_id, "type": "refresh"},
        expire_delta=timedelta(days=settings.refresh_token_expire_days),
    )


def decode_token(token: str) -> dict:
    """
    Decode and validate a JWT token.

    Raises:
        JWTError: If token is invalid, expired, or tampered with.
    """
    return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])


def build_token_response(user: User) -> TokenResponse:
    """Build the full token response for a logged-in user."""
    user_id = str(user.id)
    org_id = str(user.org_id)
    return TokenResponse(
        access_token=create_access_token(user_id, org_id, user.role),
        refresh_token=create_refresh_token(user_id),
        expires_in=settings.access_token_expire_minutes * 60,
    )


# ─── Auth Service ─────────────────────────────────────────────────────────────

class AuthService:
    """Business logic for authentication and user management."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def register(self, payload: RegisterRequest) -> tuple[User, TokenResponse]:
        """
        Register a new user and create their organization.

        Flow:
          1. Check email not already taken
          2. Create Organization
          3. Create User (owner role)
          4. Return user + JWT tokens
        """
        # Check duplicate email
        result = await self.db.execute(select(User).where(User.email == payload.email))
        if result.scalar_one_or_none():
            raise ValueError("Email already registered")

        # Create organization
        org = Organization(
            name=payload.org_name,
            slug=payload.org_slug,
        )
        self.db.add(org)
        await self.db.flush()  # Get org.id before creating user

        # Create user as org owner
        user = User(
            org_id=org.id,
            email=payload.email,
            password_hash=hash_password(payload.password),
            full_name=payload.full_name,
            role="owner",
        )
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)

        log.info("user.registered", email=user.email, org=org.slug)
        return user, build_token_response(user)

    async def login(self, email: str, password: str) -> tuple[User, TokenResponse]:
        """
        Authenticate a user and return JWT tokens.

        Raises:
            ValueError: On invalid credentials or inactive account.
        """
        result = await self.db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

        if not user or not user.password_hash:
            raise ValueError("Invalid credentials")
        if not verify_password(password, user.password_hash):
            raise ValueError("Invalid credentials")
        if not user.is_active:
            raise ValueError("Account is deactivated")

        # Update last login
        user.last_login_at = datetime.now(UTC)
        await self.db.commit()

        log.info("user.login", email=user.email)
        return user, build_token_response(user)

    async def refresh(self, refresh_token: str) -> TokenResponse:
        """Refresh an access token using a valid refresh token."""
        try:
            payload = decode_token(refresh_token)
            if payload.get("type") != "refresh":
                raise ValueError("Invalid token type")

            user_id = payload["sub"]
        except JWTError as exc:
            raise ValueError("Invalid or expired refresh token") from exc

        result = await self.db.execute(
            select(User).where(User.id == uuid.UUID(user_id))
        )
        user = result.scalar_one_or_none()
        if not user or not user.is_active:
            raise ValueError("User not found or inactive")

        return build_token_response(user)

    async def get_user_by_id(self, user_id: uuid.UUID) -> User | None:
        result = await self.db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()


# ─── RBAC Helpers ─────────────────────────────────────────────────────────────

ROLE_HIERARCHY = {"owner": 4, "admin": 3, "member": 2, "viewer": 1}


def has_role(user: User, minimum_role: str) -> bool:
    """Return True if the user's role meets or exceeds the minimum required role."""
    user_level = ROLE_HIERARCHY.get(user.role, 0)
    required_level = ROLE_HIERARCHY.get(minimum_role, 0)
    return user_level >= required_level
