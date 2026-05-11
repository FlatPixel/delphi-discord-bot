# Discord Delphi Bot

Discord bot implementing the **Delphi method**: iterative, anonymous consultation of an expert panel, with statistical synthesis between rounds.

## Table of contents

- [How it works](#how-it-works)
- [1. Creating the Discord bot](#1-creating-the-discord-bot)
- [2. Setting up the GitHub repo](#2-setting-up-the-github-repo)
- [3. Deploying on QNAP](#3-deploying-on-qnap)
- [4. Updates](#4-updates)
- [Bot commands](#bot-commands)
- [Anonymity & security](#anonymity--security)
- [Known limitations](#known-limitations)

## How it works

1. The **facilitator** starts a session with `/delphi_create`: question, panel (mentions), response type, number of rounds.
2. The bot **DMs each panelist** with a "Respond" button that opens a form.
3. Responses are **collected privately** (justification is optional but recommended).
4. Once everyone has answered, the bot **generates an anonymized synthesis**: median, distribution, arguments — without revealing who said what.
5. The bot **DMs each panelist** with this synthesis and invites them to revise for the next round.
6. Iterate until all rounds are done, then **post the final report** in the original channel.

Three question types: **numeric** (median / mean / quartiles), **Likert 1-5** (distribution), **multiple choice** (votes per option).

---

## 1. Creating the Discord bot

1. Go to https://discord.com/developers/applications → **New Application**.
2. **Bot** tab → **Add Bot** → copy the **TOKEN** (put it in `.env` later, **never in Git**).
3. Still in **Bot** → enable **Privileged Gateway Intents** → check `SERVER MEMBERS INTENT`.
4. **OAuth2 → URL Generator** tab:
   - Scopes: `bot` + `applications.commands`
   - Permissions: `Send Messages`, `Use Slash Commands`, `Read Message History`
   - Copy the generated URL, open it in a browser, add the bot to your server.

---

## 2. Setting up the GitHub repo

### On your dev machine

```bash
# From the folder containing all the provided files
git init
git add .
git commit -m "Initial commit: Discord Delphi bot"

# Create a repo on github.com (public or private doesn't matter — .env is gitignored)
git remote add origin git@github.com:YOUR_USER/delphi-bot.git
git branch -M main
git push -u origin main
```

⚠️ **Before pushing**, verify that `.gitignore` excludes `.env` and `data/`. The repo must NEVER contain your Discord token. The `.env.example` file is committed as a blank template.

### Public or private?

- **Public repo**: no auth needed for `git clone` on the QNAP. Simple. As long as `.env` stays gitignored, nothing sensitive is exposed — the code itself isn't confidential.
- **Private repo**: requires an **SSH key** on the NAS added to your GitHub account, or a **Personal Access Token** for HTTPS cloning. More friction, more privacy.

---

## 3. Deploying on QNAP

### Prerequisites

- QNAP model compatible with **Container Station** (almost all x86 models: TS-x53, x64, x73, h-series, TVS, etc.). Low-end ARM models (TS-x28 / x31 / x32) don't support it.
- **SSH enabled** on your NAS (Control Panel → Telnet/SSH).
- **Container Station** installed via the App Center.

### Step 1 — Enable SSH and connect

In QTS: *Control Panel → Network & File Services → Telnet/SSH* → check **Enable SSH**.

From your computer:
```bash
ssh admin@YOUR_NAS_IP
```

### Step 2 — Clone the repo

Pick a working directory. Container Station creates a `/share/Container/` share by default:

```bash
cd /share/Container/
git clone https://github.com/YOUR_USER/delphi-bot.git
cd delphi-bot
```

For a private repo over SSH: `git clone git@github.com:YOUR_USER/delphi-bot.git` after adding the NAS's public key to GitHub.

### Step 3 — Configure the token

```bash
cp .env.example .env
vi .env     # or nano if installed via Entware
```

Fill in:
```
DISCORD_BOT_TOKEN=your_token_pasted_here
```

Save. This file stays local to the NAS, never on GitHub.

### Step 4 — Launch

```bash
docker compose up -d --build
```

`--build` builds the image locally from the `Dockerfile`. `-d` runs it in the background.

### Step 5 — Verify

```bash
docker compose logs -f
```

You should see lines like:
```
[INFO] delphi-bot: Logged in as Delphi#1234 (ID: ...)
[INFO] delphi-bot: Present on 1 server(s)
```

`Ctrl+C` to exit the logs (the container keeps running). On Discord, the bot appears online. Try `/delphi_create` to test.

### Step 6 — Container Station visibility

The container shows up automatically in Container Station's UI (Containers section). You can view logs, CPU/RAM usage, and restart it in one click. You can also do everything graphically: *Container Station → Create → Create Application → paste the `docker-compose.yml` content*.

---

## 4. Updates

### Normal workflow

On your dev machine, edit the code → commit → push:
```bash
git add bot.py
git commit -m "feat: add automatic per-round deadline"
git push
```

On the QNAP via SSH:
```bash
cd /share/Container/delphi-bot
./update.sh
```

The script runs `git pull` + `docker compose build` + `docker compose up -d` + tails the logs. That's it.

### If update.sh isn't executable

```bash
chmod +x update.sh
```

### Rollback if something breaks

```bash
git log --oneline                    # find a working commit
git checkout COMMIT_HASH
docker compose up -d --build
```

---

## Bot commands

| Command | Usage |
|---------|-------|
| `/delphi_create` | Start a session (facilitator) |
| `/delphi_respond session_id:N` | Respond to the current round (fallback if the DM button stops working, e.g. after a bot restart) |
| `/delphi_status session_id:N` | Show session state |
| `/delphi_close_round session_id:N` | Force-close the current round (facilitator) |
| `/delphi_abort session_id:N` | Abort the session (facilitator) |

### Examples

```
/delphi_create
  question: How many person-days to deliver the back-office redesign?
  panel: @alice @bob @charlie @diana
  type: Numeric (numerical estimate)
  rounds: 3
```

```
/delphi_create
  question: Which market should we prioritize in H2?
  panel: @alice @bob @charlie
  type: Choice among options
  rounds: 2
  options: France|Germany|Spain|Italy
```

---

## Anonymity & security

- **Panel-side**: nobody sees who answered what. Syntheses contain only statistical aggregates and depersonalized justifications.
- **Server-side**: the SQLite database (`data/delphi.db` on the NAS) stores the `user_id` for each response. This is necessary to prevent double-voting and to track who hasn't responded yet. Anyone with SSH/admin access to the NAS can therefore technically trace individual votes.
- **Network**: no ports are exposed. The bot only makes outbound connections to Discord servers. The NAS stays invisible from the internet for this service.
- **Backup**: the database lives in `./data/`. Include it in your regular QNAP backup strategy (Hyper Data Protector, snapshots, etc.).

---

## Known limitations

- **No persistent views**: if the bot restarts, the "Respond" button on in-flight DMs stops working. Fallback: `/delphi_respond`.
- **No automatic per-round timeout**: if a panelist never responds, close manually with `/delphi_close_round`.
- **No free-text questions**: to add this, plug an LLM (e.g. Anthropic API) into the justifications to summarize them.
- **No CSV/JSON export** of sessions.
- **One session = one question**: for a multi-item questionnaire, run several sessions in parallel.

---

## Repo structure

```
delphi-bot/
├── bot.py                  # Bot code
├── requirements.txt        # Python dependencies
├── Dockerfile              # Image build
├── docker-compose.yml      # Orchestration
├── .env.example            # Config template (copy to .env)
├── .gitignore              # Excludes .env, data/, __pycache__
├── update.sh               # Update script for the QNAP
└── README.md               # This file
```

After deployment on the NAS, this is added:
```
├── .env                    # Discord token (never committed)
└── data/
    └── delphi.db           # SQLite database (never committed)
```
