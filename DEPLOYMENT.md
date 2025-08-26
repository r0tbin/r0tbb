# Bug Bounty Tool - Linux Deployment Guide

**Created by r0tbin**

Esta guía te ayuda a deployar la herramienta de bug bounty en Linux desde cero.

## 📋 Pre-requisitos

### Sistema base
```bash
# Ubuntu/Debian
sudo apt update && sudo apt install -y python3 python3-pip git curl wget jq

# CentOS/RHEL
sudo yum install -y python3 python3-pip git curl wget epel-release
sudo yum install -y jq

# Arch Linux
sudo pacman -S python python-pip git curl wget jq
```

### Go (para herramientas de seguridad)
```bash
# Descargar e instalar Go
wget https://go.dev/dl/go1.21.5.linux-amd64.tar.gz
sudo tar -C /usr/local -xzf go1.21.5.linux-amd64.tar.gz

# Agregar a PATH
echo 'export PATH=$PATH:/usr/local/go/bin:$HOME/go/bin' >> ~/.bashrc
source ~/.bashrc

# Verificar instalación
go version
```

## 🚀 Instalación

### 1. Clonar/Transferir el proyecto
```bash
# Si tienes el código localmente, cópialo al servidor Linux
# O si está en Git:
# git clone https://github.com/r0tbin/bugbounty-tool.git
cd r0tbb
```

### 2. Instalar dependencias Python
```bash
# Crear entorno virtual (recomendado)
python3 -m venv venv
source venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt

# Instalar la herramienta
pip install -e .
```

### 3. Instalar herramientas externas
```bash
# Ejecutar script de instalación de herramientas
chmod +x scripts/postinstall.sh
./scripts/postinstall.sh

# O instalar manualmente:
go install -v github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest
go install -v github.com/projectdiscovery/httpx/cmd/httpx@latest
go install -v github.com/projectdiscovery/katana/cmd/katana@latest
go install -v github.com/projectdiscovery/nuclei/v2/cmd/nuclei@latest
go install -v github.com/projectdiscovery/naabu/v2/cmd/naabu@latest
go install -v github.com/projectdiscovery/dnsx/cmd/dnsx@latest
go install github.com/sensepost/gowitness@latest
go install github.com/rverton/webanalyze/cmd/webanalyze@latest
```

### 4. Configurar Telegram (opcional)
```bash
# Copiar template de configuración
cp .env.example .env

# Editar con tus credenciales
nano .env
```

Contenido del `.env`:
```bash
# Telegram Configuration
BOT_TOKEN=123456789:ABCDEFghijklmnopqrstuvwxyz123456789
CHAT_ID=123456789

# Directory Configuration
ROOT_DIR=.
WORK_DIR=bug-bounty

# Execution Configuration
CONCURRENCY=2
DEFAULT_TIMEOUT=3600
HARD_KILL_GRACE=10

# Logging
LOG_LEVEL=INFO
MAX_LOG_SIZE=50MB
```

### 5. Crear bot de Telegram

1. **Crear bot:**
   - Habla con @BotFather en Telegram
   - Ejecuta `/newbot`
   - Dale un nombre y username a tu bot
   - Copia el token que te da

2. **Obtener tu Chat ID:**
   ```bash
   # Envía un mensaje a tu bot primero, luego:
   curl "https://api.telegram.org/bot<TU_BOT_TOKEN>/getUpdates"
   # Busca tu chat ID en la respuesta
   ```

## 🧪 Verificación

### Verificar instalación
```bash
# Verificar comando principal
bb --help

# Verificar herramientas externas
./scripts/postinstall.sh

# Verificar configuración
bb list
```

### Primer test
```bash
# Crear estructura inicial
mkdir -p bug-bounty

# Inicializar target de prueba
bb init ejemplo.com

# Verificar estructura creada
ls -la bug-bounty/ejemplo.com/

# Editar pipeline si es necesario
nano bug-bounty/ejemplo.com/tasks.yaml

# Ejecutar pipeline de prueba
bb run ejemplo.com

# Verificar resultados
bb status ejemplo.com
bb summarize ejemplo.com
```

## 🤖 Iniciar Bot de Telegram

```bash
# En una terminal separada o tmux/screen
bb bot

# O ejecutar en background
nohup bb bot > bot.log 2>&1 &
```

### Comandos del bot:
- `/status ejemplo.com` - Ver progreso
- `/resultados ejemplo.com` - Descargar reportes  
- `/tail ejemplo.com` - Ver logs recientes
- `/stop ejemplo.com` - Parar ejecución
- `/top ejemplo.com` - Ver hallazgos principales
- `/list` - Listar todos los targets

## 📁 Estructura de directorios

Después de la instalación tendrás:
```
/home/user/r0tbb/
├── bugbounty/              # Código fuente
├── templates/              # Configuraciones YAML
├── scripts/               # Scripts de instalación
├── bug-bounty/            # Workspace (se crea automáticamente)
│   └── ejemplo.com/       # Directorio por target
│       ├── tasks.yaml     # Pipeline específico
│       ├── progress.json  # Estado rápido
│       ├── run.db        # Base de datos SQLite
│       ├── logs/         # Logs de ejecución
│       ├── outputs/      # Resultados de herramientas
│       └── reports/      # Reportes generados
├── requirements.txt
├── setup.py
└── .env                  # Tu configuración
```

## 🔧 Troubleshooting

### Comando `bb` no encontrado
```bash
# Verificar que esté en PATH
which bb

# Si no está, verificar instalación
pip show bugbounty-tool

# Reinstalar si es necesario
pip install -e .
```

### Herramientas externas faltantes
```bash
# Verificar instalación
./scripts/postinstall.sh

# Agregar Go bin al PATH si falta
echo 'export PATH=$PATH:$HOME/go/bin' >> ~/.bashrc
source ~/.bashrc
```

### Problemas de permisos
```bash
# Dar permisos de ejecución
chmod +x scripts/postinstall.sh
chmod +x bug-bounty/*/logs/*.log
```

### Bot de Telegram no responde
```bash
# Verificar configuración
grep -E "BOT_TOKEN|CHAT_ID" .env

# Verificar conectividad
curl "https://api.telegram.org/bot<TU_TOKEN>/getMe"

# Ver logs del bot
bb bot
```

## 🎯 Workflow típico

```bash
# 1. Inicializar nuevo target
bb init target.com

# 2. Personalizar pipeline (opcional)
nano bug-bounty/target.com/tasks.yaml

# 3. Ejecutar pipeline
bb run target.com

# 4. Monitorear progreso (desde Telegram o CLI)
bb status target.com

# 5. Ver resultados
bb summarize target.com

# 6. Descargar archive
bb zip target.com
```

## 📱 Control remoto vía Telegram

Una vez configurado el bot, puedes controlar todo remotamente:

```
/status target.com     → Ver progreso en tiempo real
/resultados target.com → Descargar summary.md y results.zip  
/tail target.com       → Ver últimas líneas del log
/stop target.com       → Parar ejecución actual
/top target.com        → Ver top 5 hallazgos más jugosos
```

---

**¡Listo para cazar bugs! 🎯**

*Created by r0tbin - Happy hunting!*