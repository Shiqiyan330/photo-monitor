// src/hooks/useWebSocket.js
import { useEffect, useRef } from "react"

export default function useWebSocket(onMessage) {
  const wsRef = useRef(null)

  useEffect(() => {
    let ws

    const connect = () => {
      const protocol = window.location.protocol === "https:" ? "wss:" : "ws:"
      ws = new WebSocket(`${protocol}//${window.location.host}/ws`)
      wsRef.current = ws

      ws.onopen = () => console.log("WS连接成功")

      ws.onmessage = (e) => {
        const data = JSON.parse(e.data)
        onMessage(data)
      }

      ws.onclose = () => {
        console.log("WS断开，重连中...")
        setTimeout(connect, 2000) // 自动重连
      }
    }

    connect()

    return () => ws?.close()
  }, [])
}
