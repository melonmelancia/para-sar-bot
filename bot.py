import os
import discord
from discord.ext import tasks, commands
import asyncio
from google.oauth2 import service_account
from googleapiclient.discovery import build
import logging
import random

# Configuração do logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger()

# Obter variáveis do GitHub Secrets
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
GOOGLE_PRIVATE_KEY = os.getenv("GOOGLE_PRIVATE_KEY", "").replace("\\n", "\n")
GOOGLE_CLIENT_EMAIL = os.getenv("GOOGLE_CLIENT_EMAIL")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
CHANNEL_ID = int(os.getenv("CHANNEL_ID", 0))
MENTION_CHANNEL_ID = int(os.getenv("MENTION_CHANNEL_ID", 0))
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")

# Debug: verificar se as variáveis de ambiente estão carregadas corretamente
env_vars = ["DISCORD_BOT_TOKEN", "GOOGLE_CLIENT_EMAIL", "GOOGLE_CLIENT_ID", "GOOGLE_PRIVATE_KEY", "CHANNEL_ID", "MENTION_CHANNEL_ID", "SPREADSHEET_ID"]
missing_vars = [var for var in env_vars if not os.getenv(var)]

if missing_vars:
    logger.error(f"❌ ERRO: As seguintes variáveis de ambiente não estão definidas: {', '.join(missing_vars)}")
else:
    logger.info("✅ Todas as variáveis de ambiente foram carregadas corretamente!")

# Configuração do Service Account para API do Google Sheets
SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
SERVICE_ACCOUNT_INFO = {
    "type": "service_account",
    "project_id": "para-sar-bot",
    "private_key": GOOGLE_PRIVATE_KEY,
    "client_email": GOOGLE_CLIENT_EMAIL,
    "client_id": GOOGLE_CLIENT_ID,
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs"
}

# Inicializa cliente Discord
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Inicializa credenciais do Google Sheets
try:
    creds = service_account.Credentials.from_service_account_info(SERVICE_ACCOUNT_INFO, scopes=SCOPES)
    service = build("sheets", "v4", credentials=creds)
except Exception as e:
    logger.error(f"❌ Erro ao configurar API do Google Sheets: {e}")
    service = None

# Armazena respostas já processadas
processed_responses = set()

# Emojis para perguntas
QUESTION_EMOJIS = ["🔹", "🔸", "⭐", "✨", "💡", "📌", "📍", "📝", "🔍", "🗂"]

def get_random_emoji():
    return random.choice(QUESTION_EMOJIS)

# Função para buscar respostas do Google Sheets
async def get_form_responses():
    if service is None:
        logger.error("❌ Serviço da API do Google Sheets não foi inicializado corretamente.")
        return []

    try:
        sheet_metadata = service.spreadsheets().get(spreadsheetId=SPREADSHEET_ID).execute()
        sheet_name = sheet_metadata["sheets"][0]["properties"]["title"]
        range_name = f"{sheet_name}"

        result = service.spreadsheets().values().get(spreadsheetId=SPREADSHEET_ID, range=range_name).execute()
        values = result.get("values", [])

        if not values:
            logger.warning("⚠️ Nenhuma resposta encontrada na planilha.")
            return []

        headers = values[0]
        responses = [dict(zip(headers, row)) for row in values[1:] if row]
        return responses

    except Exception as e:
        logger.error(f"❌ Erro ao buscar respostas da planilha: {e}")
        return []

# Loop para checar respostas a cada 5 segundos
@tasks.loop(seconds=5)
async def check_form_responses():
    try:
        main_channel = bot.get_channel(CHANNEL_ID)
        mention_channel = bot.get_channel(MENTION_CHANNEL_ID)

        if main_channel is None or mention_channel is None:
            logger.error("❌ Um dos canais não foi encontrado.")
            return

        responses = await get_form_responses()

        if not responses:
            logger.info("🔍 Nenhuma nova resposta encontrada. Aguardando...")
            return  

        for response in responses:
            response_tuple = tuple(response.items())
            if response_tuple not in processed_responses:
                message = "\n".join([f"{get_random_emoji()} **{key}**: {value}" for key, value in response.items() if key.lower() != "discord id"])

                embed = discord.Embed(title="📩 Nova Resposta Recebida!", description=message, color=discord.Color.blue())
                await main_channel.send(embed=embed)

                discord_id = response.get("ID do Discord")
                nome_no_ic = response.get("Nome no IC")
                user_to_message = 963524916987183134  

                if discord_id and discord_id.isdigit() and nome_no_ic:
                    mention_message = f"# <:PARASAR:{1132713845559922728}>  Paracomandos\n\n|| {nome_no_ic} // <@{discord_id}> || \n\n*Você está pré-aprovado!*"
                        f"*Envie uma mensagem para <@{user_to_message}> informando sua disponibilidade de data e horário para* "
                        f"*agendarmos na melhor opção para você*.\n\n"
                        f"@here"
                    )
                    await mention_channel.send(mention_message)

                processed_responses.add(response_tuple)

    except Exception as e:
        logger.error(f"❌ Erro no loop de verificação de respostas: {e}")

@bot.event
async def on_ready():
    logger.info(f"✅ Bot conectado como {bot.user}")
    if not check_form_responses.is_running():
        check_form_responses.start()

if TOKEN:
    bot.run(TOKEN)
else:
    logger.error("❌ DISCORD_BOT_TOKEN não foi encontrado!")
