"""Explicit controller routing with sanitized attempt receipts."""

import time
from typing import Any
from urllib.parse import urlparse
from google.adk.models.base_llm import BaseLlm
from google.adk.models.lite_llm import LiteLlm
from pydantic import PrivateAttr
from .config import VALUES, CONTROLLER_MODELS as MODELS, CONTROLLER_MAX_TOKENS


def provider_config():
    values = VALUES
    endpoint = values.get(
        "AGENT_PROVIDER_URL", "https://openrouter.ai/api/v1/chat/completions"
    ).rstrip("/")
    parsed = urlparse(endpoint)
    if (
        parsed.scheme != "https"
        or parsed.hostname != "openrouter.ai"
        or parsed.path not in ("/api/v1", "/api/v1/chat/completions")
    ):
        raise ValueError(
            "Only the explicitly requested OpenRouter HTTPS endpoint is allowed"
        )
    key = values.get("AGENT_PROVIDER_API_KEY")
    if not key:
        raise ValueError("AGENT_PROVIDER_API_KEY missing from Orpheus/.env")
    return (endpoint.removesuffix("/chat/completions"), key)


class ControllerModel(BaseLlm):
    model: str = MODELS[0]
    _clients: list = PrivateAttr(default_factory=list)
    _log: Any = PrivateAttr()
    _active: int = PrivateAttr(default=0)

    def __init__(self, log, clients=None):
        super().__init__()
        self._log = log
        if clients is not None:
            self._clients = clients
        else:
            base, key = provider_config()
            self._clients = [
                LiteLlm(
                    model="openrouter/" + name,
                    api_base=base,
                    api_key=key,
                    timeout=180,
                    num_retries=1,
                    max_tokens=CONTROLLER_MAX_TOKENS,
                    extra_body={
                        "reasoning": {"enabled": False},
                        "provider": {"require_parameters": True},
                    },
                )
                for name in MODELS
            ]

    async def generate_content_async(self, llm_request, stream=False):
        for index in range(self._active, len(self._clients)):
            started = time.monotonic()
            self._log("model_attempt", requested_model=MODELS[index])
            try:
                req = llm_request.model_copy(deep=True)
                req.model = "openrouter/" + MODELS[index]
                responses = [
                    r
                    async for r in self._clients[index].generate_content_async(
                        req, stream=False
                    )
                ]
                if (
                    not responses
                    or any((r.error_code for r in responses))
                    or (not any((r.content and r.content.parts for r in responses)))
                ):
                    raise RuntimeError("Unusable provider response")
            except Exception as exc:
                self._log(
                    "model_failed",
                    requested_model=MODELS[index],
                    error_type=type(exc).__name__,
                    status_code=getattr(exc, "status_code", None),
                    routing_diagnostic="No endpoints match requested parameters"
                    if "No endpoints" in str(exc)
                    else "See provider status code",
                    elapsed_s=round(time.monotonic() - started, 3),
                )
                continue
            self._active = index
            for response in responses:
                self._log(
                    "model_response",
                    requested_model=MODELS[index],
                    served_model=response.model_version,
                    elapsed_s=round(time.monotonic() - started, 3),
                    usage=response.usage_metadata.model_dump(
                        mode="json", exclude_none=True
                    )
                    if response.usage_metadata
                    else None,
                )
                yield response
            return
        raise RuntimeError(
            "All approved vision providers failed; see sanitised model_failed events"
        )
