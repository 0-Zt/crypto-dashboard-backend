#!/usr/bin/env bash

# Install system dependencies
apt-get update
apt-get install -y wget build-essential

# Install TA-Lib
apt-get install -y ta-lib

# Install Python dependencies
pip install -r requirements.txt