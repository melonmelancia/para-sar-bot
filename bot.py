import os
import discord
import json
from google.oauth2 import service_account
from googleapiclient.discovery import build
from discord.ext import commands, tasks
import asyncio
from dotenv import load_dotenv

# Carregar variáveis de ambiente do arquivo .env
load_dotenv()

# Carregar informações do config.json
with open('config.json', 'r') as f:
    config = json.load(f)

# Obter a chave privada do ambiente (GitHub Secrets ou arquivo .env)
private_key = os.getenv("GOOGLE_PRIVATE_KEY").replace("\\n", "\n")

# Montar o dicionário do Service Account com a chave privada
service_account_info = config["SERVICE_ACCOUNT_INFO"]
service_account_info["private_key"] = private_key

# Usar as credenciais para acessar a API do Google Sheets
credentials = service_account.Credentials.from_service_account_info(service_account_info)
sheets_api = build('sheets', 'v4', credentials=credentials)

# Configurar o bot do Discord
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Evento para quando o bot estiver online
@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}!')
    print("Bot está online e pronto para usar.")
    # Iniciar a tarefa periódica quando o bot estiver online
    periodic_task.start()

# Comando para ler dados do Google Sheets
@bot.command()
async def read_sheet(ctx):
    # Ler dados do Google Sheets
    sheet = sheets_api.spreadsheets().values().get(
        spreadsheetId=config["SPREADSHEET_ID"], range="Sheet1!A1:B10").execute()
    
    rows = sheet.get('values', [])
    if not rows:
        await ctx.send('No data found.')
    else:
        for row in rows:
            await ctx.send(f'{row[0]}: {row[1]}')

# Comando de exemplo para interagir no Discord
@bot.command()
async def ping(ctx):
    await ctx.send('Pong!')

# Um exemplo de tarefa que pode ser executada periodicamente
@tasks.loop(seconds=60)  # Executa a cada 60 segundos
async def periodic_task():
    print("Executando tarefa periódica.")
    # Coloque aqui funções que você deseja executar periodicamente

# Colocar o bot para rodar
token = os.getenv("DISCORD_TOKEN")
if token is None:
    print("Erro: o token do Discord não foi encontrado.")
else:
    print("Token carregado com sucesso.")
    bot.run(token)
