# Bug Bounty Automation Tool

> **Created by r0tbin** - A personal terminal-based bug bounty automation tool with Telegram integration.

## Features

- 🎯 **Target-based execution** with isolated workspaces
- 📋 **YAML pipeline configuration** with dependency management
- 💾 **SQLite state persistence** with JSON quick-read
- 🤖 **Telegram bot integration** for remote monitoring
- 🔍 **Heuristic analysis** for finding interesting results
- ⚡ **Concurrent task execution** with timeout control
- 📊 **Progress tracking** with ETA estimation

## Quick Start

1. **Install dependencies:**
   ```bash
   make install
   ```

2. **Setup configuration:**
   ```bash
   make setup
   # Edit .env with your Telegram credentials
   ```

3. **Install external tools:**
   ```bash
   make install-tools
   ```

4. **Initialize a target:**
   ```bash
   python -m bugbounty.cli init example.com
   ```

5. **Run the pipeline:**
   ```bash
   python -m bugbounty.cli run example.com
   ```

6. **Start Telegram bot:**
   ```bash
   python -m bugbounty.cli bot
   ```

## CLI Commands

- `init <target>` - Create target structure and copy sample tasks
- `run <target>` - Execute the pipeline for a target
- `status <target>` - Show current progress
- `summarize <target>` - Generate analysis reports
- `zip <target>` - Create results archive
- `bot` - Start Telegram bot server

## Telegram Commands

- `/status <target>` - Show progress and ETA
- `/resultados <target>` - Get summary and download results
- `/tail <target>` - Show recent log entries
- `/stop <target>` - Pause/cancel execution
- `/top <target>` - Show top findings by heuristics

## Directory Structure

```
bug-bounty/<target>/
├── tasks.yaml           # Pipeline configuration
├── progress.json        # Quick-read status
├── run.db              # SQLite database
├── logs/               # Execution logs
├── outputs/            # Tool outputs
└── reports/            # Generated reports
```

## Configuration

### Tasks Pipeline (`tasks.yaml`)

```yaml
version: 1
concurrency: 2

vars:
  TARGET: "example.com"
  ROOT: "{ROOT}"
  OUT: "{OUT}"

pipeline:
  - name: subfinder
    desc: Subdomain enumeration
    cmd: |
      subfinder -d {TARGET} -all -recursive -silent \
        -o {OUT}/outputs/recon/subfinder.txt
    timeout: 1800

  - name: httpx
    needs: [subfinder]
    cmd: |
      httpx -l {OUT}/outputs/recon/subfinder.txt -cl -sc -title -td -json \
        -o {OUT}/outputs/web/httpx.json
```

### Juicy Filters (`juicy_filters.yaml`)

```yaml
rules:
  - id: secrets
    desc: Possible secrets
    file_globs: ["**/*.js", "**/*.txt", "**/*.log"]
    regex:
      - "AKIA[0-9A-Z]{16}"
      - "(?i)(secret|api[-_]?key|token)[\\s:=\"]{0,5}([A-Za-z0-9_\\-]{16,})"
```

## License

GPL-3.0 - Open source, non-commercial, free for everyone.

## Author

**r0tbin** - Personal bug bounty automation tool.