from fastapi import APIRouter, WebSocket
from core.connection_manager import ConnectionManager
from services.auth_service import employee_system

router = APIRouter()
manager = ConnectionManager()

@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    token = ws.query_params.get("token")
    user = employee_system.get_user_by_token(token)

    if not user or (user.role != "admin" and "camera" not in user.permissions):
        await ws.close(code=1008)
        return

    await manager.connect(ws)
    try:
        while True:
            await ws.receive_text()
    except:
        manager.disconnect(ws)
