# r0tbb Telegram Bot Setup

## 🔒 Security First

**IMPORTANTE**: Nunca subas credenciales al repositorio. El bot ahora requiere variables de entorno.

## 🚀 Quick Setup

### 1. Configurar Variables de Entorno

```bash
# Opción 1: Exportar en la terminal
export BOT_TOKEN="tu_token_aqui"
export CHAT_ID="tu_chat_id_aqui"

# Opción 2: Crear archivo .env (recomendado)
echo "BOT_TOKEN=tu_token_aqui" > .env
echo "CHAT_ID=tu_chat_id_aqui" >> .env
```

### 2. Obtener Credenciales

#### Bot Token:
1. Ve a Telegram y busca `@BotFather`
2. Envía `/newbot`
3. Sigue las instrucciones
4. Copia el token que te da

#### Chat ID:
1. Ve a Telegram y busca `@userinfobot`
2. Envía cualquier mensaje
3. Copia tu Chat ID

### 3. Ejecutar el Bot

```bash
# Con variables exportadas
python3 simple_bot.py

# Con archivo .env
source .env && python3 simple_bot.py
```

## 🔧 Configuración Permanente

Para no tener que configurar las variables cada vez:

```bash
# Agregar al ~/.bashrc o ~/.zshrc
echo 'export BOT_TOKEN="tu_token_aqui"' >> ~/.bashrc
echo 'export CHAT_ID="tu_chat_id_aqui"' >> ~/.bashrc
source ~/.bashrc
```

## ✅ Verificación

El bot mostrará:
- ✅ Si las variables están configuradas correctamente
- ❌ Si faltan variables (con instrucciones para configurarlas)

## 🛡️ Seguridad

- ✅ `.env` está en `.gitignore`
- ✅ No hay credenciales hardcodeadas en el código
- ✅ El bot verifica las variables antes de ejecutar
- ✅ Solo responde al chat_id autorizado

## 🚨 Troubleshooting

Si ves errores de configuración:
1. Verifica que las variables estén exportadas: `echo $BOT_TOKEN`
2. Verifica el formato del token: debe ser `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`
3. Verifica el chat_id: debe ser un número
