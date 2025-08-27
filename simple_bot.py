#!/usr/bin/env python3
"""
Bot de Telegram simple y funcional para r0tbb
"""
import os
import requests
import time
import json
import subprocess
import sys
from pathlib import Path

# Cargar variables de entorno desde .env si existe
def load_env_file():
    env_file = Path('.env')
    if env_file.exists():
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key] = value

# Cargar .env
load_env_file()

# Configuración
BOT_TOKEN = os.getenv('BOT_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')

# Verificar configuración
if not BOT_TOKEN:
    print("❌ ERROR: BOT_TOKEN environment variable not set")
    print("   Set it with: export BOT_TOKEN='your_bot_token'")
    sys.exit(1)

if not CHAT_ID:
    print("❌ ERROR: CHAT_ID environment variable not set")
    print("   Set it with: export CHAT_ID='your_chat_id'")
    sys.exit(1)

API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

def send_message(chat_id, text, parse_mode='HTML'):
    """Enviar mensaje a Telegram"""
    url = f"{API_URL}/sendMessage"
    data = {
        'chat_id': chat_id,
        'text': text,
        'parse_mode': parse_mode
    }
    try:
        response = requests.post(url, data=data)
        return response.json()
    except Exception as e:
        print(f"Error sending message: {e}")
        return None

def get_updates(offset=None):
    """Obtener actualizaciones de Telegram"""
    url = f"{API_URL}/getUpdates"
    params = {'timeout': 10}
    if offset:
        params['offset'] = offset
    
    try:
        response = requests.get(url, params=params)
        return response.json()
    except Exception as e:
        print(f"Error getting updates: {e}")
        return None

def run_r0tbb_command(command):
    """Ejecutar comando r0tbb y capturar salida"""
    try:
        env = os.environ.copy()
        env['PATH'] = f"{env.get('PATH', '')}:/home/l0n3/.local/bin:/home/l0n3/go/bin"
        
        # Los comandos r0tbb ahora funcionan globalmente
        result = subprocess.run(
            f"cd /home/l0n3/r0tbb && {command}",
            shell=True,
            capture_output=True,
            text=True,
            timeout=30,
            env=env
        )
        
        if result.returncode == 0:
            return result.stdout
        else:
            return f"Error: {result.stderr}"
    except subprocess.TimeoutExpired:
        return "❌ Command took too long (timeout 30s)"
    except Exception as e:
        return f"❌ Error executing command: {e}"

def process_message(message):
    """Procesar mensaje recibido"""
    if 'text' not in message:
        return
    
    text = message['text']
    chat_id = message['chat']['id']
    
    # Verificar que sea del chat autorizado
    if str(chat_id) != CHAT_ID:
        send_message(chat_id, "❌ Not authorized")
        return
    
    # Procesar comandos
    if text.startswith('/start'):
        response = """🎯 <b>r0tbb Bot - Working!</b>

Hello! I'm the r0tbb bot for Bug Bounty Automation.

<b>📋 Available Commands:</b>
• /start - This message
• /status [target] - Status of a target
• /list - List all targets
• /run [command] - Execute any r0tbb command
• /exec [command] - Execute any shell command (safe)
• /help - Complete help

<b>🚀 Examples:</b>
• <code>/status att</code>
• <code>/list</code>
• <code>/run init example.com</code>
• <code>/run run att</code>

<b>✅ System fully operational!</b>
Created by <b>r0tbin</b> 🔥"""
        
    elif text.startswith('/status'):
        parts = text.split()
        if len(parts) > 1:
            target = parts[1]
            output = run_r0tbb_command(f"r0tbb status {target}")
            response = f"📊 <b>Status of {target}:</b>\n\n<pre>{output}</pre>"
        else:
            output = run_r0tbb_command("r0tbb list")
            response = f"📋 <b>Available targets:</b>\n\n<pre>{output}</pre>"
    
    elif text.startswith('/list'):
        try:
            # List targets directly from the bugbounty directory
            bugbounty_dir = os.getenv('WORK_DIR', "/home/l0n3/bugbounty")
            if os.path.exists(bugbounty_dir):
                targets = [d for d in os.listdir(bugbounty_dir) if os.path.isdir(os.path.join(bugbounty_dir, d))]
                if targets:
                    targets.sort()
                    target_list = "\n".join([f"• {target}" for target in targets])
                    response = f"📋 <b>Available targets ({len(targets)}):</b>\n\n<pre>{target_list}</pre>"
                else:
                    response = "📋 <b>No targets found</b>\n\nNo bug bounty targets have been created yet."
            else:
                response = "❌ <b>Error:</b> Bug bounty directory not found"
        except Exception as e:
            response = f"❌ <b>Error listing targets:</b>\n\n<pre>{str(e)}</pre>"
    
    elif text.startswith('/run'):
        parts = text.split(' ', 1)
        if len(parts) > 1:
            command = parts[1]
            output = run_r0tbb_command(f"r0tbb {command}")
            response = f"🚀 <b>Executing: r0tbb {command}</b>\n\n<pre>{output}</pre>"
        else:
            response = """🚀 <b>Run Command Usage:</b>

<code>/run &lt;command&gt;</code>

<b>Examples:</b>
• <code>/run init example.com</code>
• <code>/run run att</code>
• <code>/run summarize att</code>
• <code>/run zip att</code>
• <code>/run clean att</code>
• <code>/run --help</code>

<b>Available commands:</b>
• init, run, status, summarize, zip, clean, bot, list"""
    
    elif text.startswith('/exec'):
            parts = text.split(' ', 1)
            if len(parts) > 1:
                command = parts[1]
                # Security check - only allow safe commands
                dangerous_commands = ['rm', 'sudo', 'su', 'chmod', 'chown', 'dd', 'mkfs', 'fdisk']
                if any(dangerous in command.lower() for dangerous in dangerous_commands):
                    response = "❌ <b>Security Warning:</b> This command is not allowed for safety reasons."
                else:
                    output = run_r0tbb_command(command)
                    response = f"💻 <b>Executing: {command}</b>\n\n<pre>{output}</pre>"
            else:
                response = """💻 <b>Execute Command Usage:</b>
                
                <code>/exec &lt;command&gt;</code>
                
                <b>Examples:</b>
                • <code>/exec ls -la</code>
                • <code>/exec pwd</code>
                • <code>/exec whoami</code>
                • <code>/exec ps aux | grep r0tbb</code>
                
                <b>⚠️ Security:</b>
                • Only safe commands allowed
                • No system modification commands
                • Commands run in r0tbb directory"""
    
    elif text.startswith('/report'):
            parts = text.split(' ', 1)
            if len(parts) > 1:
                target = parts[1]
                response = f"📊 <b>Generating security report for: {target}</b>\n\n⏳ Please wait..."
                
                # Send initial response
                send_message(chat_id, response)
                
                # Generate report
                try:
                    report_output = run_r0tbb_command(f"python3 report_generator.py {target}")
                    
                    # Split report into chunks if too long
                    if len(report_output) > 4000:
                        chunks = [report_output[i:i+4000] for i in range(0, len(report_output), 4000)]
                        for i, chunk in enumerate(chunks):
                            chunk_response = f"📊 <b>Security Report - {target}</b> (Part {i+1}/{len(chunks)})\n\n<pre>{chunk}</pre>"
                            send_message(chat_id, chunk_response)
                    else:
                        response = f"📊 <b>Security Report - {target}</b>\n\n<pre>{report_output}</pre>"
                        send_telegram_message(chat_id, response)
                    
                    return  # Don't send the initial response again
                    
                except Exception as e:
                    response = f"❌ <b>Error generating report:</b>\n\n<pre>{str(e)}</pre>"
            else:
                response = """📊 <b>Security Report Usage:</b>
                
                <code>/report &lt;target&gt;</code>
                
                <b>Examples:</b>
                • <code>/report distrisuper.com</code>
                • <code>/report example.com</code>
                • <code>/report microsoft.com</code>
                
                <b>Features:</b>
                • Detailed findings by severity
                • API keys discovered
                • Technology stack analysis
                • Statistics and metrics
                • Organized by criticality"""
    
    elif text.startswith('/help'):
        response = """🤖 <b>r0tbb Bot - Complete Help</b>

<b>📋 Bot Commands:</b>
• /start - Welcome message
• /status [target] - View specific target status
• /list - List all available targets
• /run [command] - Execute any r0tbb command
• /exec [command] - Execute any shell command (safe)
• /report [target] - Generate detailed security report
• /help - This help

<b>🔧 Available CLI Commands:</b>
• <code>r0tbb init &lt;domain&gt;</code> - Initialize target
• <code>r0tbb run &lt;target&gt;</code> - Run pipeline
• <code>r0tbb status &lt;target&gt;</code> - View progress
• <code>r0tbb summarize &lt;target&gt;</code> - Generate report
• <code>python3 report_generator.py &lt;target&gt;</code> - Detailed security report

<b>📱 Terminal Usage:</b>
<code>cd /home/l0n3/r0tbb</code>
<code>r0tbb --help</code>

<b>🎯 Integrated Tools:</b>
• subfinder • httpx • katana • nuclei


<b>✅ Ready for Bug Bounty!</b>"""
    
    else:
        response = f"❓ Unknown command: <code>{text}</code>\n\nUse /help to see available commands."
    
    send_message(chat_id, response)

def main():
    """Función principal del bot"""
    print("🤖 r0tbb bot started successfully")
    print(f"📱 Authorized chat: {CHAT_ID}")
    print("⚡ Press Ctrl+C to stop")
    
    last_update_id = 0
    
    try:
        while True:
            # Obtener actualizaciones
            updates = get_updates(last_update_id + 1)
            
            if updates and updates.get('ok'):
                for update in updates['result']:
                    last_update_id = update['update_id']
                    
                    if 'message' in update:
                        print(f"📨 Message received: {update['message'].get('text', '')}")
                        process_message(update['message'])
                    elif 'edited_message' in update:
                        print(f"📝 Message edited: {update['edited_message'].get('text', '')}")
                        process_message(update['edited_message'])
            
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped by user")
    except Exception as e:
        print(f"❌ Bot error: {e}")

if __name__ == '__main__':
    main()
