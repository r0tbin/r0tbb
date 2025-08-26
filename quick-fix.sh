#!/bin/bash

# Quick fix script for Linux deployment issues
# Created by r0tbin

echo "Fixing Linux deployment issues..."

# Fix psutil conflict
echo "Fixing psutil conflict..."
pip uninstall -y psutil || true
pip install psutil

# Fix telegram bot dependency
echo "Installing python-telegram-bot..."
pip install python-telegram-bot

# Create .env from example
echo "Creating .env file..."
cp .env.example .env || echo "Warning: .env.example not found"

# Install remaining dependencies
echo "Installing all requirements..."
pip install -r requirements.txt

# Install the tool
echo "Installing bugbounty tool..."
pip install -e .

echo "✅ Fixed! Try running: python3 -m bugbounty.cli --help"