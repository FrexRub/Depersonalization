from __future__ import annotations

import secrets

from fastapi import Header, HTTPException, status


class BearerTokenVerifier:
    def __init__(self, expected_token: str | None) -> None:
        self._expected_token = expected_token

    async def __call__(self, authorization: str | None = Header(default=None)) -> None:
        if self._expected_token is None:
            return
        scheme, separator, token = (authorization or "").partition(" ")
        valid_scheme = separator == " " and scheme.lower() == "bearer"
        valid_token = secrets.compare_digest(token, self._expected_token)
        if not (valid_scheme and valid_token):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unauthorized",
                headers={"WWW-Authenticate": "Bearer"},
            )

