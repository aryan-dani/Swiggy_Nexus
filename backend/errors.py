"""NexusError hierarchy — typed exceptions for the backend.

Raise these from tool handlers and the orchestrator.
Each can be converted to an SSE event payload via ``to_sse_event()``.
"""

from __future__ import annotations

from typing import Any


class NexusError(Exception):
    """Base class for all Nexus backend errors."""

    code: str = "NEXUS_ERROR"
    http_status: int = 500

    def __init__(self, message: str, *, detail: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.detail = detail or {}

    def to_sse_event(self) -> dict[str, Any]:
        return {
            "type": "error",
            "payload": {
                "code": self.code,
                "message": self.message,
                **self.detail,
            },
        }

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, **self.detail}


class ValidationError(NexusError):
    """Missing or malformed request parameters."""

    code = "VALIDATION_ERROR"
    http_status = 400


class NotFoundError(NexusError):
    """Resource (restaurant, order, booking) not found."""

    code = "NOT_FOUND"
    http_status = 404


class CartError(NexusError):
    """Cart-related errors: empty cart, expired cart, minimum-order not met."""

    code = "CART_ERROR"
    http_status = 422


class CartExpiredError(CartError):
    code = "CART_EXPIRED"


class MinimumOrderError(CartError):
    code = "MIN_ORDER_NOT_MET"


class CartCapExceededError(CartError):
    """Cart exceeds the ₹1000 beta cap."""

    code = "CART_CAP_EXCEEDED"


class SlotUnavailableError(NexusError):
    """Requested Dineout slot is no longer available."""

    code = "SLOT_UNAVAILABLE"
    http_status = 409


class CouponError(NexusError):
    """Coupon validation failures."""

    code = "COUPON_ERROR"
    http_status = 422


class LLMError(NexusError):
    """Errors originating from the LLM provider."""

    code = "LLM_ERROR"
    http_status = 502


class ToolCallError(NexusError):
    """Error returned by a mock MCP tool call."""

    code = "TOOL_ERROR"
    http_status = 500

    def __init__(self, tool: str, payload: dict[str, Any]) -> None:
        super().__init__(f"Tool '{tool}' failed: {payload.get('message', 'unknown')}", detail=payload)
        self.tool = tool

    def to_sse_event(self) -> dict[str, Any]:
        return {
            "type": "error",
            "payload": {
                "code": self.code,
                "tool": self.tool,
                "message": self.message,
                **self.detail,
            },
        }


class MaxIterationsError(LLMError):
    """LLM agentic loop hit the max-rounds limit."""

    code = "MAX_ITERATIONS_EXCEEDED"

    def __init__(self, rounds: int) -> None:
        super().__init__(
            f"Agent reached the maximum of {rounds} tool-call rounds. "
            "Returning partial results."
        )
        self.rounds = rounds
