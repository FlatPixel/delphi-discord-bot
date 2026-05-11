# Discord Delphi Bot

Discord bot implementing the **Delphi method**: iterative, anonymous consultation of an expert panel, with statistical synthesis between rounds.

## Table of contents

- [How it works](#how-it-works)
- [1. Creating the Discord bot](#1-creating-the-discord-bot)
- [2. Deploying](#2-deploying)
- [3. Updates](#3-updates)
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

## 2. Deploying

### Step 1 — Clone the repo

Pick a working directory:

```bash
git clone git@github.com:FlatPixel/delphi-discord-bot.git
cd delphi-bot
```

### Step 2 — Configure the token

```bash
cp .env.example .env
vim .env
```

Fill in:
```
DISCORD_BOT_TOKEN=your_token_pasted_here
```

Save. This file stays local, never online.

### Step 3 — Launch

```bash
docker compose up -d --build
```

`--build` builds the image locally from the `Dockerfile`. `-d` runs it in the background.

### Step 4 — Verify

```bash
docker compose logs -f
```

You should see lines like:
```
[INFO] delphi-bot: Logged in as Delphi#1234 (ID: ...)
[INFO] delphi-bot: Present on 1 server(s)
```

`Ctrl+C` to exit the logs (the container keeps running). On Discord, the bot appears online. Try `/delphi_create` to test.

---

## 3. Updates

```bash
cd /share/Container/delphi-bot
./update.sh
```

The script runs `git pull` + `docker compose build` + `docker compose up -d` + tails the logs. That's it.

### If update.sh isn't executable

```bash
chmod +x update.sh
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
- **Server-side**: the SQLite database (`data/delphi.db`) stores the `user_id` for each response. This is necessary to prevent double-voting and to track who hasn't responded yet. Anyone with SSH/admin access can therefore technically trace individual votes.
- **Network**: no ports are exposed. The bot only makes outbound connections to Discord servers.
- **Backup**: the database lives in `./data/`.
---

## Known limitations

- **No persistent views**: if the bot restarts, the "Respond" button on in-flight DMs stops working. Fallback: `/delphi_respond`.
- **No automatic per-round timeout**: if a panelist never responds, close manually with `/delphi_close_round`.
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
├── update.sh               # Update script
└── README.md               # This file
```

After deployment, this is added:
```
├── .env                    # Discord token (never committed)
└── data/
    └── delphi.db           # SQLite database (never committed)
```
