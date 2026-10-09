#!/bin/sh
set -e

if [ "$(id -u)" = "0" ]; then
    mkdir -p "$DATA_DIR"
    find "$DATA_DIR" ! -user kanplan -exec chown kanplan:kanplan {} + \
        || echo "Warning: could not change ownership of $DATA_DIR"
    export HOME=/home/kanplan
    exec setpriv --reuid=kanplan --regid=kanplan --init-groups "$0" "$@"
fi

python manage.py migrate --noinput --verbosity 0
python manage.py setup_first_user --from-env

exec "$@"
