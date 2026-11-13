"""WebSocket channels (contract section 4).

Auth: ?token=<access_token> query param (browsers cannot set WS headers).
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import joinedload

from app.core.security import decode_token
from app.db.session import SessionLocal
from app.models.drivers import Driver
from app.models.identity import (
    RESTAURANT_ROLES,
    ROLE_ADMIN,
    ROLE_DISPATCHER,
    User,
    UserRole,
)
from app.models.orders import Order
from app.services.websocket import manager

router = APIRouter(prefix="/ws", tags=["websocket"])


def _user_from_token(token: str | None) -> User | None:
    if not token:
        return None
    payload = decode_token(token)
    if payload is None or payload.get("type") != "access":
        return None
    db = SessionLocal()
    try:
        return (
            db.query(User)
            .options(joinedload(User.roles).joinedload(UserRole.role))
            .filter(User.id == int(payload["sub"]))
            .first()
        )
    finally:
        db.close()


async def _reject(websocket: WebSocket, code: int = 4401):
    await websocket.close(code=code)


@router.websocket("/orders/{order_id}")
async def order_channel(websocket: WebSocket, order_id: int, token: str | None = None):
    user = _user_from_token(token)
    if user is None:
        await _reject(websocket)
        return
    db = SessionLocal()
    try:
        order = db.query(Order).filter(Order.id == order_id).first()
        if order is None:
            await _reject(websocket, 4404)
            return
        allowed = (
            user.has_role(ROLE_ADMIN)
            or (order.customer is not None and order.customer.user_id == user.id)
            or user.has_role(*RESTAURANT_ROLES, scope_id=order.restaurant_id)
        )
        if not allowed:
            await _reject(websocket, 4403)
            return
    finally:
        db.close()
    channel = manager.order_channel(order_id)
    await manager.connect(channel, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await manager.disconnect(channel, websocket)


@router.websocket("/driver/{driver_id}")
async def driver_channel(websocket: WebSocket, driver_id: int, token: str | None = None):
    user = _user_from_token(token)
    if user is None:
        await _reject(websocket)
        return
    db = SessionLocal()
    try:
        driver = db.query(Driver).filter(Driver.id == driver_id).first()
        if driver is None or driver.user_id != user.id:
            await _reject(websocket, 4403)
            return
    finally:
        db.close()
    channel = manager.driver_channel(driver_id)
    await manager.connect(channel, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await manager.disconnect(channel, websocket)


@router.websocket("/dispatch")
async def dispatch_channel(websocket: WebSocket, token: str | None = None):
    user = _user_from_token(token)
    if user is None:
        await _reject(websocket)
        return
    if not user.has_role(ROLE_DISPATCHER, ROLE_ADMIN):
        await _reject(websocket, 4403)
        return
    channel = manager.DISPATCH_CHANNEL
    await manager.connect(channel, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await manager.disconnect(channel, websocket)


@router.websocket("/restaurant/{restaurant_id}")
async def restaurant_channel(
    websocket: WebSocket, restaurant_id: int, token: str | None = None
):
    user = _user_from_token(token)
    if user is None:
        await _reject(websocket)
        return
    if not (
        user.has_role(ROLE_ADMIN)
        or user.has_role(*RESTAURANT_ROLES, scope_id=restaurant_id)
    ):
        await _reject(websocket, 4403)
        return
    channel = manager.restaurant_channel(restaurant_id)
    await manager.connect(channel, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await manager.disconnect(channel, websocket)
