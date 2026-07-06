"""Runtime order/booking store for track_* and get_booking_status mocks."""

from __future__ import annotations

from typing import Any

_food_orders: dict[str, dict[str, Any]] = {}
_im_orders: dict[str, dict[str, Any]] = {}
_bookings: dict[str, dict[str, Any]] = {}


def save_food_order(order: dict[str, Any]) -> None:
    oid = str(order.get("orderId") or order.get("order_id", ""))
    if oid:
        _food_orders[oid] = order


def save_im_order(order: dict[str, Any]) -> None:
    oid = str(order.get("orderId") or order.get("order_id", ""))
    if oid:
        _im_orders[oid] = order


def save_booking(booking: dict[str, Any]) -> None:
    bid = str(booking.get("bookingId") or booking.get("booking_id", ""))
    if bid:
        _bookings[bid] = booking


def get_food_order(order_id: str) -> dict[str, Any] | None:
    return _food_orders.get(order_id)


def get_im_order(order_id: str) -> dict[str, Any] | None:
    return _im_orders.get(order_id)


def get_booking(booking_id: str) -> dict[str, Any] | None:
    return _bookings.get(booking_id)


def list_food_orders() -> list[dict[str, Any]]:
    return list(_food_orders.values())


def list_im_orders() -> list[dict[str, Any]]:
    return list(_im_orders.values())
