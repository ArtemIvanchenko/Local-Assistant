# Setup on Raspberry Pi 5 (8GB)

## Hardware

- **Active cooling is mandatory** — without it the SoC throttles within ~90s and
  tokens/sec halves. Use the official Active Cooler or a fan HAT.
- **NVMe SSD via HAT** strongly recommended: OS + DB live here (microSD wears out
  from SQLite writes; SSD also loads models 3–5× faster).
- Optional overclock to 2.8–3.0 GHz (`/boot/firmware/config.txt`):
  ```
  arm_freq=3000
  over_voltage_delta=50000
  ```

## OS + Ollama

```bash
# 64-bit Raspberry Pi OS (Bookworm) or Ubuntu Server 24.04 ARM64
sudo apt update && sudo apt install -y python3.11 python3.11-venv sqlite3 gpg

# Use the LATEST Ollama — Qwen3.5 Gated DeltaNet needs recent llama.cpp operators
curl -fsSL https://ollama.com/install.sh | sh
ollama pull qwen3.5:4b
ollama pull qwen3:1.7b
ollama pull embeddinggemma:300m
ollama pull qwen3:0.6b        # optional: speculative-decoding draft
# Fallback if Qwen3.5 misbehaves on this build:
# ollama pull qwen3:4b-instruct
```

Enable Transparent Hugepages for a prefill boost:
```bash
echo always | sudo tee /sys/kernel/mm/transparent_hugepage/enabled
```

Speed knobs that live on the **Ollama server** (not per-request). Add them to the
Ollama service environment (`sudo systemctl edit ollama`):
```
[Service]
Environment="OLLAMA_KV_CACHE_TYPE=q8_0"        # quantize KV cache → more context fits
Environment="OLLAMA_SPECULATIVE_DECODE=1"      # draft model speedup (Ollama 5.x)
Environment="OLLAMA_FLASH_ATTENTION=1"
```
Then `ollama pull qwen3:0.6b` so the draft model is available.

## Project

```bash
git clone https://github.com/ArtemIvanchenko/Local-Assistant.git
cd Local-Assistant
python3.11 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pre-commit install

cp .env.example .env
#  - TELEGRAM_BOT_TOKEN  (from @BotFather)
#  - OWNER_CHAT_IDS      (your id from @userinfobot)

sqlite3 data/assistant.db < src/local_assistant/db/schema.sql
python -m local_assistant
```

## Service + backups

```bash
sudo cp deploy/systemd/local-assistant.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now local-assistant
# Restart=always in the unit acts as the crash watchdog.

# Encrypted nightly backup (systemd timer):
echo 'BACKUP_PASSPHRASE=change-me' > ~/.local-assistant-backup.env && chmod 600 ~/.local-assistant-backup.env
sudo cp deploy/systemd/local-assistant-backup.{service,timer} /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now local-assistant-backup.timer
```

## Verify

- `free -h` while a request runs → models + app fit in 8GB.
- Send a message → reply from the local model; check `messages` table.
- `systemctl restart local-assistant` → reminders/history survive.
