"""FastAPI routes for POST /food, /im, /dineout local mock MCP."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from mcp_server.facade import invoke_vertical


class MCPRequestBody(BaseModel):
    method: str = Field(..., min_length=1)
    params: dict[str, Any] = Field(default_factory=dict)


router = APIRouter(tags=["mock-mcp"])


@router.post("/food")
def post_food_mcp(body: MCPRequestBody) -> dict[str, Any]:
    return invoke_vertical("food", body.method, body.params)


@router.post("/im")
def post_im_mcp(body: MCPRequestBody) -> dict[str, Any]:
    return invoke_vertical("im", body.method, body.params)


@router.post("/dineout")
def post_dineout_mcp(body: MCPRequestBody) -> dict[str, Any]:
    return invoke_vertical("dineout", body.method, body.params)
