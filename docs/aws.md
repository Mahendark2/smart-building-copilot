# Running on AWS (EC2)

The simplest setup is one EC2 instance running Docker Compose.

1. Launch an instance: Ubuntu 24.04, `t3.small` or bigger, 20 GB disk.
2. Security group: allow SSH (22) from your IP, and HTTP on the dashboard port
   (8080, or 80 if you set `PORT=80`). Do not open 5432 or 47808.
3. Install Docker:
   ```bash
   sudo apt update && sudo apt install -y docker.io docker-compose-v2 git
   sudo usermod -aG docker $USER && newgrp docker
   ```
4. Get the code and start it:
   ```bash
   git clone <your repo url> smart-building-copilot
   cd smart-building-copilot
   cp .env.example .env && nano .env     # add LLM_API_KEY
   docker compose up -d --build
   ```
5. Open `http://<instance public IP>:8080`.

## Monitoring

- `docker compose logs -f` shows every service. For logs that survive restarts,
  set Docker's `awslogs` log driver to send them to CloudWatch.
- `/api/health` returns 503 when the database is down, so it works as a health
  check for a load balancer or an uptime monitor.
- See [../RUNBOOK.md](../RUNBOOK.md) for the checks and fixes.

## Cost

A `t3.small` running all day costs a few dollars a week. Stop the instance when
you are not demoing it.
