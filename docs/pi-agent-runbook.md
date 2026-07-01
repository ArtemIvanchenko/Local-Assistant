# Runbook for the setup agent on the Raspberry Pi

**You are a coding agent running on a Raspberry Pi 5 (8GB).** Your job: bring the
**Local Assistant** (this repo) online as an always-on Telegram AI secretary. Work
top-to-bottom. Each step has a **verification gate** — do not proceed until it passes.
Stop and ask the human only where marked 🙋.

## Ground rules

- **Never commit secrets or personal data.** `.env`, `data/`, `logs/`, `backups/`,
  `MEMORY.md`, `*.gguf` are gitignored — keep it that way. This repo is **public**.
- The software is already complete (phases 0–9). You are doing **deployment + phase 1
  hardware bring-up only** — do not rewrite application code unless a gate fails and the
  cause is a genuine bug (if so, fix minimally, run `pytest`, and note it).
- Prefer the repo's own docs: [`setup-pi.md`](setup-pi.md), [`architecture.md`](architecture.md),
  [`integrations-apple.md`](integrations-apple.md).
- After each gate, print what you verified. At the end, produce the **acceptance report**.

---

## Step 0 — Confirm the environment

```bash
uname -m                      # expect aarch64
free -h                       # expect ~8Gi total
nproc                         # expect 4
cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null   # /1000 = °C
```
**Gate:** 64-bit ARM, ~8GB RAM, 4 cores. If 32-bit OS → 🙋 tell the human to reflash
64-bit Raspberry Pi OS; do not continue.

## Step 1 — System dependencies

```bash
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3-pip sqlite3 gpg git build-essential
```
**Gate:** `python3.11 --version` and `sqlite3 --version` succeed.

## Step 2 — Ollama + server-side speed knobs

```bash
curl -fsSL https://ollama.com/install.sh | sh
sudo systemctl enable --now ollama
```
Add server env (these are NOT per-request): `sudo systemctl edit ollama`, insert:
```
[Service]
Environment="OLLAMA_KV_CACHE_TYPE=q8_0"
Environment="OLLAMA_FLASH_ATTENTION=1"
# Enable only after the draft model is pulled (Step 3):
# Environment="OLLAMA_SPECULATIVE_DECODE=1"
```
Then `sudo systemctl restart ollama`.
**Gate:** `curl -s http://127.0.0.1:11434/api/tags` returns JSON.

## Step 3 — Pull models

```bash
ollama pull qwen3.5:4b          # primary
ollama pull qwen3:4b-instruct   # fallback (used if Qwen3.5 is unstable here)
ollama pull qwen3:1.7b          # router
ollama pull embeddinggemma:300m # embeddings
ollama pull qwen3:0.6b          # speculative-decoding draft
```
**Gate:** `ollama list` shows all five. Then quick sanity:
```bash
ollama run qwen3.5:4b "ответь одним словом: работает?"
```
If Qwen3.5 errors with an operator/format problem (Gated DeltaNet needs a recent
build), run `ollama --version`; if old, update Ollama. If it still fails, note it —
Step 6 will fall back to `qwen3:4b-instruct`.

## Step 4 — Project install

```bash
cd ~ && git clone https://github.com/ArtemIvanchenko/Local-Assistant.git
cd Local-Assistant
python3.11 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pre-commit install || true
python -m pytest -q          # expect all pass
```
**Gate:** `pytest` is green.

## Step 5 — Configuration 🙋

```bash
cp .env.example .env
```
Ask the human for and fill in:
- `TELEGRAM_BOT_TOKEN` — from @BotFather.
- `OWNER_CHAT_IDS` — their numeric id from @userinfobot.
- **Optional** Apple: `APPLE_ID` + `APPLE_APP_PASSWORD` (app-specific password from
  appleid.apple.com — NOT the Apple ID password). Leave blank to stay fully local.
  See [`integrations-apple.md`](integrations-apple.md).

Set `chmod 600 .env`. Adjust `TIMEZONE`, digest times, `QUIET_HOURS` if asked.

## Step 6 — Preflight + choose the main model

```bash
python -m local_assistant --check     # creates/initializes the DB, shows status
```
**Gate:** `--check` shows models installed, `owners` set, and (if configured)
`icloud: on`.

Now pick the main model objectively:
```bash
python scripts/eval_run.py --model qwen3.5:4b        > /tmp/eval_main.txt 2>&1 || true
python scripts/eval_run.py --model qwen3:4b-instruct > /tmp/eval_fallback.txt 2>&1 || true
tail -n 2 /tmp/eval_main.txt /tmp/eval_fallback.txt
```
Choose the model with higher tool-selection accuracy (tie-break: lower latency, and
Qwen3.5 if it ran cleanly). If Qwen3.5 failed to run, choose the fallback. Persist it
by setting `MODEL_MAIN` in `.env` (or leave default if Qwen3.5 won). Re-run `--check`.
**Gate:** the chosen model's eval accuracy is reasonable (aim ≥ 4/6) and latency is
recorded. Report both numbers.

## Step 7 — First run (foreground smoke) 🙋

```bash
python -m local_assistant
```
Ask the human to message the bot on Telegram: e.g. «напомни через 2 минуты проверить бота»
and «что ты умеешь». Confirm: a streamed reply appears, and ~2 min later the reminder
fires **with snooze buttons**. Then Ctrl-C.
**Gate:** reply received + reminder fired. If the bot answers a NON-owner, stop — the
whitelist is misconfigured (check `OWNER_CHAT_IDS`).

## Step 8 — Install as a service + backups

Edit paths/User in the unit if the home dir isn't `/home/pi`.
```bash
sudo cp deploy/systemd/local-assistant.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now local-assistant
systemctl status local-assistant --no-pager

# Nightly encrypted backup:
echo 'BACKUP_PASSPHRASE=<ask-human>' > ~/.local-assistant-backup.env
chmod 600 ~/.local-assistant-backup.env
sudo cp deploy/systemd/local-assistant-backup.{service,timer} /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now local-assistant-backup.timer
```
**Gate:** service is `active (running)`; `journalctl -u local-assistant -n 20` shows
"running"; `systemctl list-timers | grep local-assistant` lists the backup timer.
Verify a backup end-to-end: `sudo systemctl start local-assistant-backup.service` then
check a `backups/la-*.tgz.gpg` file exists.

## Step 9 — Hardware tuning (verify, don't over-tune)

- **Cooling is mandatory.** Run a 2-min load (`ollama run qwen3.5:4b "напиши абзац"`),
  watch temp: `watch -n2 'vcgencmd measure_temp; vcgencmd get_throttled'`. If
  `throttled` is non-zero → 🙋 the human needs active cooling before relying on this.
- Transparent Hugepages: `echo always | sudo tee /sys/kernel/mm/transparent_hugepage/enabled`.
- Optional overclock (only if cooling is good): 🙋 confirm with the human before editing
  `/boot/firmware/config.txt` (`arm_freq=3000`, `over_voltage_delta=50000`), then reboot.
- After the draft model is present, you may enable `OLLAMA_SPECULATIVE_DECODE=1` in the
  ollama service env (Step 2) and `restart ollama`.

## Step 10 — Acceptance report

Report to the human:
- [ ] OS 64-bit, RAM/cores OK, throttling status
- [ ] Ollama up, 5 models pulled
- [ ] `pytest` green, `--check` clean
- [ ] Chosen main model + eval accuracy + avg latency (both candidates)
- [ ] Telegram: streamed reply ✓, reminder+snooze ✓, whitelist enforced ✓
- [ ] iCloud: on/off (+ a synced event visible if on)
- [ ] systemd service active + backup timer scheduled + one backup produced
- [ ] Cooling verdict (throttled or not) and whether overclock was applied

---

## Troubleshooting

| Symptom | Likely cause → fix |
|---|---|
| `--check`: ollama not reachable | `systemctl status ollama`; restart it |
| Qwen3.5 errors on run | Old Ollama/llama.cpp; update Ollama, else use `qwen3:4b-instruct` |
| Bot starts then exits: "OWNER_CHAT_IDS not set" | Fill `OWNER_CHAT_IDS` in `.env` |
| Replies very slow / device hot | Throttling — needs active cooling (Step 9) |
| `sqlite-vec: fallback` in `--check` | Extension didn't load; semantic search degrades to LIKE — acceptable, note it |
| iCloud errors on add_event | Wrong app-specific password, or data is "On My Mac" not iCloud |
| Bot answers a stranger | `OWNER_CHAT_IDS` wrong — fix immediately, it's a security issue |

Keep changes minimal and reversible. When done, leave the working tree clean
(`git status` — only `.env`/`data/` which are ignored).
