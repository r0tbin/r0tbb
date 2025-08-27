#!/bin/bash

# Global Installation Script for r0tbb Bug Bounty Tool
# Installs globally without requiring virtual environments

set -e

echo "🎯 r0tbb - Global Installation"
echo "=============================="
echo "Created by r0tbin"
echo

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Check if running as root
if [[ $EUID -eq 0 ]]; then
   echo -e "${YELLOW}⚠️  Running as root - will install system-wide${NC}"
   INSTALL_FLAG="--break-system-packages"
else
   echo -e "${BLUE}📦 Installing for current user${NC}"
   INSTALL_FLAG="--user"
fi

echo -e "${BLUE}📦 Step 1: System dependencies${NC}"

# Install system packages
if command -v apt-get &> /dev/null; then
    sudo apt-get update
    sudo apt-get install -y python3 python3-pip curl wget jq git build-essential
elif command -v yum &> /dev/null; then
    sudo yum install -y python3 python3-pip curl wget jq git gcc
elif command -v pacman &> /dev/null; then
    sudo pacman -S python python-pip curl wget jq git base-devel
fi

echo -e "${BLUE}📦 Step 2: Python packages${NC}"

# Upgrade pip
python3 -m pip install --upgrade pip $INSTALL_FLAG

# Install dependencies globally
echo "Installing r0tbb dependencies..."
python3 -m pip install $INSTALL_FLAG typer rich python-dotenv pyyaml jinja2 peewee psutil jsonpath-ng python-telegram-bot aiofiles

# Install the tool
echo "Installing r0tbb..."
python3 -m pip install $INSTALL_FLAG -e .

echo -e "${GREEN}✅ r0tbb installed globally${NC}"

echo -e "${BLUE}📦 Step 3: PATH verification${NC}"

# Check if in PATH
if command -v r0tbb &> /dev/null; then
    echo -e "${GREEN}✅ r0tbb command available${NC}"
else
    echo -e "${YELLOW}⚠️  r0tbb not in PATH${NC}"
    
    # Add user bin to PATH if needed
    if [[ $INSTALL_FLAG == "--user" ]]; then
        USER_BIN=$(python3 -m site --user-base)/bin
        echo -e "${BLUE}Add this to your ~/.bashrc or ~/.zshrc:${NC}"
        echo "export PATH=\$PATH:$USER_BIN"
        
        # Try to add automatically
        if [[ -f ~/.bashrc ]]; then
            echo "export PATH=\$PATH:$USER_BIN" >> ~/.bashrc
            echo -e "${GREEN}✅ Added to ~/.bashrc${NC}"
        fi
    fi
fi

echo -e "${BLUE}📦 Step 4: Configuration${NC}"

# Create configuration
if [ ! -f ".env" ]; then
    cp .env.example .env 2>/dev/null || echo "BOT_TOKEN=your_token_here" > .env
    echo -e "${YELLOW}⚠️  Edit .env with your Telegram credentials${NC}"
fi

# Create work directory
mkdir -p bug-bounty

echo -e "${BLUE}📦 Step 5: External tools (optional)${NC}"

# Install Go tools if Go is available
if command -v go &> /dev/null; then
    echo "Installing security tools..."
    go install -v github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest
    go install -v github.com/projectdiscovery/httpx/cmd/httpx@latest
    go install -v github.com/projectdiscovery/katana/cmd/katana@latest
    go install -v github.com/projectdiscovery/nuclei/v2/cmd/nuclei@latest
    go install -v github.com/projectdiscovery/naabu/v2/cmd/naabu@latest
    go install -v github.com/projectdiscovery/dnsx/cmd/dnsx@latest
    echo -e "${GREEN}✅ Security tools installed${NC}"
else
    echo -e "${YELLOW}⚠️  Go not found - external tools need manual installation${NC}"
fi

echo -e "${BLUE}📦 Step 6: Testing${NC}"

# Test installation
echo "Testing r0tbb..."
if command -v r0tbb &> /dev/null; then
    r0tbb --help > /dev/null && echo -e "${GREEN}✅ r0tbb working${NC}"
else
    echo -e "${RED}❌ r0tbb command not found${NC}"
    echo "Try: source ~/.bashrc or restart your terminal"
fi

echo
echo -e "${GREEN}🎉 Global installation completed!${NC}"
echo
echo "Usage:"
echo "  r0tbb init example.com"
echo "  r0tbb run example.com" 
echo "  r0tbb status example.com"
echo "  r0tbb bot"
echo
echo -e "${BLUE}📚 Read DEPLOYMENT.md for detailed instructions${NC}"
echo -e "${GREEN}🚀 Happy bug hunting! - r0tbin${NC}"