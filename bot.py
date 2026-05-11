#!/usr/bin/env python3
"""
Bot Discord pour la méthode Delphi.
Collecte itérative et anonyme d'avis d'experts via DM, avec synthèse
statistique entre les tours.
"""

import os
import re
import json
import logging
import sqlite3
import statistics
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

# ============== CONFIGURATION ==============

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("delphi-bot")

TOKEN = os.getenv("DISCORD_BOT_TOKEN")
DB_PATH = os.getenv("DELPHI_DB_PATH", "delphi.db")

intents = discord.Intents.default()
intents.members = True  # Privilégié : à activer dans le Developer Portal
bot = commands.Bot(command_prefix="!", intents=intents)


# ============== BASE DE DONNÉES ==============

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,
                facilitator_id INTEGER NOT NULL,
                question TEXT NOT NULL,
                question_type TEXT NOT NULL,
                options TEXT,
                total_rounds INTEGER NOT NULL,
                current_round INTEGER DEFAULT 1,
                status TEXT DEFAULT 'active',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS panelists (
                session_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                PRIMARY KEY (session_id, user_id)
            );
            CREATE TABLE IF NOT EXISTS responses (
                session_id INTEGER NOT NULL,
                round_number INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                value TEXT NOT NULL,
                justification TEXT,
                submitted_at TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (session_id, round_number, user_id)
            );
        """)


# ============== LOGIQUE DELPHI ==============

def create_session(guild_id, channel_id, facilitator_id, question,
                   qtype, options, panelists, rounds):
    with db() as conn:
        cur = conn.execute(
            """INSERT INTO sessions
               (guild_id, channel_id, facilitator_id, question,
                question_type, options, total_rounds)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (guild_id, channel_id, facilitator_id, question, qtype,
             json.dumps(options) if options else None, rounds),
        )
        session_id = cur.lastrowid
        for uid in panelists:
            conn.execute(
                "INSERT OR IGNORE INTO panelists (session_id, user_id) VALUES (?, ?)",
                (session_id, uid),
            )
        return session_id


def get_session(session_id):
    with db() as conn:
        return conn.execute(
            "SELECT * FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()


def get_panelists(session_id):
    with db() as conn:
        rows = conn.execute(
            "SELECT user_id FROM panelists WHERE session_id = ?",
            (session_id,),
        ).fetchall()
    return [r["user_id"] for r in rows]


def is_panelist(session_id, user_id):
    with db() as conn:
        return conn.execute(
            "SELECT 1 FROM panelists WHERE session_id = ? AND user_id = ?",
            (session_id, user_id),
        ).fetchone() is not None


def submit_response(session_id, round_num, user_id, value, justification=None):
    with db() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO responses
               (session_id, round_number, user_id, value, justification)
               VALUES (?, ?, ?, ?, ?)""",
            (session_id, round_num, user_id, value, justification),
        )


def all_responses_in(session_id, round_num):
    with db() as conn:
        n_panel = conn.execute(
            "SELECT COUNT(*) FROM panelists WHERE session_id = ?",
            (session_id,),
        ).fetchone()[0]
        n_resp = conn.execute(
            """SELECT COUNT(*) FROM responses
               WHERE session_id = ? AND round_number = ?""",
            (session_id, round_num),
        ).fetchone()[0]
    return n_resp >= n_panel


def synthesize_round(session_id, round_num):
    """Génère une synthèse statistique anonymisée du tour."""
    session = get_session(session_id)
    with db() as conn:
        responses = conn.execute(
            """SELECT value, justification FROM responses
               WHERE session_id = ? AND round_number = ?""",
            (session_id, round_num),
        ).fetchall()

    qtype = session["question_type"]
    values = [r["value"] for r in responses]
    justifs = [r["justification"] for r in responses if r["justification"]]

    out = f"**Synthèse du tour {round_num}** — {len(responses)} réponse(s)\n\n"

    if qtype == "numeric":
        nums = [float(v) for v in values]
        out += (
            f"📊 **Statistiques**\n"
            f"• Médiane : `{statistics.median(nums):.2f}`\n"
            f"• Moyenne : `{statistics.mean(nums):.2f}`\n"
            f"• Min – Max : `{min(nums):.2f}` – `{max(nums):.2f}`\n"
        )
        if len(nums) >= 4:
            q = statistics.quantiles(nums, n=4)
            out += f"• Q1 – Q3 : `{q[0]:.2f}` – `{q[2]:.2f}` (IIQ)\n"

    elif qtype == "likert":
        out += "📊 **Distribution** (1 = pas du tout d'accord, 5 = tout à fait)\n"
        for i in range(1, 6):
            c = values.count(str(i))
            bar = "█" * c if c else "·"
            out += f"`{i}` {bar} ({c})\n"
        nums = [int(v) for v in values]
        out += (f"\nMédiane : `{statistics.median(nums)}` | "
                f"Moyenne : `{statistics.mean(nums):.2f}`\n")

    elif qtype == "choice":
        options = json.loads(session["options"])
        out += "📊 **Répartition des votes**\n"
        ranked = sorted(
            ((opt, values.count(opt)) for opt in options),
            key=lambda x: -x[1],
        )
        for opt, c in ranked:
            bar = "█" * c if c else "·"
            out += f"**{opt}** : {bar} ({c})\n"

    if justifs:
        out += "\n💬 **Arguments anonymisés**\n"
        for j in justifs:
            j_short = j[:300] + ("…" if len(j) > 300 else "")
            out += f"> {j_short}\n"

    return out


def advance_round(session_id):
    """Passe au tour suivant, ou clôture la session si dernier tour atteint."""
    session = get_session(session_id)
    if session["current_round"] >= session["total_rounds"]:
        with db() as conn:
            conn.execute(
                "UPDATE sessions SET status = 'completed' WHERE id = ?",
                (session_id,),
            )
        return None
    new_round = session["current_round"] + 1
    with db() as conn:
        conn.execute(
            "UPDATE sessions SET current_round = ? WHERE id = ?",
            (new_round, session_id),
        )
    return new_round


# ============== INTERFACE UTILISATEUR ==============

class ResponseModal(discord.ui.Modal):
    """Formulaire de réponse à un tour."""

    def __init__(self, session_id, round_num, qtype, options=None):
        super().__init__(title=f"Réponse — Tour {round_num}")
        self.session_id = session_id
        self.round_num = round_num
        self.qtype = qtype
        self.options = options

        if qtype == "numeric":
            self.value_input = discord.ui.TextInput(
                label="Votre estimation (nombre)",
                placeholder="ex : 42.5",
                required=True,
                max_length=20,
            )
        elif qtype == "likert":
            self.value_input = discord.ui.TextInput(
                label="Niveau d'accord (1 à 5)",
                placeholder="1 = pas du tout, 5 = tout à fait",
                required=True,
                max_length=1,
            )
        else:  # choice
            opts_preview = " / ".join(options or [])
            self.value_input = discord.ui.TextInput(
                label="Votre choix",
                placeholder=opts_preview[:100],
                required=True,
                max_length=100,
            )
        self.add_item(self.value_input)

        self.justif_input = discord.ui.TextInput(
            label="Justification (optionnelle, recommandée)",
            style=discord.TextStyle.paragraph,
            required=False,
            max_length=1000,
        )
        self.add_item(self.justif_input)

    async def on_submit(self, interaction: discord.Interaction):
        v = self.value_input.value.strip()

        # Validation
        if self.qtype == "numeric":
            try:
                float(v)
            except ValueError:
                await interaction.response.send_message(
                    "❌ Valeur invalide : entrez un nombre.", ephemeral=True
                )
                return
        elif self.qtype == "likert":
            if v not in {"1", "2", "3", "4", "5"}:
                await interaction.response.send_message(
                    "❌ Entrez un entier entre 1 et 5.", ephemeral=True
                )
                return
        elif self.qtype == "choice":
            if v not in (self.options or []):
                await interaction.response.send_message(
                    f"❌ Options possibles : {', '.join(self.options or [])}",
                    ephemeral=True,
                )
                return

        submit_response(
            self.session_id, self.round_num, interaction.user.id,
            v, self.justif_input.value or None,
        )
        await interaction.response.send_message(
            "✅ Réponse enregistrée, merci.", ephemeral=True
        )

        if all_responses_in(self.session_id, self.round_num):
            logger.info(
                f"Toutes les réponses reçues pour session {self.session_id} "
                f"tour {self.round_num}, clôture automatique."
            )
            await close_round(self.session_id, self.round_num)


class RespondView(discord.ui.View):
    """Vue avec un bouton 'Répondre' (non persistante)."""

    def __init__(self, session_id, round_num, qtype, options=None):
        super().__init__(timeout=None)
        self.session_id = session_id
        self.round_num = round_num
        self.qtype = qtype
        self.options = options

    @discord.ui.button(
        label="Répondre", style=discord.ButtonStyle.primary, emoji="📝"
    )
    async def respond(self, interaction, button):
        modal = ResponseModal(
            self.session_id, self.round_num, self.qtype, self.options
        )
        await interaction.response.send_modal(modal)


async def send_round_to_panelist(user, session_id, round_num, question,
                                 qtype, options=None, synthesis=None):
    """DM un panéliste avec la question et un bouton de réponse."""
    embed = discord.Embed(
        title=f"🗳️ Delphi — Tour {round_num} (session #{session_id})",
        description=question,
        color=discord.Color.blue(),
    )
    if synthesis:
        embed.add_field(
            name="Synthèse du tour précédent",
            value=synthesis[:1024],
            inline=False,
        )
        embed.add_field(
            name="💡 Consigne",
            value=("Au regard de la synthèse, vous pouvez réviser ou "
                   "confirmer votre position. **Si vous êtes éloigné(e) "
                   "de la médiane, justifiez en quelques mots.**"),
            inline=False,
        )
    if qtype == "choice" and options:
        embed.add_field(
            name="Options",
            value="\n".join(f"• {o}" for o in options),
            inline=False,
        )
    embed.set_footer(
        text=f"Astuce : si le bouton ne répond plus, utilisez "
             f"/delphi_respond session_id:{session_id}"
    )

    view = RespondView(session_id, round_num, qtype, options)
    try:
        await user.send(embed=embed, view=view)
        return True
    except discord.Forbidden:
        logger.warning(f"DM impossible pour user {user.id}")
        return False


async def close_round(session_id, round_num):
    """Clôture le tour, poste la synthèse, lance le tour suivant ou termine."""
    session = get_session(session_id)
    if not session or session["status"] != "active":
        return
    if session["current_round"] != round_num:
        return  # Déjà clôturé

    synthesis = synthesize_round(session_id, round_num)
    channel = bot.get_channel(session["channel_id"])

    if channel:
        # Découpe en plusieurs messages si trop long
        chunks = [synthesis[i:i + 1900] for i in range(0, len(synthesis), 1900)]
        await channel.send(
            f"🔔 **Tour {round_num} clôturé** — session #{session_id}"
        )
        for c in chunks:
            await channel.send(c)

    new_round = advance_round(session_id)
    if new_round is None:
        if channel:
            await channel.send(
                f"🏁 **Session #{session_id} terminée.** "
                f"La synthèse ci-dessus constitue le résultat final."
            )
        return

    options = json.loads(session["options"]) if session["options"] else None
    for uid in get_panelists(session_id):
        try:
            user = bot.get_user(uid) or await bot.fetch_user(uid)
            await send_round_to_panelist(
                user, session_id, new_round, session["question"],
                session["question_type"], options=options, synthesis=synthesis,
            )
        except Exception as e:
            logger.exception(f"Erreur envoi tour {new_round} à user {uid}: {e}")


# ============== SLASH COMMANDS ==============

@bot.tree.command(
    name="delphi_create",
    description="Lance une nouvelle session Delphi",
)
@app_commands.describe(
    question="La question soumise au panel",
    panel="Mentions des participants (ex : @alice @bob @charlie)",
    type="Type de réponse attendue",
    rounds="Nombre de tours (2 à 5, défaut 3)",
    options="Pour 'choice' uniquement : options séparées par | (ex : A|B|C)",
)
@app_commands.choices(type=[
    app_commands.Choice(name="Numérique (estimation chiffrée)", value="numeric"),
    app_commands.Choice(name="Likert 1-5 (niveau d'accord)", value="likert"),
    app_commands.Choice(name="Choix parmi options", value="choice"),
])
async def delphi_create(
    interaction: discord.Interaction,
    question: str,
    panel: str,
    type: app_commands.Choice[str],
    rounds: int = 3,
    options: Optional[str] = None,
):
    user_ids = [int(m) for m in re.findall(r"<@!?(\d+)>", panel)]
    if not user_ids:
        await interaction.response.send_message(
            "❌ Mentionnez au moins un participant (@nom).", ephemeral=True
        )
        return
    if not 2 <= rounds <= 5:
        await interaction.response.send_message(
            "❌ Le nombre de tours doit être entre 2 et 5.", ephemeral=True
        )
        return

    parsed_options = None
    if type.value == "choice":
        if not options:
            await interaction.response.send_message(
                "❌ Pour 'choice', précisez les options (séparées par |).",
                ephemeral=True,
            )
            return
        parsed_options = [o.strip() for o in options.split("|") if o.strip()]
        if len(parsed_options) < 2:
            await interaction.response.send_message(
                "❌ Au moins 2 options sont nécessaires.", ephemeral=True
            )
            return

    session_id = create_session(
        interaction.guild_id, interaction.channel_id, interaction.user.id,
        question, type.value, parsed_options, list(set(user_ids)), rounds,
    )

    await interaction.response.send_message(
        f"✅ **Session Delphi #{session_id} créée.**\n"
        f"📨 Envoi des invitations en DM aux {len(set(user_ids))} panélistes…",
        ephemeral=False,
    )

    failed = []
    for uid in set(user_ids):
        try:
            user = bot.get_user(uid) or await bot.fetch_user(uid)
            ok = await send_round_to_panelist(
                user, session_id, 1, question, type.value, parsed_options
            )
            if not ok:
                failed.append(f"<@{uid}>")
        except Exception as e:
            logger.exception(f"Erreur DM user {uid}: {e}")
            failed.append(f"<@{uid}>")

    if failed:
        await interaction.followup.send(
            f"⚠️ Impossible d'envoyer un DM à : {', '.join(failed)} "
            f"(DMs fermés ou utilisateur introuvable).",
            ephemeral=True,
        )


@bot.tree.command(
    name="delphi_respond",
    description="Répondre au tour en cours d'une session (fallback du bouton DM)",
)
@app_commands.describe(session_id="ID de la session")
async def delphi_respond(interaction: discord.Interaction, session_id: int):
    session = get_session(session_id)
    if not session:
        await interaction.response.send_message(
            "❌ Session introuvable.", ephemeral=True
        )
        return
    if not is_panelist(session_id, interaction.user.id):
        await interaction.response.send_message(
            "❌ Vous ne faites pas partie de ce panel.", ephemeral=True
        )
        return
    if session["status"] != "active":
        await interaction.response.send_message(
            "❌ Cette session est terminée.", ephemeral=True
        )
        return
    options = json.loads(session["options"]) if session["options"] else None
    modal = ResponseModal(
        session_id, session["current_round"], session["question_type"], options
    )
    await interaction.response.send_modal(modal)


@bot.tree.command(
    name="delphi_status",
    description="Affiche l'état d'une session",
)
@app_commands.describe(session_id="ID de la session")
async def delphi_status(interaction: discord.Interaction, session_id: int):
    session = get_session(session_id)
    if not session:
        await interaction.response.send_message(
            "❌ Session introuvable.", ephemeral=True
        )
        return
    panelists = get_panelists(session_id)
    with db() as conn:
        responded = conn.execute(
            """SELECT COUNT(*) FROM responses
               WHERE session_id = ? AND round_number = ?""",
            (session_id, session["current_round"]),
        ).fetchone()[0]

    embed = discord.Embed(
        title=f"📋 Session Delphi #{session_id}",
        description=session["question"],
        color=discord.Color.gold(),
    )
    embed.add_field(name="Statut", value=session["status"], inline=True)
    embed.add_field(
        name="Tour",
        value=f"{session['current_round']}/{session['total_rounds']}",
        inline=True,
    )
    embed.add_field(
        name="Réponses",
        value=f"{responded}/{len(panelists)}",
        inline=True,
    )
    embed.add_field(name="Type", value=session["question_type"], inline=True)
    embed.add_field(
        name="Facilitateur",
        value=f"<@{session['facilitator_id']}>",
        inline=True,
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(
    name="delphi_close_round",
    description="Force la clôture du tour en cours (facilitateur uniquement)",
)
@app_commands.describe(session_id="ID de la session")
async def delphi_close_round(interaction: discord.Interaction, session_id: int):
    session = get_session(session_id)
    if not session:
        await interaction.response.send_message(
            "❌ Session introuvable.", ephemeral=True
        )
        return
    if interaction.user.id != session["facilitator_id"]:
        await interaction.response.send_message(
            "❌ Seul le facilitateur peut clôturer un tour manuellement.",
            ephemeral=True,
        )
        return
    if session["status"] != "active":
        await interaction.response.send_message(
            "❌ Session déjà terminée.", ephemeral=True
        )
        return

    await interaction.response.send_message(
        f"⏩ Clôture du tour {session['current_round']}…", ephemeral=True
    )
    await close_round(session_id, session["current_round"])


@bot.tree.command(
    name="delphi_abort",
    description="Annule une session en cours (facilitateur uniquement)",
)
@app_commands.describe(session_id="ID de la session")
async def delphi_abort(interaction: discord.Interaction, session_id: int):
    session = get_session(session_id)
    if not session:
        await interaction.response.send_message(
            "❌ Session introuvable.", ephemeral=True
        )
        return
    if interaction.user.id != session["facilitator_id"]:
        await interaction.response.send_message(
            "❌ Seul le facilitateur peut annuler.", ephemeral=True
        )
        return
    with db() as conn:
        conn.execute(
            "UPDATE sessions SET status = 'aborted' WHERE id = ?",
            (session_id,),
        )
    await interaction.response.send_message(
        f"🛑 Session #{session_id} annulée.", ephemeral=False
    )


# ============== ÉVÉNEMENTS ==============

@bot.event
async def on_ready():
    init_db()
    await bot.tree.sync()
    logger.info(f"Connecté comme {bot.user} (ID: {bot.user.id})")
    logger.info(f"Présent sur {len(bot.guilds)} serveur(s)")


if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit(
            "❌ Définissez la variable d'environnement DISCORD_BOT_TOKEN"
        )
    bot.run(TOKEN, log_handler=None)
