"""Read selected Gmail labels using an operator-managed access token."""

import base64
import os
from urllib.parse import quote, urlencode
from urllib.request import Request, build_opener
from urllib.error import HTTPError

from ..errors import BrainError, require
from ..extraction import NoRedirect
from ..util import loads

BASE = "https://gmail.googleapis.com/gmail/v1/users/me/messages"


def plain_parts(payload):
    result = []
    if payload.get("mimeType") == "text/plain" and payload.get("body", {}).get("data"):
        value = payload["body"]["data"]
        result.append(base64.urlsafe_b64decode(value + "=" * (-len(value) % 4)).decode("utf-8", errors="replace"))
    for part in payload.get("parts", []):
        result.extend(plain_parts(part))
    return result


def scan(config, fetch=None):
    """Full bounded reconciliation. Token refresh/OAuth UI are outside this adapter."""
    token = os.environ.get(config["token_env"], "")
    require(bool(token), "gmail_credential", "The configured Gmail token environment variable is empty.")

    def request(url):
        try:
            with build_opener(NoRedirect()).open(Request(url, headers={"Authorization": "Bearer " + token}), timeout=25) as response:
                data = response.read(2_000_001)
            require(len(data) <= 2_000_000, "gmail_limit", "Gmail response is too large.")
            return loads(data)
        except HTTPError as error:
            raise BrainError("gmail_authorization" if error.code in {401, 403} else "gmail_provider",
                             "Gmail authorization or provider request failed.", 502) from None
        except BrainError:
            raise
        except Exception:
            raise BrainError("gmail_provider", "Gmail request failed.", 502) from None

    fetch = fetch or request
    messages, page = [], None
    while True:
        params = [("maxResults", "100")] + [("labelIds", value) for value in config["label_ids"]]
        if page:
            params.append(("pageToken", page))
        response = fetch(BASE + "?" + urlencode(params))
        messages.extend(response.get("messages", []))
        require(len(messages) <= 500, "gmail_limit", "Selected labels exceed 500 messages. Narrow the binding before syncing.")
        next_page = response.get("nextPageToken")
        if not next_page:
            break
        require(next_page != page, "gmail_pagination", "Gmail pagination did not advance.")
        page = next_page
    result = []
    for summary in messages:
        item = fetch(BASE + "/" + quote(summary["id"], safe="") + "?format=full")
        payload = item.get("payload", {})
        headers = {h["name"].casefold(): h["value"] for h in payload.get("headers", [])}
        parts = plain_parts(payload)
        content = "\n".join(["Subject: " + headers.get("subject", "(no subject)"),
                             "From: " + headers.get("from", "unknown"),
                             "Date: " + headers.get("date", "unknown"), "\n".join(parts) or item.get("snippet", "")])
        require(len(content) <= 200_000, "gmail_limit", "A message exceeds the supported text limit.")
        result.append({"external_id": item["id"], "title": headers.get("subject", "Gmail message")[:200],
                       "content": content, "mime": "text/plain"})
    return result
