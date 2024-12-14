#!/usr/bin/env bash
# Install TA-Lib
wget http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz
tar -xvzf ta-lib-0.4.0-src.tar.gz
cd ta-lib/
./configure --prefix=/usr
make
make install
cd ..
rm -rf ta-lib-0.4.0-src.tar.gz ta-lib/
# Install Python dependencies
pip install -r requirements.txt