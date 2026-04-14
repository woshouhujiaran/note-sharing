from __future__ import annotations

import base64
import hashlib
import hmac
import json
from dataclasses import dataclass


class AuthError(RuntimeError):
    pass


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def decode_jwt(token: str, secret: str | None = None) -> dict:
    try:
        header_b64, payload_b64, signature_b64 = token.split(".")
    except ValueError as exc:
        raise AuthError("invalid token format") from exc

    try:
        header = json.loads(_b64url_decode(header_b64))
        payload = json.loads(_b64url_decode(payload_b64))
    except Exception as exc:  # noqa: BLE001
        raise AuthError("token payload decode failed") from exc

    if secret:
        if header.get("alg") != "HS256":
            raise AuthError("unsupported token algorithm")

        signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
        expected_signature = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
        actual_signature = _b64url_decode(signature_b64)

        if not hmac.compare_digest(expected_signature, actual_signature):
            raise AuthError("token signature mismatch")

    return payload


@dataclass(slots=True)
class AuthUser:
    user_id: str | None
    username: str | None
    role: str | None


def extract_user_from_authorization(authorization: str | None, secret: str | None = None) -> AuthUser:
    if not authorization or not authorization.startswith("Bearer "):
        raise AuthError("missing bearer token")

    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise AuthError("missing token")

    payload = decode_jwt(token, secret)
    return AuthUser(
        user_id=str(payload.get("userId") or payload.get("id") or ""),
        username=payload.get("sub") or payload.get("username"),
        role=payload.get("role"),
    )
