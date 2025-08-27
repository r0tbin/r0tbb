#!/bin/bash

# Post-installation script for Bug Bounty Tool by r0tbin
# Validates external tool dependencies and provides installation guidance

echo "🔧 Bug Bounty Tool - Dependency Validation"
echo "=========================================="
echo

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Tools to check
declare -A TOOLS=(
    ["subfinder"]="Subdomain enumeration"
    ["httpx"]="HTTP probing and analysis"
    ["katana"]="Web crawling and endpoint discovery"
    ["nuclei"]="Vulnerability scanning"
    ["naabu"]="Port scanning"
    ["dnsx"]="DNS resolution and enumeration"
    ["gowitness"]="Screenshot capture"
    ["webanalyze"]="Technology detection"
    ["jq"]="JSON processing"
    ["curl"]="HTTP requests"
)

# Optional tools
declare -A OPTIONAL_TOOLS=(
    ["paramspider"]="Parameter discovery"
    ["amass"]="Additional subdomain enumeration"
    ["s3scanner"]="S3 bucket discovery"
    ["git"]="Version control (for tool updates)"
    ["go"]="Go language (for installing Go tools)"
    ["python3"]="Python 3 (for scripts)"
)

missing_tools=()
optional_missing=()

echo "Checking required tools..."
echo "-------------------------"

# Check required tools
for tool in "${!TOOLS[@]}"; do
    if command -v "$tool" &> /dev/null; then
        version=$(timeout 10s $tool -version 2>/dev/null | head -1 || echo "unknown")
        echo -e "${GREEN}✓${NC} $tool - ${TOOLS[$tool]} ($version)"
    else
        echo -e "${RED}✗${NC} $tool - ${TOOLS[$tool]} (not found)"
        missing_tools+=("$tool")
    fi
done

echo
echo "Checking optional tools..."
echo "-------------------------"

# Check optional tools
for tool in "${!OPTIONAL_TOOLS[@]}"; do
    if command -v "$tool" &> /dev/null; then
        version=$(timeout 10s $tool --version 2>/dev/null | head -1 || echo "unknown")
        echo -e "${GREEN}✓${NC} $tool - ${OPTIONAL_TOOLS[$tool]} ($version)"
    else
        echo -e "${YELLOW}○${NC} $tool - ${OPTIONAL_TOOLS[$tool]} (optional, not found)"
        optional_missing+=("$tool")
    fi
done

echo
echo "Summary"
echo "-------"

if [ ${#missing_tools[@]} -eq 0 ]; then
    echo -e "${GREEN}✅ All required tools are installed!${NC}"
else
    echo -e "${RED}❌ Missing required tools: ${missing_tools[*]}${NC}"
fi

if [ ${#optional_missing[@]} -gt 0 ]; then
    echo -e "${YELLOW}⚠️  Missing optional tools: ${optional_missing[*]}${NC}"
fi

echo
echo "Installation Guide"
echo "=================="

if [ ${#missing_tools[@]} -gt 0 ] || [ ${#optional_missing[@]} -gt 0 ]; then
    echo "To install missing tools, you can use the following commands:"
    echo
    
    # Go tools installation
    if [[ " ${missing_tools[*]} ${optional_missing[*]} " =~ " subfinder " ]] || 
       [[ " ${missing_tools[*]} ${optional_missing[*]} " =~ " httpx " ]] || 
       [[ " ${missing_tools[*]} ${optional_missing[*]} " =~ " katana " ]] || 
       [[ " ${missing_tools[*]} ${optional_missing[*]} " =~ " nuclei " ]] || 
       [[ " ${missing_tools[*]} ${optional_missing[*]} " =~ " naabu " ]] || 
       [[ " ${missing_tools[*]} ${optional_missing[*]} " =~ " dnsx " ]]; then
        
        echo -e "${BLUE}Go Tools (ProjectDiscovery):${NC}"
        echo "go install -v github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest"
        echo "go install -v github.com/projectdiscovery/httpx/cmd/httpx@latest"
        echo "go install -v github.com/projectdiscovery/katana/cmd/katana@latest"
        echo "go install -v github.com/projectdiscovery/nuclei/v2/cmd/nuclei@latest"
        echo "go install -v github.com/projectdiscovery/naabu/v2/cmd/naabu@latest"
        echo "go install -v github.com/projectdiscovery/dnsx/cmd/dnsx@latest"
        echo
    fi
    
    # Other tools
    if [[ " ${missing_tools[*]} ${optional_missing[*]} " =~ " gowitness " ]]; then
        echo -e "${BLUE}gowitness:${NC}"
        echo "go install github.com/sensepost/gowitness@latest"
        echo
    fi
    
    if [[ " ${missing_tools[*]} ${optional_missing[*]} " =~ " webanalyze " ]]; then
        echo -e "${BLUE}webanalyze:${NC}"
        echo "go install github.com/rverton/webanalyze/cmd/webanalyze@latest"
        echo
    fi
    
    if [[ " ${missing_tools[*]} ${optional_missing[*]} " =~ " jq " ]]; then
        echo -e "${BLUE}jq (JSON processor):${NC}"
        echo "# Ubuntu/Debian: sudo apt install jq"
        echo "# macOS: brew install jq"
        echo "# Windows: choco install jq"
        echo
    fi
    
    if [[ " ${missing_tools[*]} ${optional_missing[*]} " =~ " amass " ]]; then
        echo -e "${BLUE}amass:${NC}"
        echo "go install -v github.com/OWASP/Amass/v3/...@master"
        echo
    fi
    
    echo -e "${YELLOW}Note: Make sure your Go bin directory is in your PATH${NC}"
    echo "Add this to your ~/.bashrc or ~/.zshrc:"
    echo "export PATH=\$PATH:\$(go env GOPATH)/bin"
    echo
fi

echo "Configuration"
echo "============="
echo "1. Copy .env.example to .env and configure your Telegram credentials"
echo "2. Edit templates/tasks.sample.yaml to customize your pipeline"
echo "3. Run 'bb init <target>' to initialize a new target"
echo
echo -e "${GREEN}🚀 Ready to hunt bugs! Happy hacking from r0tbin${NC}"

# Exit with error code if required tools are missing
if [ ${#missing_tools[@]} -gt 0 ]; then
    exit 1
else
    exit 0
fi