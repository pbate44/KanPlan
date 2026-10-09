<p align="center">
  <img src="docs/banner.svg" alt="KanPlan" width="720">
</p>

<p align="center">
  <b>A self-hosted kanban board with an AI assistant that can help you plan and create tasks.</b><br>
  Runs on your machine with a local LLM, or connects to any OpenAI-compatible API.
</p>

<p align="center">
  <a href="https://github.com/pbate44/KanPlan/actions/workflows/tests.yml"><img src="https://img.shields.io/github/actions/workflow/status/pbate44/KanPlan/tests.yml?branch=main&label=tests&style=flat-square&color=0c66e4" alt="Tests"></a>
  <img src="https://img.shields.io/badge/python-3.12+-579dff?style=flat-square&logo=python&logoColor=white" alt="Python 3.12+">
  <img src="https://img.shields.io/badge/django-5.2-1d7afc?style=flat-square&logo=django&logoColor=white" alt="Django 5.2">
  <a href="https://github.com/pbate44/KanPlan/pkgs/container/kanplan"><img src="https://img.shields.io/badge/docker-ghcr.io-388bff?style=flat-square&logo=docker&logoColor=white" alt="Docker image"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/licence-MIT-0055cc?style=flat-square" alt="MIT licence"></a>
</p>

<p align="center">
  <a href="#-quick-start">Quick start</a> ·
  <a href="#-board-assistant">Board assistant</a> ·
  <a href="#-ai-setup">AI setup</a> ·
  <a href="#-contributing">Contributing</a>
</p>

---

## ✨ Features

| | |
|---|---|
| 🗂️ **Kanban boards** | Columns, swimlanes, drag-and-drop cards, priorities and colour coding |
| 📝 **Task Cards** | Descriptions, subtasks, a running work log and file attachments (images, PDF, Word) |
| 🤖 **Board Agent** | Chat with a whole board and have it create, move and delete cards for you |
| 💬 **Card chat** | Ask about one card, its log and its attachments; chats are saved as sessions |
| 🔌 **Bring your own model** | Ollama, LM Studio, OpenRouter or any OpenAI-compatible API, chosen per user |
| 📄 **PDF export** | Export a card's work log as a PDF |
| 🔒 **Local by default** | SQLite, no external services, light and dark themes |

---

## 🤖 Board Agent

Open a board and click **Board Assistant** in the top bar. The panel slides in beside the board, so you can watch the cards change while you chat.

The assistant sees the board's columns, swimlanes and card titles, and can use four tools:

| Tool | What it does |
|---|---|
| 🔍 `get_card_details` | Reads a card's description, subtasks and work log before answering |
| ➕ `create_card` | Adds a card to any column and swimlane, with a description and subtasks |
| ↔️ `move_card` | Moves a card to another column or swimlane |
| 🗑️ `delete_cards` | Asks to delete cards. **Nothing is deleted until you click Confirm** |

Try things like:

> *"Break the 'Launch website' card into smaller cards in To Do."*
> *"Move everything about the API into In Progress."*
> *"Which cards have no subtasks yet?"*

Every change shows up in the chat as it happens and is written to the card's work log. Chats are saved per board, so you can come back to an earlier session from the history button.

> [!NOTE]
> The board assistant needs a model that supports **tool calling**. Most current models do; with Ollama, try `llama3.2` or `qwen2.5`.

---

## 🚀 Quick start

| Option | You need | Notes |
|---|---|---|
| **1. Script** | [git](https://git-scm.com) | The script offers to install [uv](https://docs.astral.sh/uv), which downloads Python 3.12+ if needed |
| **2. Docker** | [Docker](https://docs.docker.com/get-docker/) | PDF export works out of the box |
| **3. Manual** | git, [uv](https://docs.astral.sh/uv) | |
| *Optional, any option* | [Ollama](https://ollama.com) or an API key | For the AI features, see [AI setup](#-ai-setup) |
| *Optional, script/manual* | [WeasyPrint's system libraries](https://doc.courtbouillon.org/weasyprint/stable/first_steps.html#installation) | Only for PDF export, e.g. `brew install pango` on macOS |

Once it's running, open **[http://localhost:8000](http://localhost:8000)**.

### Option 1: Script (recommended)

```bash
git clone https://github.com/pbate44/KanPlan.git
cd KanPlan
./start.sh          # Windows: double-click start.bat
```

The script installs everything, offers to create your account on first run and opens your browser. Re-run it any time to start KanPlan; finished steps are skipped. Use `PORT=9000 ./start.sh` for a different port.

### Option 2: Docker

```bash
docker run -d --name kanplan -p 8000:8000 -v kanplan-data:/data \
  --add-host=host.docker.internal:host-gateway ghcr.io/pbate44/kanplan
```

Or, from a clone: `docker compose up -d`. Data goes in `./data` and settings are read from `.env`. To update, run `git pull && docker compose up -d --build`.

Sign up in the browser, or set `DJANGO_SUPERUSER_USERNAME` and `DJANGO_SUPERUSER_PASSWORD` to create an account on first start. Pass [AI settings](#-ai-setup) with `-e`, e.g. `-e OPENROUTER_API_KEY=your-key`. To reach KanPlan from other devices, add their hostname or IP to `ALLOWED_HOSTS` (keep `localhost` in the list).

### Option 3: Manual

```bash
git clone https://github.com/pbate44/KanPlan.git
cd KanPlan
uv run python manage.py migrate
uv run python manage.py runserver
```

You don't need a database server or a config file. Data is stored in `db.sqlite3`, and a secret key is generated on first run. Copy `.env.example` to `.env` to change settings.

---

## 🧠 AI setup

KanPlan works with any OpenAI-compatible API. Each user can pick a connection in **Settings → AI Assistant** and check it with the **Test** button. Until they do, the server default from `.env` is used (the start script creates `.env` from `.env.example` on first run). Restart the app after changing `.env`.

| Provider | Setup |
|---|---|
| 🦙 **Ollama** (local, default) | Install [Ollama](https://ollama.com) and pull a model, e.g. `ollama pull llama3.2`. No config needed. |
| 🖥️ **LM Studio** (local) | Start its server, then set `AI_BASE_URL=http://localhost:1234/v1` |
| 🌐 **OpenRouter** (hosted) | Set `OPENROUTER_API_KEY=your-key` |
| ⚙️ **Other** (OpenAI, etc.) | Set `AI_BASE_URL` and `AI_API_KEY` |

Each user picks a model from the server's list in **Settings → AI Model** (OpenRouter models are labelled free or paid). Set `AI_MODEL` to choose the default. Web search in the chats is only available with OpenRouter.

Small local models have short context windows, so answers about cards with long logs or large attachments may miss details.

**Docker:** the container reaches Ollama or LM Studio on your machine through `host.docker.internal` automatically. For LM Studio, use `http://host.docker.internal:1234/v1`. On Linux, Ollama only listens on `127.0.0.1` by default, so start it with `OLLAMA_HOST=0.0.0.0` to let the container reach it.

---

## 🧱 Tech stack

| Layer | Technology |
|---|---|
| Backend | Django 5.2, SQLite |
| Frontend | Vanilla JS, jQuery, Bootstrap |
| AI | OpenAI Python SDK against any OpenAI-compatible server |

```
KanPlan/
├── app/
│   ├── views/          # One file per feature area (board, card, ai, board_ai, auth…)
│   ├── services/       # Business logic: AI providers, board assistant, card changes
│   ├── models.py       # Board → Column → Card, Swimlane, chats, attachments
│   ├── templates/      # Django HTML templates
│   └── static/         # CSS and vanilla JS
├── kanplan/
│   ├── settings.py     # All config, read from environment variables
│   └── urls.py
├── tests/              # pytest suite
├── .env.example        # Optional overrides (copy to .env)
├── pyproject.toml      # Dependencies (managed with uv)
├── Dockerfile / docker-compose.yml
└── start.sh / start.bat
```

---

## 🤝 Contributing

Pull requests are welcome. For major changes, please open an issue first.

Run `uv sync` to install everything, including dev tools, and `uv run pytest` to run the tests.

1. Fork the repo
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Commit your changes
4. Push and open a PR

---

## ⚖️ Disclaimer

KanPlan is not affiliated with, endorsed by, or connected to any AI provider. The AI features use whichever model provider you configure.

## 📜 Licence

[MIT](LICENSE) © Patrick Bateson
