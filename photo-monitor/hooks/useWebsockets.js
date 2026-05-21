import { useEffect, useRef } from "react"

export default function useWebSocket(onMessage) {
  const wsRef = useRef(null)
  const onMessageRef = useRef(onMessage)

  useEffect(() => {
    onMessageRef.current = onMessage
  }, [onMessage])

  useEffect(() => {
    let ws
    let reconnectTimer = 0
    let closed = false

    const connect = () => {
      const protocol = window.location.protocol === "https:" ? "wss:" : "ws:"
      ws = new WebSocket(`${protocol}//${window.location.host}/ws`)
      wsRef.current = ws

      ws.onopen = () => console.log("WS 连接成功")

      ws.onmessage = (event) => {
        const data = JSON.parse(event.data)
        onMessageRef.current(data)
      }

      ws.onclose = () => {
        if (closed) {
          return
        }
        console.log("WS 断开，重连中...")
        reconnectTimer = window.setTimeout(connect, 2000)
      }
    }

    connect()

    return () => {
      closed = true
      window.clearTimeout(reconnectTimer)
      ws?.close()
    }
  }, [])
}
