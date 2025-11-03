# Deployment Guide

Clepsy is intended for a single self-hosted user. Start by deciding how you want to reach your instance:

- **Private tunnel (recommended):** keep the backend off the public internet and expose it with a secure tunnel such as Tailscale Serve/Funnel or Cloudflare Tunnel.
- **Public domain with Caddy:** run behind a reverse proxy that terminates TLS on your own domain and is reachable from anywhere.

Pick the option that fits your environment, then follow the matching steps below.

## Private Access via Secure Tunnel

### Prerequisites
- Docker Engine and Docker Compose on the host
- Either [Tailscale](https://tailscale.com/download) or [Cloudflare Tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/) installed and authenticated on the same host

### 1. Prepare the directory
```bash
mkdir clepsy && cd clepsy
curl -fsSLo docker-compose.yml https://raw.githubusercontent.com/SamGalanakis/clepsy/main/docker-compose.prod.yml
echo "CLEPSY_PORT=8000" > .env    # adjust if you need a different port
```
Clepsy generates the bootstrap password automatically and stores it in the persistent volume. Update the value in `.env` if you want Clepsy to bind to a different host port.

### 2. Start the backend
```bash
docker compose up -d
```
The Clepsy API now listens on port `8000` inside the container and is reachable from the host network.

### 3. Expose the service through your tunnel
- **Tailscale Serve / Funnel:** follow [Tailscale Serve](https://tailscale.com/kb/1312/serve) for private tailnet access or [Tailscale Funnel](https://tailscale.com/kb/1223/funnel/) for a public `ts.net` URL. Point the origin at `http://127.0.0.1:<port>` using the same port you set via `CLEPSY_PORT` (default `8000`).
- **Cloudflare Tunnel:** use the [Cloudflare Tunnel quick start](https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/tunnel-guide/local/) to run `cloudflared` on the host and map the tunnel to `http://localhost:<port>` with that same value.


### 4. First sign-in
Visit the URL provided by your tunnel and sign in using the generated bootstrap password.
Get the bootstrap password by running:
```bash
docker compose cp clepsy:/var/lib/clepsy/bootstrap_password.txt - | tar -xO
```
Rotate the password from the Clepsy UI immediately after login.


## Public Domain Deployment with Caddy

Choose this path when you want a public domain with certificates from Let's Encrypt.

### Additional prerequisites
- A DNS A/AAAA record (for example `clepsy.example.com`) pointing to the host
- Ports **80** and **443** reachable from the internet

### 1. Fetch the compose files
```bash
mkdir clepsy && cd clepsy
curl -fsSLo docker-compose.prod.yml https://raw.githubusercontent.com/SamGalanakis/clepsy/main/docker-compose.prod.yml
curl -fsSLo docker-compose.prod.gateway.yml https://raw.githubusercontent.com/SamGalanakis/clepsy/main/docker-compose.prod.gateway.yml
curl -fsSLo Caddyfile https://raw.githubusercontent.com/SamGalanakis/clepsy/main/Caddyfile
echo "DOMAIN=clepsy.example.com" > .env
echo "CLEPSY_PORT=8000" >> .env
```

### 2. Launch Clepsy with Caddy
```bash
docker compose -f docker-compose.prod.yml -f docker-compose.prod.gateway.yml up -d
```
Caddy requests certificates for `DOMAIN` and `www.DOMAIN` and proxies traffic to the Clepsy backend. Watch issuance progress with:
```bash
docker compose logs -f caddy
```
Open `https://$DOMAIN/` and log in using the password stored at `/var/lib/clepsy/bootstrap_password.txt`. Retrieve it the same way:
```bash
docker compose cp clepsy:/var/lib/clepsy/bootstrap_password.txt - | cat
```

## After Deployment
- Change the bootstrap password from the Clepsy web UI immediately after first login.
- Tail `docker compose logs clepsy` during the first run to confirm database migrations complete cleanly.
- Pair sources from **Settings -> Sources** in the UI. Use these repos to install collectors:
  - [Desktop source](https://github.com/SamGalanakis/clepsy-desktop-source)
  - [Android source](https://github.com/SamGalanakis/clepsy-android-source)

Switch between the tunnel and Caddy approaches by stopping one stack and starting the other compose file combination.
