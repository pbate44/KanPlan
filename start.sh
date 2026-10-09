#!/usr/bin/env sh
# Install (if needed) and start KanPlan. Safe to re-run: finished steps are skipped.
set -e
cd "$(dirname "$0")"

# Always use this project's .venv, even if another virtualenv is active.
unset VIRTUAL_ENV

PORT="${PORT:-8000}"
URL="http://localhost:$PORT"

if ! command -v uv >/dev/null 2>&1; then
    if [ -x "$HOME/.local/bin/uv" ]; then
        PATH="$HOME/.local/bin:$PATH"
    else
        printf "KanPlan uses uv (https://docs.astral.sh/uv) to install Python and its dependencies.\n"
        printf "Install uv now? [Y/n] "
        read -r answer
        case "$answer" in
            [nN]*) echo "Install uv yourself, then re-run ./start.sh"; exit 1 ;;
        esac
        curl -LsSf https://astral.sh/uv/install.sh | sh
        PATH="$HOME/.local/bin:$PATH"
    fi
fi

# --inexact keeps dev tools installed for contributors who run this script.
echo "Installing dependencies..."
uv sync --no-dev --inexact --quiet

if [ ! -f .env ]; then
    cp .env.example .env
    echo "Created .env (AI uses a local Ollama by default; see .env for other providers)."
fi

uv run --no-sync python manage.py migrate --verbosity 0

uv run --no-sync python manage.py setup_first_user

# Open the browser once the server responds
(
    for _ in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do
        if curl -s -o /dev/null "$URL"; then
            if command -v open >/dev/null 2>&1; then open "$URL"
            elif command -v xdg-open >/dev/null 2>&1; then xdg-open "$URL" >/dev/null 2>&1
            fi
            break
        fi
        sleep 1
    done
) &

echo "Starting KanPlan at $URL (press Ctrl+C to stop)"
exec uv run --no-sync python manage.py runserver "$PORT"
