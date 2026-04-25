import logging
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from typing_extensions import Annotated, Doc

from fastapi_mcp.types import (
    ApiKey,
    ApiKeyCreate,
    ApiKeyUpdate,
    ApiKeyStatus,
    Permission,
)


logger = logging.getLogger(__name__)


class ApiKeyManager:
    """
    API Key management system for FastAPI-MCP.
    
    Provides API key generation, validation, and management.
    """

    def __init__(
        self,
        key_prefix: Annotated[
            str,
            Doc("Prefix for generated API keys"),
        ] = "mcp",
        default_permissions: Annotated[
            List[Permission],
            Doc("Default permissions for new API keys"),
        ] = None,
        default_rate_limit: Annotated[
            Optional[int],
            Doc("Default rate limit for new API keys (requests per window)"),
        ] = None,
        default_rate_limit_window: Annotated[
            int,
            Doc("Default rate limit window in seconds"),
        ] = 60,
    ):
        self._api_keys: Dict[str, ApiKey] = {}
        self._api_keys_by_key: Dict[str, ApiKey] = {}
        self._api_keys_by_user: Dict[str, List[str]] = {}
        self._key_prefix = key_prefix
        self._default_permissions = default_permissions or [Permission.READ_TOOLS, Permission.CALL_TOOLS]
        self._default_rate_limit = default_rate_limit
        self._default_rate_limit_window = default_rate_limit_window

    def create_api_key(
        self,
        user_id: str,
        key_create: ApiKeyCreate,
    ) -> ApiKey:
        key_value = ApiKey.generate_key(self._key_prefix)
        api_key_id = str(uuid.uuid4())

        expires_at = None
        if key_create.expires_in_days:
            expires_at = datetime.utcnow() + timedelta(days=key_create.expires_in_days)

        api_key = ApiKey(
            id=api_key_id,
            key=key_value,
            name=key_create.name,
            description=key_create.description,
            user_id=user_id,
            status=ApiKeyStatus.ACTIVE,
            permissions=key_create.permissions or self._default_permissions,
            rate_limit=key_create.rate_limit or self._default_rate_limit,
            rate_limit_window=key_create.rate_limit_window or self._default_rate_limit_window,
            expires_at=expires_at,
            created_at=datetime.utcnow(),
        )

        self._api_keys[api_key_id] = api_key
        self._api_keys_by_key[key_value] = api_key

        if user_id not in self._api_keys_by_user:
            self._api_keys_by_user[user_id] = []
        self._api_keys_by_user[user_id].append(api_key_id)

        logger.info(f"API Key created: {api_key.name} (ID: {api_key_id}) for user {user_id}")
        return api_key

    def get_api_key(self, api_key_id: str) -> Optional[ApiKey]:
        return self._api_keys.get(api_key_id)

    def get_api_key_by_key(self, key: str) -> Optional[ApiKey]:
        return self._api_keys_by_key.get(key)

    def validate_api_key(self, key: str) -> Optional[ApiKey]:
        api_key = self._api_keys_by_key.get(key)
        if not api_key:
            return None
        if not api_key.is_valid():
            return None
        return api_key

    def list_api_keys(self, user_id: Optional[str] = None) -> List[ApiKey]:
        if user_id:
            api_key_ids = self._api_keys_by_user.get(user_id, [])
            return [self._api_keys[aid] for aid in api_key_ids if aid in self._api_keys]
        return list(self._api_keys.values())

    def list_active_api_keys(self, user_id: Optional[str] = None) -> List[ApiKey]:
        keys = self.list_api_keys(user_id)
        return [k for k in keys if k.is_valid()]

    def update_api_key(self, api_key_id: str, key_update: ApiKeyUpdate) -> Optional[ApiKey]:
        api_key = self._api_keys.get(api_key_id)
        if not api_key:
            return None

        update_data = key_update.model_dump(exclude_unset=True)

        for key, value in update_data.items():
            if value is not None:
                setattr(api_key, key, value)

        logger.info(f"API Key updated: {api_key.name} (ID: {api_key_id})")
        return api_key

    def revoke_api_key(self, api_key_id: str) -> bool:
        api_key = self._api_keys.get(api_key_id)
        if not api_key:
            return False

        api_key.status = ApiKeyStatus.REVOKED
        logger.info(f"API Key revoked: {api_key.name} (ID: {api_key_id})")
        return True

    def delete_api_key(self, api_key_id: str) -> bool:
        api_key = self._api_keys.get(api_key_id)
        if not api_key:
            return False

        key_value = api_key.key
        user_id = api_key.user_id

        del self._api_keys[api_key_id]
        del self._api_keys_by_key[key_value]

        if user_id in self._api_keys_by_user:
            if api_key_id in self._api_keys_by_user[user_id]:
                self._api_keys_by_user[user_id].remove(api_key_id)

        logger.info(f"API Key deleted: {api_key.name} (ID: {api_key_id})")
        return True

    def record_usage(self, api_key_id: str) -> bool:
        api_key = self._api_keys.get(api_key_id)
        if not api_key:
            return False

        api_key.usage_count += 1
        api_key.last_used_at = datetime.utcnow()
        return True

    def check_permission(self, api_key_id: str, permission: Permission) -> bool:
        api_key = self._api_keys.get(api_key_id)
        if not api_key:
            return False
        if not api_key.is_valid():
            return False
        if Permission.ADMIN_ALL in api_key.permissions:
            return True
        return permission in api_key.permissions

    def get_permissions_for_key(self, api_key_id: str) -> List[Permission]:
        api_key = self._api_keys.get(api_key_id)
        if not api_key:
            return []
        return api_key.permissions

    def rotate_api_key(self, api_key_id: str) -> Optional[ApiKey]:
        api_key = self._api_keys.get(api_key_id)
        if not api_key:
            return None

        old_key = api_key.key
        new_key = ApiKey.generate_key(self._key_prefix)

        del self._api_keys_by_key[old_key]
        api_key.key = new_key
        self._api_keys_by_key[new_key] = api_key

        logger.info(f"API Key rotated: {api_key.name} (ID: {api_key_id})")
        return api_key

    def get_stats(self) -> Dict[str, Any]:
        total_keys = len(self._api_keys)
        active_keys = sum(1 for k in self._api_keys.values() if k.is_valid())
        revoked_keys = sum(1 for k in self._api_keys.values() if k.status == ApiKeyStatus.REVOKED)
        inactive_keys = sum(1 for k in self._api_keys.values() if k.status == ApiKeyStatus.INACTIVE)
        total_usage = sum(k.usage_count for k in self._api_keys.values())

        users_with_keys = len(self._api_keys_by_user)

        return {
            "total_keys": total_keys,
            "active_keys": active_keys,
            "revoked_keys": revoked_keys,
            "inactive_keys": inactive_keys,
            "total_usage": total_usage,
            "users_with_keys": users_with_keys,
        }
