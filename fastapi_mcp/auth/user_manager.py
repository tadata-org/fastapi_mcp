import logging
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Callable, Any
from typing_extensions import Annotated, Doc

from fastapi_mcp.types import (
    User,
    UserCreate,
    UserUpdate,
    UserRole,
    Permission,
)


logger = logging.getLogger(__name__)


class UserManager:
    """
    User management system for FastAPI-MCP.
    
    Provides user CRUD operations, authentication, and permission checking.
    """

    def __init__(
        self,
        enable_admin_user: Annotated[
            bool,
            Doc("Whether to enable the default admin user"),
        ] = True,
        admin_username: Annotated[
            str,
            Doc("Username for the default admin user"),
        ] = "admin",
        admin_password: Annotated[
            Optional[str],
            Doc("Password for the default admin user (if None, a random one will be generated)"),
        ] = None,
        password_hasher: Annotated[
            Optional[Callable[[str], str]],
            Doc("Optional custom password hasher function"),
        ] = None,
        password_verifier: Annotated[
            Optional[Callable[[str, str], bool]],
            Doc("Optional custom password verifier function"),
        ] = None,
    ):
        self._users: Dict[str, User] = {}
        self._users_by_username: Dict[str, User] = {}
        self._passwords: Dict[str, str] = {}
        self._password_hasher = password_hasher or self._default_hash_password
        self._password_verifier = password_verifier or self._default_verify_password

        if enable_admin_user:
            self._create_default_admin(admin_username, admin_password)

    def _default_hash_password(self, password: str) -> str:
        try:
            import bcrypt
            password_bytes = password.encode("utf-8")
            salt = bcrypt.gensalt()
            return bcrypt.hashpw(password_bytes, salt).decode("utf-8")
        except ImportError:
            import hashlib
            return hashlib.sha256(password.encode("utf-8")).hexdigest()

    def _default_verify_password(self, password: str, hashed: str) -> bool:
        try:
            import bcrypt
            return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
        except ImportError:
            import hashlib
            return hashlib.sha256(password.encode("utf-8")).hexdigest() == hashed

    def _create_default_admin(self, username: str, password: Optional[str] = None) -> User:
        if password is None:
            password = uuid.uuid4().hex
            logger.warning(f"Default admin user created with password: {password}")
            logger.warning("Please change this password in production!")

        admin_user = User(
            id=str(uuid.uuid4()),
            username=username,
            role=UserRole.ADMIN,
            permissions=[Permission.ADMIN_ALL],
            is_active=True,
        )

        self._users[admin_user.id] = admin_user
        self._users_by_username[username] = admin_user
        self._passwords[admin_user.id] = self._password_hasher(password)

        logger.info(f"Default admin user created: {username}")
        return admin_user

    def create_user(self, user_create: UserCreate) -> User:
        if user_create.username in self._users_by_username:
            raise ValueError(f"Username '{user_create.username}' already exists")

        user = User(
            id=str(uuid.uuid4()),
            username=user_create.username,
            email=user_create.email,
            role=user_create.role,
            permissions=user_create.permissions,
            is_active=True,
        )

        self._users[user.id] = user
        self._users_by_username[user.username] = user

        if user_create.password:
            self._passwords[user.id] = self._password_hasher(user_create.password)

        logger.info(f"User created: {user.username} (ID: {user.id})")
        return user

    def get_user(self, user_id: str) -> Optional[User]:
        return self._users.get(user_id)

    def get_user_by_username(self, username: str) -> Optional[User]:
        return self._users_by_username.get(username)

    def list_users(self) -> List[User]:
        return list(self._users.values())

    def update_user(self, user_id: str, user_update: UserUpdate) -> Optional[User]:
        user = self._users.get(user_id)
        if not user:
            return None

        update_data = user_update.model_dump(exclude_unset=True)

        for key, value in update_data.items():
            if value is not None:
                setattr(user, key, value)

        logger.info(f"User updated: {user.username} (ID: {user.id})")
        return user

    def delete_user(self, user_id: str) -> bool:
        user = self._users.get(user_id)
        if not user:
            return False

        del self._users[user_id]
        del self._users_by_username[user.username]

        if user_id in self._passwords:
            del self._passwords[user_id]

        logger.info(f"User deleted: {user.username} (ID: {user.id})")
        return True

    def authenticate_user(self, username: str, password: str) -> Optional[User]:
        user = self._users_by_username.get(username)
        if not user:
            logger.warning(f"Authentication failed: user '{username}' not found")
            return None

        if not user.is_active:
            logger.warning(f"Authentication failed: user '{username}' is inactive")
            return None

        hashed_password = self._passwords.get(user.id)
        if not hashed_password:
            logger.warning(f"Authentication failed: no password set for user '{username}'")
            return None

        if not self._password_verifier(password, hashed_password):
            logger.warning(f"Authentication failed: invalid password for user '{username}'")
            return None

        user.last_login = datetime.utcnow()
        logger.info(f"User authenticated: {username} (ID: {user.id})")
        return user

    def set_password(self, user_id: str, password: str) -> bool:
        user = self._users.get(user_id)
        if not user:
            return False

        self._passwords[user_id] = self._password_hasher(password)
        logger.info(f"Password set for user: {user.username} (ID: {user.id})")
        return True

    def check_permission(self, user_id: str, permission: Permission) -> bool:
        user = self._users.get(user_id)
        if not user:
            return False
        return user.has_permission(permission)

    def check_role(self, user_id: str, role: UserRole) -> bool:
        user = self._users.get(user_id)
        if not user:
            return False
        return user.has_role(role)

    def get_permissions_for_user(self, user_id: str) -> List[Permission]:
        user = self._users.get(user_id)
        if not user:
            return []
        if user.role == UserRole.ADMIN:
            return list(Permission)
        return user.permissions

    def get_stats(self) -> Dict[str, Any]:
        total_users = len(self._users)
        active_users = sum(1 for u in self._users.values() if u.is_active)
        users_by_role = {
            role.value: sum(1 for u in self._users.values() if u.role == role)
            for role in UserRole
        }

        return {
            "total_users": total_users,
            "active_users": active_users,
            "users_by_role": users_by_role,
        }
