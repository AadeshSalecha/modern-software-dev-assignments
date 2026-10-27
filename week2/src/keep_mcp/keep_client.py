"""The real Google Keep client (httpx) and the protocol the server codes against.

The server never talks to httpx directly: it depends on the :class:`KeepApi`
protocol, so tests can inject an in-memory implementation and exercise the same
tool code paths (see ``fake_client.py``).
"""

from __future__ import annotations

import logging
from typing import Any, Protocol, runtime_checkable

import httpx

from .config import KEEP_BASE_URL
from .errors import ToolFailure, from_http, transient

logger = logging.getLogger(__name__)

JSON = dict[str, Any]


@runtime_checkable
class KeepApi(Protocol):
    """The slice of ``keep.googleapis.com/v1`` this server uses."""

    async def list_notes(
        self,
        *,
        page_size: int = 100,
        page_token: str | None = None,
        filter: str | None = None,
    ) -> JSON:
        """``notes.list``. Returns ``{}`` when nothing matches."""
        ...

    async def get_note(self, name: str) -> JSON:
        """``notes.get``. Returns the raw ``Note``."""
        ...

    async def create_note(self, payload: JSON) -> JSON:
        """``notes.create`` with ``{"title", "body"}``."""
        ...

    async def delete_note(self, name: str) -> JSON:
        """``notes.delete`` (permanent)."""
        ...

    async def create_permissions(self, name: str, emails: list[str]) -> JSON:
        """``permissions.batchCreate`` with role ``WRITER`` for every address."""
        ...

    async def aclose(self) -> None:
        """Release network resources."""
        ...


def _safe_json(response: httpx.Response) -> JSON:
    try:
        payload = response.json()
    except ValueError:
        return {}
    return payload if isinstance(payload, dict) else {"data": payload}


def _retry_after(response: httpx.Response) -> int | None:
    raw = response.headers.get("Retry-After")
    if not raw:
        return None
    try:
        return int(float(raw.strip()))
    except ValueError:
        return None


class HttpKeepClient:
    """``KeepApi`` over HTTP, using a token provider for every request.

    Every transport failure is converted into a :class:`ToolFailure` with a
    taxonomy entry (``rate_limited`` / ``transient`` / ``input`` / ``not_found``
    / ``auth_setup``), so no exception ever escapes a tool.
    """

    def __init__(
        self,
        token_provider: Any,
        *,
        base_url: str = KEEP_BASE_URL,
        timeout: float = 30.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._token_provider = token_provider
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._transport = transport
        self._client: httpx.AsyncClient | None = None

    async def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self._timeout, transport=self._transport)
        return self._client

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        payload: JSON | None = None,
        context: str = "keep",
    ) -> JSON:
        token = await self._token_provider.keep_access_token()
        url = f"{self._base_url}/{path.lstrip('/')}"
        client = await self._http()
        try:
            response = await client.request(
                method,
                url,
                params=params,
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
            )
        except httpx.TimeoutException:
            raise ToolFailure(
                transient(f"the Keep API did not answer within {self._timeout:g}s (request timed out)")
            ) from None
        except httpx.HTTPError as exc:
            raise ToolFailure(
                transient(f"could not reach the Keep API ({type(exc).__name__}: {exc})")
            ) from None

        if response.status_code >= 400:
            body = _safe_json(response)
            logger.debug("keep %s %s -> %s", method, url, response.status_code)
            raise ToolFailure(
                from_http(
                    response.status_code,
                    body,
                    context=context,  # type: ignore[arg-type]
                    retry_after=_retry_after(response),
                )
            )
        return _safe_json(response)

    async def list_notes(
        self,
        *,
        page_size: int = 100,
        page_token: str | None = None,
        filter: str | None = None,
    ) -> JSON:
        params: dict[str, Any] = {"pageSize": page_size}
        if filter:
            params["filter"] = filter
        if page_token:
            params["pageToken"] = page_token
        return await self._request("GET", "notes", params=params)

    async def get_note(self, name: str) -> JSON:
        return await self._request("GET", name, context="note")

    async def create_note(self, payload: JSON) -> JSON:
        return await self._request("POST", "notes", payload=payload)

    async def delete_note(self, name: str) -> JSON:
        return await self._request("DELETE", name, context="note")

    async def create_permissions(self, name: str, emails: list[str]) -> JSON:
        payload = {"requests": [{"permission": {"email": email, "role": "WRITER"}} for email in emails]}
        return await self._request("POST", f"{name}/permissions:batchCreate", payload=payload, context="note")
