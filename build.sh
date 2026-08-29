#!/usr/bin/env bash
apt-get update && apt-get install -y wget curl unzip libxi6 libgconf-2-4 libnss3 chromium-browser chromium-chromedriver
pip install -r requirements.txt
