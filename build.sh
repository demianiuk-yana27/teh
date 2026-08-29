#!/usr/bin/env bash
# оновлення та встановлення системного браузера та залежностей
apt-get update && apt-get install -y chromium-browser chromium-chromedriver
pip install -r requirements.txt
