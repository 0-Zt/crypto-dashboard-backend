#!/usr/bin/env bash

# Download and install ta-lib
wget http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz
tar -xvzf ta-lib-0.4.0-src.tar.gz
cd ta-lib/
./configure --prefix=$HOME/.local
make
make install
cd ..
rm -rf ta-lib-0.4.0-src.tar.gz ta-lib/

# Set TA_LIBRARY_PATH and TA_INCLUDE_PATH
export TA_LIBRARY_PATH=$HOME/.local/lib
export TA_INCLUDE_PATH=$HOME/.local/include

# Install Python dependencies
pip install --user -r requirements.txt