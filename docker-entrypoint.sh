#!/bin/sh
set -eu

chown -R bot:bot /app/sessions
exec gosu bot "$@"