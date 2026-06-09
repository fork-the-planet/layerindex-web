#!/bin/bash
python3 ${APP_DIR:-/opt}/layerindex/manage.py migrate "$@"
