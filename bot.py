import os
import discord
from discord.ext import tasks, commands
import asyncio
from google.oauth2 import service_account
from googleapiclient.discovery import build
import logging
import random
import json

# Configuração do logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger()

# Carregar configurações do arquivo config.json
with open('config.json') as config_file:
    config = json.load(config_file)

# Acessar o token diretamente das variáveis de ambiente
TOKEN = os.getenv("DISCORD_BOT_TOKEN")  # Usando o token do GitHub Secrets

CHANNEL_ID = config["CHANNEL_ID"]
MENTION_CHANNEL_ID = config["MENTION_CHANNEL_ID"]
SPREADSHEET_ID = config["SPREADSHEET_ID"]
SERVICE_ACCOUNT_INFO = config["SERVICE_ACCOUNT_INFO"]

# Configurações da API do Google Sheets
SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

# Inicializa cliente Discord
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Inicializa credenciais do Google Sheets
creds = service_account.Credentials.from_service_account_info(SERVICE_ACCOUNT_INFO, scopes=SCOPES)
service = build("sheets", "v4", credentials=creds)

# Armazena respostas já processadas
processed_responses = set()

# Emojis para perguntas
QUESTION_EMOJIS = ["🔹", "🔸", "⭐", "✨", "💡", "📌", "📍", "📝", "🔍", "🗂"]
def get_random_emoji():
    return random.choice(QUESTION_EMOJIS)

# Função para buscar respostas do Google Sheets
async def get_form_responses():
    try:
        sheet_metadata = service.spreadsheets().get(spreadsheetId=SPREADSHEET_ID).execute()
        sheet_name = sheet_metadata["sheets"][0]["properties"]["title"]
        range_name = f"{sheet_name}"

        result = service.spreadsheets().values().get(spreadsheetId=SPREADSHEET_ID, range=range_name).execute()
        values = result.get("values", [])

        if not values:
            logger.warning("Nenhuma resposta encontrada na planilha.")
            return []

        headers = values[0]  # Primeira linha é o cabeçalho
        responses = []
        for row in values[1:]:  # Linhas com respostas
            response = dict(zip(headers, row))
            responses.append(response)
        return responses

    except Exception as e:
        logger.error(f"Erro ao buscar respostas: {e}")
        return []

# Loop para checar respostas a cada 5 segundos
@tasks.loop(seconds=5)
async def check_form_responses():
    main_channel = bot.get_channel(CHANNEL_ID)
    mention_channel = bot.get_channel(MENTION_CHANNEL_ID)
    if main_channel is None or mention_channel is None:
        logger.error("Um dos canais não foi encontrado!")
        return

    responses = await get_form_responses()

    for response in responses:
        response_tuple = tuple(response.items())
        if response_tuple not in processed_responses:
            message = "\n".join([f"{get_random_emoji()} **{key}**: {value}" for key, value in response.items() if key.lower() != "discord id"])

            embed = discord.Embed(title="📩 Nova Resposta Recebida!", description=message, color=discord.Color.blue())
            await main_channel.send(embed=embed)

            # Menção ao usuário que passou
            discord_id = response.get("ID do Discord")  # Busca pelo ID do Discord
            nome_no_ic = response.get("Nome no IC")  # Resposta da pergunta "Nome no IC"
            user_to_message = 963524916987183134  # ID fixo para mensagem

            if discord_id and discord_id.isdigit() and nome_no_ic:
                logger.info(f"Mencionando usuário com ID: {discord_id}")
                mention_message = (
                    f"# <:PARASAR:{1132713845559922728}>  Paracomandos\n\n"
                    f"{nome_no_ic} // <@{discord_id}>\n\n"
                    f"Você está pré-aprovado para a Paracomandos! \n"
                    f"Envie uma mensagem para <@{user_to_message}> informando sua disponibilidade de data e horário para "
                    f"agendarmos na melhor opção para você."
                )
                await mention_channel.send(mention_message)
            else:
                logger.warning(f"Discord ID ou Nome no IC inválido ou ausente para a resposta: {response}")

            processed_responses.add(response_tuple)

# Comando !teste para mencionar o último ID
@bot.command()
async def teste(ctx):
    last_discord_id = None
    responses = await get_form_responses()
    for response in responses:
        discord_id = response.get("ID do Discord")
        if discord_id and discord_id.isdigit():
            last_discord_id = discord_id

    if last_discord_id:
        await ctx.send(f"👋 Olá <@{last_discord_id}>, aqui está o seu teste!")
    else:
        await ctx.send("Nenhum ID de Discord foi registrado ainda!")

# Evento de inicialização do bot
@bot.event
async def on_ready():
    logger.info(f"Bot conectado como {bot.user}")
    if not check_form_responses.is_running():
        check_form_responses.start()

# Inicia o bot
bot.run(TOKEN)
