from __future__ import annotations

# app/services/auth/service.py: 提供最小内部账号校验、密码哈希和 HS256 JWT 签发/校验。

import base64
import hashlib
import hmac
import json
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from pydantic import ValidationError

from app.services.auth.models import AuthenticatedUser, InternalUser
from app.core.config import Settings


class AuthConfigurationError(RuntimeError):
    """鉴权配置缺失或不可解析。"""


class InvalidCredentialsError(RuntimeError):
    """用户名或密码无效。"""


class TokenValidationError(RuntimeError):
    """JWT 无效、过期或对应账号不可用。"""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True, slots=True)
class IssuedToken:
    access_token: str
    expires_at: datetime

    @property
    def expires_in_seconds(self) -> int:
        return max(0, int((self.expires_at - _utc_now()).total_seconds()))


def hash_password(password: str, *, salt: str | None = None, iterations: int = 260_000) -> str:
    """生成可放入内部账号 JSON 文件的 PBKDF2-SHA256 密码哈希。"""

    if not password:
        raise ValueError("password 不能为空。")
    resolved_salt = salt or secrets.token_urlsafe(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        resolved_salt.encode("utf-8"),
        iterations,
    )
    return f"pbkdf2_sha256${iterations}${resolved_salt}${_b64url_encode(digest)}"


def verify_password(password: str, password_hash: str) -> bool:
    """校验 PBKDF2-SHA256 密码哈希。"""

    try:
        scheme, iterations_text, salt, expected_digest = password_hash.split("$", 3)
        iterations = int(iterations_text)
    except ValueError:
        return False
    if scheme != "pbkdf2_sha256" or iterations <= 0:
        return False
    actual_hash = hash_password(password, salt=salt, iterations=iterations)
    actual_digest = actual_hash.rsplit("$", 1)[-1]
    return hmac.compare_digest(actual_digest, expected_digest)


class AuthService:
    """基于配置加载内部账号，并用 HS256 JWT 表达登录态。"""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._users_by_username = self._load_users_by_username(*self._read_users_config())
        self._users_by_id = {item.id: item for item in self._users_by_username.values()}

    def authenticate(self, username: str, password: str) -> AuthenticatedUser:
        """校验用户名密码，成功后返回不含密码哈希的用户上下文。"""

        self._ensure_auth_configured()
        normalized_username = _normalize_username(username)
        user = self._users_by_username.get(normalized_username)
        if user is None or user.status != "active" or not verify_password(password, user.password_hash):
            raise InvalidCredentialsError("用户名或密码错误。")
        return self._to_authenticated_user(user)

    def issue_access_token(self, user: AuthenticatedUser) -> IssuedToken:
        """为已认证用户签发短期访问 token。"""

        secret = self._require_jwt_secret()
        issued_at = _utc_now()
        expires_at = issued_at + timedelta(minutes=self.settings.auth_access_token_expire_minutes)
        payload = {
            "sub": user.id,
            "username": user.username,
            "role": user.role,
            "tenant_id": user.tenant_id,
            "company_id": user.company_id,
            "iat": int(issued_at.timestamp()),
            "exp": int(expires_at.timestamp()),
        }
        return IssuedToken(
            access_token=self._encode_jwt(payload, secret),
            expires_at=expires_at,
        )

    def authenticate_bearer_token(self, token: str) -> AuthenticatedUser:
        """校验 Bearer token，并确认对应账号仍可用。"""

        payload = self._decode_jwt(token)
        user_id = str(payload.get("sub") or "")
        user = self._users_by_id.get(user_id)
        if user is None or user.status != "active":
            raise TokenValidationError("invalid_token", "token 对应账号不存在或已禁用。")
        return self._to_authenticated_user(user)

    def _ensure_auth_configured(self) -> None:
        self._require_jwt_secret()
        if not self._users_by_username:
            raise AuthConfigurationError(
                "AUTH_INTERNAL_USERS_FILE/AUTH_INTERNAL_USERS_JSON 未配置，内部账号登录不可用。"
            )

    def _require_jwt_secret(self) -> str:
        secret = self.settings.auth_jwt_secret_key.strip()
        if not secret:
            raise AuthConfigurationError("AUTH_JWT_SECRET_KEY 未配置，JWT 鉴权不可用。")
        return secret

    def _encode_jwt(self, payload: dict[str, Any], secret: str) -> str:
        header = {"alg": self.settings.auth_jwt_algorithm, "typ": "JWT"}
        encoded_header = _b64url_encode(json.dumps(header, separators=(",", ":"), sort_keys=True).encode("utf-8"))
        encoded_payload = _b64url_encode(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
        signing_input = f"{encoded_header}.{encoded_payload}"
        signature = hmac.new(secret.encode("utf-8"), signing_input.encode("ascii"), hashlib.sha256).digest()
        return f"{signing_input}.{_b64url_encode(signature)}"

    def _decode_jwt(self, token: str) -> dict[str, Any]:
        secret = self._require_jwt_secret()
        try:
            encoded_header, encoded_payload, encoded_signature = token.split(".", 2)
        except ValueError as exc:
            raise TokenValidationError("invalid_token", "token 格式无效。") from exc
        signing_input = f"{encoded_header}.{encoded_payload}"
        expected_signature = _b64url_encode(
            hmac.new(secret.encode("utf-8"), signing_input.encode("ascii"), hashlib.sha256).digest()
        )
        if not hmac.compare_digest(encoded_signature, expected_signature):
            raise TokenValidationError("invalid_token", "token 签名无效。")
        try:
            header = json.loads(_b64url_decode(encoded_header))
            payload = json.loads(_b64url_decode(encoded_payload))
        except (ValueError, json.JSONDecodeError) as exc:
            raise TokenValidationError("invalid_token", "token 内容无效。") from exc
        if header.get("alg") != self.settings.auth_jwt_algorithm:
            raise TokenValidationError("invalid_token", "token 签名算法无效。")
        expires_at = payload.get("exp")
        if not isinstance(expires_at, int):
            raise TokenValidationError("invalid_token", "token 缺少过期时间。")
        if expires_at <= int(_utc_now().timestamp()):
            raise TokenValidationError("token_expired", "token 已过期。")
        return payload

    def _read_users_config(self) -> tuple[str, str]:
        """从 Settings 读取内部账号 JSON 文本，并把文件读取错误转成鉴权配置错误。"""

        try:
            return self.settings.read_auth_internal_users_json(), self.settings.auth_internal_users_source_label
        except OSError as exc:
            raise AuthConfigurationError(f"AUTH_INTERNAL_USERS_FILE 无法读取: {self.settings.auth_internal_users_file}") from exc

    def _load_users_by_username(self, raw_users_json: str, source_label: str) -> dict[str, InternalUser]:
        """解析内部账号 JSON，并按标准化用户名建立索引。"""

        raw_text = raw_users_json.strip()
        if not raw_text:
            return {}
        try:
            decoded = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            raise AuthConfigurationError(f"{source_label} 不是合法 JSON。") from exc
        raw_users = decoded.get("users") if isinstance(decoded, dict) else decoded
        if not isinstance(raw_users, list):
            raise AuthConfigurationError(f"{source_label} 必须是用户数组或包含 users 数组。")
        users_by_username: dict[str, InternalUser] = {}
        for raw_user in raw_users:
            try:
                user = InternalUser.model_validate(raw_user)
            except ValidationError as exc:
                raise AuthConfigurationError(f"{source_label} 用户配置无效: {exc}") from exc
            username_key = _normalize_username(user.username)
            if username_key in users_by_username:
                raise AuthConfigurationError(f"{source_label} 用户名重复: {user.username}")
            users_by_username[username_key] = user
        return users_by_username

    def _to_authenticated_user(self, user: InternalUser) -> AuthenticatedUser:
        return AuthenticatedUser(
            id=user.id,
            username=user.username,
            role=user.role,
            tenant_id=user.tenant_id,
            company_id=user.company_id,
            display_name=user.display_name,
        )


def _normalize_username(username: str) -> str:
    return username.strip().lower()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(f"{data}{padding}".encode("ascii"))
