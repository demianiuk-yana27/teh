#!/usr/bin/env bash
set -o errexit

STORAGE_DIR=/opt/render/project/.render

if [[ ! -d $STORAGE_DIR/chrome ]]; then
  echo "...Downloading Chrome"
  mkdir -p $STORAGE_DIR/chrome
  cd $STORAGE_DIR/chrome
  wget -q -P ./ https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
  dpkg -x ./google-chrome-stable_current_amd64.deb $STORAGE_DIR/chrome
  rm ./google-chrome-stable_current_amd64.deb
  cd $HOME/project/src
else
  echo "...Using Chrome from cache"
fi

CHROME_BIN="$STORAGE_DIR/chrome/opt/google/chrome/google-chrome"
CHROME_VERSION=$("$CHROME_BIN" --version | grep -oP '\d+\.\d+\.\d+\.\d+')
echo "Chrome version: $CHROME_VERSION"

if [[ ! -f $STORAGE_DIR/chromedriver/chromedriver ]]; then
  echo "...Downloading Chromedriver"
  mkdir -p $STORAGE_DIR/chromedriver
  cd $STORAGE_DIR/chromedriver
  wget -q "https://storage.googleapis.com/chrome-for-testing-public/${CHROME_VERSION}/linux64/chromedriver-linux64.zip"
  unzip -q chromedriver-linux64.zip
  mv chromedriver-linux64/chromedriver .
  chmod +x chromedriver
  rm -r chromedriver-linux64 chromedriver-linux64.zip
  cd $HOME/project/src
else
  echo "...Using Chromedriver from cache"
fi

pip install -r requirements.txt
