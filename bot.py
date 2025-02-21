   import os
import discord
from discord.ext import tasks, commands
from google.oauth2 import service_account
from googleapiclient.discovery import build
import logging
import random
import json
import traceback  # Import para capturar traceback completo

# Configuração do logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger()

# Carregar configurações do arquivo config.json
try:
    with open('config.json') as config_file:
        config = json.load(config_file)
except FileNotFoundError:
    logger.error("❌ Arquivo config.json não encontrado!")
    exit(1)

# Acessar variáveis de ambiente do GitHub Secrets
DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
GOOGLE_CLIENT_EMAIL = os.getenv("GOOGLE_CLIENT_EMAIL")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_PRIVATE_KEY = os.getenv("GOOGLE_PRIVATE_KEY")

# Se a chave privada estiver mal formatada, corrigimos isso
if GOOGLE_PRIVATE_KEY:
    GOOGLE_PRIVATE_KEY = GOOGLE_PRIVATE_KEY.replace("\\n", "\n")

# Verificação das credenciais
if not DISCORD_TOKEN:
    logger.error("❌ Variável de ambiente DISCORD_BOT_TOKEN não definida!")
    exit(1)

if not GOOGLE_CLIENT_EMAIL or not GOOGLE_CLIENT_ID or not GOOGLE_PRIVATE_KEY:
    logger.error("❌ Variáveis do Google não definidas corretamente! Verifique os GitHub Secrets.")
    exit(1)

# Configuração da conta de serviço
SERVICE_ACCOUNT_INFO = {
    "type": "service_account",
    "project_id": os.getenv("GOOGLE_PROJECT_ID"),
    "private_key_id": os.getenv("GOOGLE_PRIVATE_KEY_ID"),
    "private_key": GOOGLE_PRIVATE_KEY,
    "client_email": GOOGLE_CLIENT_EMAIL,
    "client_id": GOOGLE_CLIENT_ID,
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/tokenl",
    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
    "client_x509_cert_url": f"https://www.googleapis.com/robot/v1/metadata/x509/netopc53%40para-sar-bot.iam.gserviceaccount.com"
}

# Configuração da API do Google Sheets
SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

try:
    creds = service_account.Credentials.from_service_account_info(SERVICE_ACCOUNT_INFO, scopes=SCOPES)
    service = build("sheets", "v4", credentials=creds)
    logger.info("✅ Conexão com Google Sheets bem-sucedida!")
except Exception as e:
    error_details = traceback.format_exc()
    logger.error(f"❌ Erro ao inicializar credenciais do Google!\nArquivo: {__file__}\nErro: {e}\nDetalhes:\n{error_details}")
    exit(1)

# Inicializa cliente Discord
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Emojis para perguntas
QUESTION_EMOJIS = ["🔹", "🔸", "⭐", "✨", "💡", "📌", "📍", "📝", "🔍", "🗂"]
def get_random_emoji():
    return random.choice(QUESTION_EMOJIS)

# Função para buscar respostas do Google Sheets
async def get_form_responses():
    try:
        sheet_metadata = service.spreadsheets().get(spreadsheetId=config["SPREADSHEET_ID"]).execute()
        sheet_name = sheet_metadata["sheets"][0]["properties"]["title"]
        range_name = f"{sheet_name}"

        result = service.spreadsheets().values().get(spreadsheetId=config["SPREADSHEET_ID"], range=range_name).execute()
        values = result.get("values", [])

        if not values:
            logger.warning("⚠ Nenhuma resposta encontrada na planilha.")
            return []

        headers = values[0]  # Primeira linha é o cabeçalho
        responses = []
        for row in values[1:]:  # Linhas com respostas
            response = dict(zip(headers, row))
            responses.append(response)
        return responses

    except Exception as e:
        error_details = traceback.format_exc()
        logger.error(f"❌ Erro ao buscar respostas!\nArquivo: {__file__}\nErro: {e}\nDetalhes:\n{error_details}")
        return []

# Loop para checar respostas a cada 5 segundos
processed_responses = set()

@tasks.loop(seconds=5)
async def check_form_responses():
    try:
        main_channel = bot.get_channel(config["CHANNEL_ID"])
        mention_channel = bot.get_channel(config["MENTION_CHANNEL_ID"])

        if main_channel is None or mention_channel is None:
            logger.error("❌ Um dos canais não foi encontrado!")
            return

        responses = await get_form_responses()

        for response in responses:
            response_tuple = tuple(response.items())
            if response_tuple not in processed_responses:
                message = "\n".join([f"{get_random_emoji()} **{key}**: {value}" for key, value in response.items() if key.lower() != "discord id"])

                embed = discord.Embed(title="📩 Nova Resposta Recebida!", description=message, color=discord.Color.blue())
                await main_channel.send(embed=embed)

                # Menção ao usuário que passou
                discord_id = response.get("ID do Discord")
                nome_no_ic = response.get("Nome no IC")
                user_to_message = 963524916987183134  # ID fixo para mensagem

                if discord_id and discord_id.isdigit() and nome_no_ic:
                    logger.info(f"🔔 Mencionando usuário com ID: {discord_id}")
                    mention_message = (
                        f"# <:PARASAR:{1132713845559922728}>  Paracomandos\n\n"
                        f"{nome_no_ic} // <@{discord_id}>\n\n"
                        f"Você está pré-aprovado para a Paracomandos! \n"
                        f"Envie uma mensagem para <@{user_to_message}> informando sua disponibilidade de data e horário para "
                        f"agendarmos na melhor opção para você."
                    )
                    await mention_channel.send(mention_message)
                else:
                    logger.warning(f"⚠ Discord ID ou Nome no IC inválido ou ausente para a resposta: {response}")

                processed_responses.add(response_tuple)
    except Exception as e:
        error_details = traceback.format_exc()
        logger.error(f"❌ Erro na verificação de respostas!\nArquivo: {__file__}\nErro: {e}\nDetalhes:\n{error_details}")

# Evento de inicialização do bot
@bot.event
async def on_ready():
    logger.info(f"✅ Bot conectado como {bot.user}")
    if not check_form_responses.is_running():
        check_form_responses.start()

# Inicia o bot
bot.run(DISCORD_TOKEN)
