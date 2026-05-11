# Bot Discord Delphi

Bot Discord qui implémente la **méthode Delphi** : consultation itérative et anonyme d'un panel d'experts, avec synthèse statistique entre les tours.

## Sommaire

- [Fonctionnement](#fonctionnement)
- [1. Création du bot Discord](#1-création-du-bot-discord)
- [2. Mise en place du repo GitHub](#2-mise-en-place-du-repo-github)
- [3. Déploiement sur QNAP](#3-déploiement-sur-qnap)
- [4. Mises à jour ultérieures](#4-mises-à-jour-ultérieures)
- [Commandes du bot](#commandes-du-bot)
- [Anonymat & sécurité](#anonymat--sécurité)
- [Limitations connues](#limitations-connues)

## Fonctionnement

1. Le **facilitateur** lance une session avec `/delphi_create` : question, panel (mentions), type de réponse, nombre de tours.
2. Le bot **envoie un DM** à chaque panéliste avec un bouton « Répondre » qui ouvre un formulaire.
3. Les réponses sont **collectées en privé** (justification optionnelle mais recommandée).
4. Quand tous ont répondu, le bot **génère une synthèse anonymisée** : médiane, distribution, arguments — sans révéler qui a dit quoi.
5. Le bot **DM chaque panéliste** avec cette synthèse et l'invite à réviser pour le tour suivant.
6. Itération jusqu'à épuisement des tours, puis **rapport final** dans le canal d'origine.

Trois types de questions : **numérique** (médiane/moyenne/quartiles), **Likert 1-5** (distribution), **choix multiple** (votes par option).

---

## 1. Création du bot Discord

1. Va sur https://discord.com/developers/applications → **New Application**.
2. Onglet **Bot** → **Add Bot** → copie le **TOKEN** (à mettre dans `.env` plus tard, **jamais dans Git**).
3. Toujours dans **Bot** → active **Privileged Gateway Intents** → coche `SERVER MEMBERS INTENT`.
4. Onglet **OAuth2 → URL Generator** :
   - Scopes : `bot` + `applications.commands`
   - Permissions : `Send Messages`, `Use Slash Commands`, `Read Message History`
   - Copie l'URL générée, ouvre-la dans un navigateur, ajoute le bot à ton serveur.

---

## 2. Mise en place du repo GitHub

### Sur ta machine de dev

```bash
# Dans le dossier contenant tous les fichiers fournis
git init
git add .
git commit -m "Initial commit: bot Delphi Discord"

# Crée un repo sur github.com (public ou privé peu importe — le .env est gitignored)
git remote add origin git@github.com:TON_USER/delphi-bot.git
git branch -M main
git push -u origin main
```

⚠️ **Vérifie avant le push** que `.gitignore` exclut bien `.env` et `data/`. Le repo ne doit JAMAIS contenir ton token Discord. Le fichier `.env.example` est commit, lui, comme modèle vide.

### Public ou privé ?

- **Repo public** : pas d'auth nécessaire pour le `git clone` sur le QNAP. Simple. Tant que `.env` est gitignored, aucune info sensible n'est exposée — le code n'a rien de confidentiel.
- **Repo privé** : il te faudra une **clé SSH** sur le NAS ajoutée à ton compte GitHub, ou un **Personal Access Token** pour cloner en HTTPS. Plus de friction mais plus discret.

---

## 3. Déploiement sur QNAP

### Prérequis

- Modèle QNAP compatible **Container Station** (la quasi-totalité des x86 : TS-x53, x64, x73, h-series, TVS, etc.). Les modèles ARM bas de gamme (TS-x28/x31/x32) ne le supportent pas.
- **SSH activé** sur ton NAS (Panneau de configuration → Telnet/SSH).
- **Container Station** installé via l'App Center.

### Étape 1 — Activer SSH et se connecter

Sur l'interface QTS : *Panneau de configuration → Network & File Services → Telnet/SSH* → coche **Enable SSH**.

Depuis ton ordi :
```bash
ssh admin@IP_DE_TON_NAS
```

### Étape 2 — Cloner le repo

Choisis un emplacement de travail. Container Station crée un partage `/share/Container/` par défaut :

```bash
cd /share/Container/
git clone https://github.com/TON_USER/delphi-bot.git
cd delphi-bot
```

Pour un repo privé en SSH : `git clone git@github.com:TON_USER/delphi-bot.git` après avoir ajouté la clé publique du NAS à GitHub.

### Étape 3 — Configurer le token

```bash
cp .env.example .env
vi .env     # ou nano si installé via Entware
```

Renseigne :
```
DISCORD_BOT_TOKEN=ton_token_collé_ici
```

Sauvegarde. Ce fichier reste local au NAS, jamais sur GitHub.

### Étape 4 — Lancer

```bash
docker compose up -d --build
```

Le `--build` construit l'image localement à partir du `Dockerfile`. `-d` lance en arrière-plan.

### Étape 5 — Vérifier

```bash
docker compose logs -f
```

Tu dois voir une ligne du genre :
```
[INFO] delphi-bot: Connecté comme Delphi#1234 (ID: ...)
[INFO] delphi-bot: Présent sur 1 serveur(s)
```

`Ctrl+C` pour quitter les logs (le conteneur continue de tourner). Sur Discord, le bot apparaît en ligne. Lance `/delphi_create` pour tester.

### Étape 6 — Visibilité dans Container Station

Le conteneur apparaît automatiquement dans l'UI de Container Station (rubrique « Conteneurs »). Tu peux y voir les logs, l'usage CPU/RAM, le redémarrer en un clic. Tu peux aussi tout piloter en graphique : *Container Station → Créer → Créer une application → coller le contenu du `docker-compose.yml`*.

---

## 4. Mises à jour ultérieures

### Workflow normal

Sur ta machine de dev, tu modifies le code → commit → push :
```bash
git add bot.py
git commit -m "feat: ajout deadline automatique par tour"
git push
```

Sur le QNAP en SSH :
```bash
cd /share/Container/delphi-bot
./update.sh
```

Le script fait `git pull` + `docker compose build` + `docker compose up -d` + affiche les logs. C'est tout.

### Si update.sh n'est pas exécutable

```bash
chmod +x update.sh
```

### Rollback en cas de pépin

```bash
git log --oneline                    # trouve un commit qui marchait
git checkout COMMIT_HASH
docker compose up -d --build
```

---

## Commandes du bot

| Commande | Usage |
|----------|-------|
| `/delphi_create` | Lance une session (facilitateur) |
| `/delphi_respond session_id:N` | Répondre au tour en cours (fallback si le bouton DM ne marche plus, ex. après redémarrage du bot) |
| `/delphi_status session_id:N` | État d'une session |
| `/delphi_close_round session_id:N` | Force la clôture du tour (facilitateur) |
| `/delphi_abort session_id:N` | Annule la session (facilitateur) |

### Exemples

```
/delphi_create
  question: Combien de jours-homme pour livrer la refonte du back-office ?
  panel: @alice @bob @charlie @diana
  type: Numérique (estimation chiffrée)
  rounds: 3
```

```
/delphi_create
  question: Quel marché prioriser au S2 ?
  panel: @alice @bob @charlie
  type: Choix parmi options
  rounds: 2
  options: France|Allemagne|Espagne|Italie
```

---

## Anonymat & sécurité

- **Côté panel** : personne ne voit qui a répondu quoi. Les synthèses ne contiennent qu'agrégats statistiques et justifications dépersonnalisées.
- **Côté serveur** : la base SQLite (`data/delphi.db` sur le NAS) contient le `user_id` de chaque réponse. C'est nécessaire pour empêcher le double-vote et suivre qui n'a pas encore répondu. Quiconque a un accès SSH/admin au NAS peut donc techniquement remonter aux votes individuels.
- **Réseau** : aucun port n'est exposé. Le bot fait uniquement des connexions sortantes vers les serveurs Discord. Le NAS reste invisible depuis Internet pour ce service.
- **Backup** : la base est dans `./data/`, à inclure dans ta stratégie de sauvegarde habituelle (Hyper Data Protector, snapshots, etc.).

---

## Limitations connues

- **Pas de vues persistantes** : si le bot redémarre, le bouton « Répondre » des DMs en cours cesse de marcher. Fallback : `/delphi_respond`.
- **Pas de timeout automatique par tour** : si un panéliste ne répond jamais, clôturer manuellement avec `/delphi_close_round`.
- **Pas de questions texte libre** : pour ajouter ce mode, brancher un LLM (API Anthropic par exemple) sur les justifications pour les résumer.
- **Pas d'export CSV/JSON** des sessions.
- **Une session = une question** : pour un questionnaire à plusieurs items, lancer plusieurs sessions en parallèle.

---

## Structure du repo

```
delphi-bot/
├── bot.py                  # Code du bot
├── requirements.txt        # Dépendances Python
├── Dockerfile              # Build de l'image
├── docker-compose.yml      # Orchestration
├── .env.example            # Modèle de config (à copier en .env)
├── .gitignore              # Exclut .env, data/, __pycache__
├── update.sh               # Script de mise à jour côté QNAP
└── README.md               # Ce fichier
```

Sur le NAS après déploiement, s'ajoutent :
```
├── .env                    # Token Discord (jamais commit)
└── data/
    └── delphi.db           # Base SQLite (jamais commit)
```
