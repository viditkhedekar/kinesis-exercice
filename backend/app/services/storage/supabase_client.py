"""A thin client for the Supabase Storage REST API.

Deliberately not the ``supabase`` SDK: we use exactly five operations (upload,
download, exists, delete, sign) and the SDK would drag auth/postgrest/realtime
into the Render image for no benefit. This mirrors how ``services/email`` talks
to Resend/SendGrid directly.

Authentication is the **service-role key**, which bypasses row-level security.
It is server-side only and must never reach the browser — the backend hands out
short-lived signed URLs instead.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import BinaryIO
from urllib.parse import quote

import httpx

logger = logging.getLogger("kinesis.storage")

# Supabase mounts the storage API under this prefix.
_API_PREFIX = "/storage/v1"
# One list page; the API caps this server-side anyway.
_LIST_PAGE = 100


class SupabaseStorageError(RuntimeError):
    """A Supabase Storage call failed."""


class ObjectNotFound(SupabaseStorageError):
    """The requested object does not exist in the bucket."""


def _encode(key: str) -> str:
    """Percent-encode a key for use as a URL path, keeping the separators."""
    return quote(key, safe="/")


class SupabaseStorageClient:
    """Minimal REST wrapper around one Supabase Storage bucket."""

    def __init__(
        self,
        url: str,
        service_role_key: str,
        bucket: str,
        *,
        timeout: float = 120.0,
        client: httpx.Client | None = None,
    ) -> None:
        if not url or not service_role_key:
            raise SupabaseStorageError(
                "Supabase storage is not configured: set SUPABASE_URL and "
                "SUPABASE_SERVICE_ROLE_KEY."
            )
        self.base_url = url.rstrip("/")
        self.bucket = bucket
        self._key = service_role_key
        self._client = client or httpx.Client(
            base_url=f"{self.base_url}{_API_PREFIX}",
            headers={
                "Authorization": f"Bearer {service_role_key}",
                "apikey": service_role_key,
            },
            timeout=timeout,
            follow_redirects=True,
        )

    # --- internals ---------------------------------------------------------

    def _raise(self, resp: httpx.Response, action: str, key: str) -> None:
        # Never log the body verbatim at error level — it can echo request headers.
        raise SupabaseStorageError(
            f"Supabase storage {action} failed for '{key}' "
            f"(HTTP {resp.status_code}): {resp.text[:300]}"
        )

    def close(self) -> None:
        self._client.close()

    # --- objects -----------------------------------------------------------

    def upload(
        self, key: str, fileobj: BinaryIO, *, content_type: str | None = None
    ) -> None:
        """Upload (or overwrite) an object, streaming from ``fileobj``."""
        headers = {
            "x-upsert": "true",
            "content-type": content_type or "application/octet-stream",
        }
        resp = self._client.post(
            f"/object/{self.bucket}/{_encode(key)}", content=fileobj, headers=headers
        )
        if resp.status_code >= 400:
            self._raise(resp, "upload", key)

    def upload_file(
        self, key: str, local_path: str | Path, *, content_type: str | None = None
    ) -> None:
        with open(local_path, "rb") as fh:
            self.upload(key, fh, content_type=content_type)

    def download(self, key: str) -> bytes:
        resp = self._client.get(f"/object/{self.bucket}/{_encode(key)}")
        if resp.status_code in (400, 404):
            raise ObjectNotFound(f"No such object: {key}")
        if resp.status_code >= 400:
            self._raise(resp, "download", key)
        return resp.content

    def download_to(self, key: str, dest: str | Path) -> None:
        """Stream an object to a local file (used for CV processing temp files)."""
        with self._client.stream("GET", f"/object/{self.bucket}/{_encode(key)}") as resp:
            if resp.status_code in (400, 404):
                raise ObjectNotFound(f"No such object: {key}")
            if resp.status_code >= 400:
                resp.read()
                self._raise(resp, "download", key)
            with open(dest, "wb") as out:
                for chunk in resp.iter_bytes(chunk_size=1024 * 256):
                    out.write(chunk)

    def exists(self, key: str) -> bool:
        """HEAD the object, falling back to a prefix listing on older gateways."""
        resp = self._client.head(f"/object/{self.bucket}/{_encode(key)}")
        if resp.status_code == 200:
            return True
        if resp.status_code in (400, 404):
            return False
        # 405/501 etc: some deployments don't route HEAD — ask the list API instead.
        prefix, _, name = key.rpartition("/")
        return any(entry.get("name") == name for entry in self.list(prefix, search=name))

    def size(self, key: str) -> int | None:
        """Stored byte size, or ``None`` when unknown/missing (used to verify uploads)."""
        prefix, _, name = key.rpartition("/")
        for entry in self.list(prefix, search=name):
            if entry.get("name") == name:
                meta = entry.get("metadata") or {}
                raw = meta.get("size")
                return int(raw) if raw is not None else None
        return None

    def remove(self, keys: list[str]) -> None:
        """Delete objects. Missing objects are a no-op, matching the FS backend."""
        if not keys:
            return
        resp = self._client.request(
            "DELETE", f"/object/{self.bucket}", json={"prefixes": keys}
        )
        if resp.status_code in (400, 404):
            return
        if resp.status_code >= 400:
            self._raise(resp, "delete", ", ".join(keys[:3]))

    def list(self, prefix: str, *, search: str | None = None) -> list[dict]:
        """One level of a prefix. Folders come back with ``id`` set to ``None``."""
        out: list[dict] = []
        offset = 0
        while True:
            body: dict = {"prefix": prefix, "limit": _LIST_PAGE, "offset": offset}
            if search:
                body["search"] = search
            resp = self._client.post(f"/object/list/{self.bucket}", json=body)
            if resp.status_code >= 400:
                self._raise(resp, "list", prefix)
            page = resp.json()
            if not isinstance(page, list) or not page:
                break
            out.extend(page)
            if len(page) < _LIST_PAGE:
                break
            offset += _LIST_PAGE
        return out

    def list_recursive(self, prefix: str) -> list[str]:
        """Every object key under ``prefix``, descending into pseudo-folders."""
        keys: list[str] = []
        base = prefix.rstrip("/")
        for entry in self.list(base):
            name = entry.get("name")
            if not name:
                continue
            child = f"{base}/{name}" if base else name
            if entry.get("id") is None:  # folder placeholder
                keys.extend(self.list_recursive(child))
            else:
                keys.append(child)
        return keys

    def create_signed_url(self, key: str, expires_in: int) -> str:
        """A time-limited public URL for one object. Never persisted — it expires."""
        resp = self._client.post(
            f"/object/sign/{self.bucket}/{_encode(key)}", json={"expiresIn": int(expires_in)}
        )
        if resp.status_code in (400, 404):
            raise ObjectNotFound(f"No such object: {key}")
        if resp.status_code >= 400:
            self._raise(resp, "sign", key)
        signed = (resp.json() or {}).get("signedURL") or (resp.json() or {}).get("signedUrl")
        if not signed:
            raise SupabaseStorageError(f"Supabase returned no signed URL for '{key}'")
        if signed.startswith("http://") or signed.startswith("https://"):
            return signed
        return f"{self.base_url}{_API_PREFIX}/{signed.lstrip('/')}"

    # --- bucket ------------------------------------------------------------

    def ensure_bucket(self, *, public: bool = False) -> bool:
        """Create the bucket if missing. Returns True when it was created.

        Private by default: objects are reachable only via the service-role key
        (server-side) or a signed URL the backend issues after an auth check.
        """
        resp = self._client.get(f"/bucket/{self.bucket}")
        if resp.status_code == 200:
            return False
        created = self._client.post(
            "/bucket", json={"id": self.bucket, "name": self.bucket, "public": public}
        )
        if created.status_code == 409:
            return False
        if created.status_code >= 400:
            self._raise(created, "create bucket", self.bucket)
        return True
