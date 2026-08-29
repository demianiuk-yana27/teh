#!/usr/bin/env bash
set -o errexit

# Оновлюємо менеджери пакетів і ставимо Chromium та його залежності
apt-get update && apt-get install -y \
    chromium-browser \
    chromium-chromedriver

pip install -r requirements.txt
