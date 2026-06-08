# HTTPS Support Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Serve the existing photo monitor application over HTTPS for `yuelansuodao.cn`.

**Architecture:** Terminate TLS in the frontend Nginx container. Keep the backend on internal HTTP at `photo-backend:8000`, and continue proxying API and WebSocket traffic through the frontend container.

**Tech Stack:** Docker Compose, Nginx, Vite static frontend, FastAPI backend.

---

### Task 1: Nginx TLS Configuration

**Files:**
- Modify: `photo-monitor/nginx.conf`

- [ ] **Step 1: Replace the single HTTP server with HTTP redirect plus HTTPS server**

Configure port `80` to redirect all requests to HTTPS. Configure port `443` with the mounted certificate pair:

```nginx
server {
  listen 80;
  server_name yuelansuodao.cn www.yuelansuodao.cn;
  return 301 https://$host$request_uri;
}

server {
  listen 443 ssl;
  server_name yuelansuodao.cn www.yuelansuodao.cn;
  client_max_body_size 200m;

  ssl_certificate /etc/nginx/certs/fullchain.pem;
  ssl_certificate_key /etc/nginx/certs/privkey.pem;
  ssl_protocols TLSv1.2 TLSv1.3;
  ssl_prefer_server_ciphers off;

  root /usr/share/nginx/html;
  index index.html;

  # Existing proxy and static locations remain inside this HTTPS server.
}
```

- [ ] **Step 2: Preserve backend proxy headers**

Keep `X-Forwarded-Proto $scheme` on every proxied API and WebSocket location so the backend can see the original scheme if future backend logic needs it.

- [ ] **Step 3: Preserve WebSocket upgrade support**

Keep the existing `/ws` block with `proxy_http_version 1.1`, `Upgrade`, and `Connection "upgrade"` headers. The frontend code already chooses `wss:` when loaded over HTTPS.

### Task 2: Docker Runtime Configuration

**Files:**
- Modify: `docker-compose.yml`
- Modify: `docker-compose.frontend.yml`
- Modify: `photo-monitor/Dockerfile`

- [ ] **Step 1: Expose HTTPS in Compose**

Add `443:443` to the frontend service while keeping `80:80`.

- [ ] **Step 2: Mount the certificate directory read-only**

Mount the local Nginx-compatible certificate folder into the frontend container:

```yaml
volumes:
  - ./certs/yuelansuodao.cn:/etc/nginx/certs:ro
```

- [ ] **Step 3: Advertise both ports in the image**

Change `photo-monitor/Dockerfile` from `EXPOSE 80` to:

```dockerfile
EXPOSE 80 443
```

### Task 3: Verification

**Files:**
- No code files.

- [ ] **Step 1: Check Nginx config with the official image**

Run:

```bash
docker run --rm -v "$PWD/photo-monitor/nginx.conf:/etc/nginx/conf.d/default.conf:ro" -v "$PWD/certs/yuelansuodao.cn:/etc/nginx/certs:ro" nginx:1.27-alpine nginx -t
```

Expected output includes:

```text
nginx: configuration file /etc/nginx/nginx.conf test is successful
```

- [ ] **Step 2: Rebuild and start the stack**

Run:

```bash
docker compose up -d --build
```

Expected: both `photo-backend` and `photo-frontend` are running.

- [ ] **Step 3: Smoke test HTTPS**

Open `https://yuelansuodao.cn/`. Confirm the login page loads, API calls return through the same domain, and monitor updates continue through WebSocket.
