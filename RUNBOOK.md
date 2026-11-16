# Runbook

## Start, stop, restart

```bash
docker compose up -d --build     # start everything
docker compose ps                # what is running
docker compose logs -f gateway   # follow one service
docker compose restart api       # restart all 3 API copies
docker compose down              # stop (data stays in the pgdata volume)
docker compose down -v           # stop and delete all readings
```

## Is it healthy?

| Check | Command | Healthy answer |
| --- | --- | --- |
| Nginx | `curl localhost:8080/nginx-health` | `ok` |
| API and database | `curl localhost:8080/api/health` | `"status":"ok"`, `"points_with_data":72` |
| Load balancing | run `curl -si localhost:8080/api/health \| grep X-Served-By` a few times | the name changes between the 3 copies |
| Gateway | `docker compose logs --tail 5 gateway` | `saved 72/72 points` every 5 s |
| Assistant | `curl localhost:8080/assistant/health` | `"llm_configured":true` |

## Common problems

**Dashboard says "Cannot reach the API"**
1. `docker compose ps`: are the `api` containers up?
2. `docker compose logs api`: a database error means `db` is not ready. Run `docker compose restart api`.

**Points show `--` or the fault list stays empty**
The gateway is not saving data.
1. `docker compose logs gateway`. `read failed ... timeout` means it cannot reach the simulator.
2. `docker compose restart simulator gateway`.
3. Fault rules need 10 readings (about 1 minute) and drift needs 30 (about 3 minutes) after a fresh start.

**`saved 0/72 points` or `unknown-object` errors**
The gateway is talking to the wrong device. Check `CONTROLLER=simulator:47808` in
`docker-compose.yml`. Running both on one machine without Docker? They need
different ports (47808 and 47809), as in the README.

**Chat answers "LLM not configured"**
Set `LLM_API_KEY` in `.env` (or `LLM_PROVIDER=ollama`), then `docker compose up -d assistant`.
`curl localhost:8080/assistant/health` shows the provider and model in use.

**Chat answers "LLM call failed"**
Check the key, `LLM_PROVIDER`, `LLM_BASE_URL` and `LLM_MODEL`. The model must support tool calling.
"every model was busy" means the provider is overloaded (Gemini's 503 "high demand").
Wait a minute, or add more models to `LLM_MODEL`, separated by commas. The
assistant tries them in order and the chat shows which one answered.
With Ollama, the first answer waits until the model download finishes
(`docker compose logs ollama-pull`).

**One API copy keeps crashing**
`docker compose logs api` shows all copies. Nginx skips a copy that errors
(`proxy_next_upstream`), so users keep working while you fix it.

**Database is filling up**
Each reading is one row: 72 rows every 5 s, about 1.2 million a day. Trim old data:
```bash
docker compose exec db psql -U sbc -c "delete from readings where ts < now() - interval '7 days';"
```

**The agent describes odd history, like a value that "dropped"**
Old readings from an earlier run are still in the database. Start clean with
`docker compose down -v` then `docker compose up --build`.

## Change the faults

Edit `FAULTS` in `.env` (for example `2:fan_off,4:high_co2`), then
`docker compose up -d simulator`.
