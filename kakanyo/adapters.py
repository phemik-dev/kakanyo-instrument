"""Explicit provider opt-in. Do not transmit corpora without source-level approval."""
import json
import os
import urllib.error
import urllib.request
from urllib.parse import urlsplit

class ProviderError(RuntimeError):
    pass

def _post(url: str, payload: dict, headers: dict) -> dict:
    parsed = urlsplit(url)
    local = parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1"}
    if not (parsed.scheme == "https" or local):
        raise ProviderError("Provider endpoint must be HTTPS, or localhost HTTP for explicit testing")
    if parsed.username or parsed.password or parsed.fragment:
        raise ProviderError("Credentials and fragments are forbidden in provider endpoint")
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", **headers}, method="POST"
    )
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            raise ProviderError("Provider redirect refused")
    opener = urllib.request.build_opener(NoRedirect)
    try:
        with opener.open(req, timeout=90) as response:
            if response.status != 200:
                raise ProviderError("Provider rejected request")
            data = response.read(2_000_001)
            if len(data) > 2_000_000:
                raise ProviderError("Provider response exceeds size limit")
            result = json.loads(data)
            if not isinstance(result, dict):
                raise ProviderError("Provider response must be a JSON object")
            return result
    except ProviderError:
        raise
    except Exception as exc:
        raise ProviderError("Provider failed; verify endpoint, permission, model and credentials") from exc

class OfflineAdapter:
    """A custody-only smoke adapter; it does not evaluate the evidence."""
    local_only = True
    def invoke(self, prompt: str) -> dict:
        return {"claims": [], "contradictions": [],
                "newly_open": ["OFFLINE: no substantive analysis performed"],
                "weakened_claims": [],
                "next_pressure_tests": ["Use an authorised model and independent review"],
                "self_limitations": ["Custody/CLI smoke test only; not an epistemic result"]}

class OpenAICompatibleAdapter:
    """Works with Chat Completions-shaped endpoints; not tested against every provider."""
    def __init__(self, endpoint: str, model: str, key_env="KAKANYO_API_KEY"):
        self.endpoint, self.model, self.key_env = endpoint, model, key_env
    def invoke(self, prompt: str) -> dict:
        token = os.environ.get(self.key_env)
        if not token:
            raise ProviderError(f"Missing environment credential {self.key_env}")
        reply = _post(self.endpoint,
            {"model": self.model, "temperature": 0,
             "messages": [
                 {"role": "system", "content": "Research the supplied evidence only. Return a single JSON object; no unsupported claims."},
                 {"role": "user", "content": prompt}]},
            {"Authorization": "Bearer " + token})
        try:
            content = reply["choices"][0]["message"]["content"]
            if isinstance(content, list):
                content = "".join(part.get("text", "") for part in content if part.get("type") == "text")
            obj = json.loads(content)
            if not isinstance(obj, dict):
                raise ValueError("output not object")
            return obj
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise ProviderError("Model produced invalid instrument JSON") from exc

class ClaudeMessagesAdapter:
    def __init__(self, model: str, key_env="KAKANYO_ANTHROPIC_KEY"):
        self.model, self.key_env = model, key_env
    def invoke(self, prompt: str) -> dict:
        token = os.environ.get(self.key_env)
        if not token:
            raise ProviderError(f"Missing environment credential {self.key_env}")
        reply = _post("https://api.anthropic.com/v1/messages",
            {"model": self.model, "max_tokens": 4096, "temperature": 0,
             "messages": [{"role": "user", "content": prompt}]},
            {"x-api-key": token, "anthropic-version": "2023-06-01"})
        try:
            raw = "".join(b["text"] for b in reply["content"] if b.get("type") == "text")
            obj = json.loads(raw)
            if not isinstance(obj, dict):
                raise ValueError("output not object")
            return obj
        except (KeyError, TypeError, ValueError) as exc:
            raise ProviderError("Model produced invalid instrument JSON") from exc
