#!/bin/bash

# Bug Bounty Tool - Quick Install Script
# Created by r0tbin

set -e

echo "🎯 Bug Bounty Automation Tool - Quick Install"
echo "=============================================="
echo "Created by r0tbin"
echo

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Check if running on Linux
if [[ "$OSTYPE" != "linux-gnu"* ]]; then
    echo -e "${RED}❌ This tool is designed for Linux systems${NC}"
    exit 1
fi

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python 3 is required but not installed${NC}"
    echo "Install with: sudo apt install python3 python3-pip"
    exit 1
fi

# Check if pip is installed
if ! command -v pip3 &> /dev/null && ! python3 -m pip --version &> /dev/null; then
    echo -e "${RED}❌ pip is required but not installed${NC}"
    echo "Install with: sudo apt install python3-pip"
    exit 1
fi

echo -e "${BLUE}📦 Installing Python dependencies...${NC}"

# Create virtual environment
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Upgrade pip
python -m pip install --upgrade pip

# Install requirements
pip install -r requirements.txt

# Install the package
pip install -e .

echo -e "${GREEN}✅ Python package installed successfully${NC}"

# Check if Go is installed
if ! command -v go &> /dev/null; then
    echo -e "${YELLOW}⚠️  Go is not installed - external tools will need manual installation${NC}"
    echo "Install Go with:"
    echo "wget https://go.dev/dl/go1.21.5.linux-amd64.tar.gz"
    echo "sudo tar -C /usr/local -xzf go1.21.5.linux-amd64.tar.gz"
    echo "echo 'export PATH=\$PATH:/usr/local/go/bin:\$HOME/go/bin' >> ~/.bashrc"
    echo "source ~/.bashrc"
else
    echo -e "${BLUE}🔧 Installing external security tools...${NC}"
    
    # Install Go tools
    echo "Installing subfinder..."
    go install -v github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest
    
    echo "Installing httpx..."
    go install -v github.com/projectdiscovery/httpx/cmd/httpx@latest
    
    echo "Installing katana..."
    go install -v github.com/projectdiscovery/katana/cmd/katana@latest
    
    echo "Installing nuclei..."
    go install -v github.com/projectdiscovery/nuclei/v2/cmd/nuclei@latest
    
    echo "Installing naabu..."
    go install -v github.com/projectdiscovery/naabu/v2/cmd/naabu@latest
    
    echo "Installing dnsx..."
    go install -v github.com/projectdiscovery/dnsx/cmd/dnsx@latest
    
    echo "Installing gowitness..."
    go install github.com/sensepost/gowitness@latest
    
    echo "Installing webanalyze..."
    go install github.com/rverton/webanalyze/cmd/webanalyze@latest
    
    echo -e "${GREEN}✅ External tools installed${NC}"
fi

# Create configuration file
if [ ! -f ".env" ]; then
    echo -e "${BLUE}📝 Creating configuration file...${NC}"
    cp .env.example .env
    echo -e "${YELLOW}⚠️  Edit .env file with your Telegram credentials${NC}"
fi

# Create bug-bounty directory
mkdir -p bug-bounty

# Run validation script
if [ -x "scripts/postinstall.sh" ]; then
    echo -e "${BLUE}🔍 Validating installation...${NC}"
    ./scripts/postinstall.sh
fi

echo
echo -e "${GREEN}🎉 Installation completed successfully!${NC}"
echo
echo "Next steps:"
echo "1. Edit .env file with your Telegram credentials"
echo "2. Run: source venv/bin/activate"
echo "3. Test: bb --help"
echo "4. Initialize a target: bb init example.com"
echo "5. Run pipeline: bb run example.com"
echo "6. Start bot: bb bot"
echo
echo -e "${BLUE}📚 Read DEPLOYMENT.md for detailed instructions${NC}"
echo -e "${GREEN}🚀 Happy bug hunting! - r0tbin${NC}"