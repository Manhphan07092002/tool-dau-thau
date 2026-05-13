#!/bin/bash
echo "=============================================="
echo " CAI DAT MOI TRUONG TREO BOT TREN UBUNTU"
echo "=============================================="

# 1. Update system & install Python
echo "[1/3] Cap nhat he thong & cai dat Python3..."
sudo apt-get update -y
sudo apt-get install -y python3 python3-pip python3-venv wget curl unzip

# 2. Install Google Chrome (Required for Selenium)
echo "[2/3] Cai dat Google Chrome..."
wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | sudo apt-key add -
sudo sh -c 'echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list'
sudo apt-get update -y
sudo apt-get install -y google-chrome-stable

# 3. Install Python requirements
echo "[3/3] Cai dat thu vien Python..."
pip3 install -r requirements.txt --break-system-packages

echo "=============================================="
echo " CAI DAT HOAN TAT!"
echo "=============================================="
echo "Cach su dung:"
echo "1. Chay ngay lap tuc 1 lan: python3 run_headless.py --now"
echo "2. Chay che do treo (Scheduler): python3 run_headless.py"
echo ""
echo "De treo an tren server khong bi tat khi dong SSH, hay dung lenh:"
echo "nohup python3 run_headless.py > bot.log 2>&1 &"
echo "=============================================="
