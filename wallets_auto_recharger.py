import os
import random
import time
from dotenv import load_dotenv
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from web3 import Web3
import telebot

load_dotenv()

# ===================== Настройки =====================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
GOOGLE_CREDS_FILE = os.getenv("GOOGLE_CREDS_FILE")
SPREADSHEET_NAME = os.getenv("SPREADSHEET_NAME")
SHEET_NAME = os.getenv("SHEET_NAME")
MIN_BALANCE = os.getenv("MIN_BALANCE")
FROM_WALLET = os.getenv("FROM_WALLET_NAME")
WALLET_SECRET = os.getenv("WALLET_SECRET_NAME")
TO_WALLET = os.getenv("TO_WALLET_NAME")


# RPC URLs для сетей и их chainId
NETWORKS = {
    "op": {"rpc": os.getenv("OP_RPC"), "chainId": 10},
    "arb": {"rpc": os.getenv("ARB_RPC"), "chainId": 42161},
    "base": {"rpc": os.getenv("BASE_RPC"), "chainId": 8453}
}

FROM_WALLETS_FILE = "from_wallets.txt"
USED_WALLETS_FILE = "used_wallets.txt"

# Инициализация Telebot
bot = telebot.TeleBot(TELEGRAM_TOKEN)

# ===================== Google Sheets =====================
scope = ["https://spreadsheets.google.com/feeds",'https://www.googleapis.com/auth/drive']
creds = ServiceAccountCredentials.from_json_keyfile_name(GOOGLE_CREDS_FILE, scope)
client = gspread.authorize(creds)
sheet = client.open(SPREADSHEET_NAME).worksheet(SHEET_NAME)

# ===================== Загрузка кошельков =====================
used_wallets = set()
if os.path.exists(USED_WALLETS_FILE):
    with open(USED_WALLETS_FILE, "r") as f:
        used_wallets = set(f.read().splitlines())

with open(FROM_WALLETS_FILE, "r") as f:
    all_wallets = [w.strip() for w in f.readlines() if w.strip()]
available_wallets = [w for w in all_wallets if w not in used_wallets]

# ===================== Функции =====================
def send_telegram(message):
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except Exception as e:
        print(f"Ошибка отправки в Telegram: {e}")

def get_wallet_data(wallet_address):
    # Указываем ожидаемые заголовки
    records = sheet.get_all_records(expected_headers=[FROM_WALLET, WALLET_SECRET, TO_WALLET])
    for r in records:
        if r[FROM_WALLET].lower() == wallet_address.lower():
            return r[WALLET_SECRET], r[TO_WALLET]
    return None, None

def check_and_send(wallet):
    secret, recipient = get_wallet_data(wallet)
    print(wallet, secret, recipient)
    
    if not secret:
        print(f"Кошелек {wallet} не найден в таблице")
        return False
    sended = False
    for network, data in NETWORKS.items():
        w3 = Web3(Web3.HTTPProvider(data["rpc"]))
        account = w3.eth.account.from_key(secret)
        balance = w3.eth.get_balance(account.address)
        eth_balance = Web3.from_wei(balance, 'ether')
        #eth_balance = w3.fromWei(balance, 'ether')
        print(f"{network} balance: {eth_balance}")

        gas_now = int(w3.eth.gas_price * 1.2)
        print(gas_now)
        time.sleep(1)
        if eth_balance > float(MIN_BALANCE):
            # Транзакция
            tx = {
                'to': w3.to_checksum_address(recipient),
                'value': int(balance * 0.999 - gas_now * 21000),
                'gas': 21000,
                'gasPrice': gas_now,
                'nonce': w3.eth.get_transaction_count(account.address),
                'chainId': data["chainId"]
            }
            signed_tx = w3.eth.account.sign_transaction(tx, secret)
            tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
            print(f"Отправлено на {recipient} в сети {network}: {Web3.to_hex(tx_hash)}")
            send_telegram(f"✅ Sended {network} {eth_balance}ETH \nfrom: {wallet} \nto: {recipient}\nTx: {Web3.to_hex(tx_hash)}")

            sended = True
    return sended


# ===================== Основной цикл =====================
while available_wallets:
    wallet = random.choice(available_wallets)
    try:
        success = check_and_send(wallet)
        available_wallets.remove(wallet)
        if success:
            # Записываем в used_wallets.txt
            with open(USED_WALLETS_FILE, "a") as f:
                f.write(wallet + "\n")
            sleep_time = random.randint(600, 7200)  # 10 минут - 2 часа
            time.sleep(1)
            send_telegram(f"Next in {sleep_time//60} min")
            print('sleep', sleep_time)
            time.sleep(sleep_time)
    except Exception as e:
        print(f"Ошибка с кошельком {wallet}: {e}")
        send_telegram(f"⚠️ Error {wallet}: {e}")
        available_wallets.remove(wallet)

send_telegram("Jobs done")
