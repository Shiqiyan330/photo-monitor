from fastapi import APIRouter, WebSocket
from core.connection_manager import ConnectionManager
from services.auth_service import employee_system, user_has_any_matrix_permission

router = APIRouter()
manager = ConnectionManager()

@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    token = ws.query_params.get("token")
    user = employee_system.get_user_by_token(token)

    public_user = user.to_public_dict() if user else None
    if not public_user or (public_user["role"] != "admin" and not user_has_any_matrix_permission(public_user, "photos", {"read"})):
        await ws.close(code=1008)
        return

    await manager.connect(ws)
    try:
        while True:
            await ws.receive_text()
    except:
        manager.disconnect(ws)
