# Bug Bounty Tool by r0tbin
# Makefile for development and deployment

.PHONY: install dev test clean lint format setup bot

install:
	pip install -r requirements.txt

dev:
	pip install -r requirements.txt
	pip install -e .

test:
	python -m pytest tests/ -v

clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf build/ dist/

lint:
	flake8 bugbounty/
	black --check bugbounty/

format:
	black bugbounty/
	isort bugbounty/

setup:
	cp .env.example .env
	mkdir -p bug-bounty
	mkdir -p templates
	mkdir -p scripts
	echo "Setup complete! Edit .env with your Telegram credentials."

bot:
	python -m bugbounty.cli bot

run-example:
	python -m bugbounty.cli run example.com

# Development helpers
install-tools:
	@echo "Installing external tools..."
	@echo "Please install these tools manually:"
	@echo "- subfinder: go install -v github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest"
	@echo "- httpx: go install -v github.com/projectdiscovery/httpx/cmd/httpx@latest"
	@echo "- katana: go install github.com/projectdiscovery/katana/cmd/katana@latest"

validate-tools:
	@echo "Validating external tools..."
	@which subfinder || echo "WARNING: subfinder not found"
	@which httpx || echo "WARNING: httpx not found"
	@which katana || echo "WARNING: katana not found"