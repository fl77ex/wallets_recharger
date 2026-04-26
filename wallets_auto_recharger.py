import os
import random
import time

import gspread
import telebot
from dotenv import load_dotenv
from oauth2client.service_account import ServiceAccountCredentials
from web3 import Web3

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
GOOGLE_CREDS_FILE = os.getenv("GOOGLE_CREDS_FILE")
SPREADSHEET_NAME = os.getenv("SPREADSHEET_NAME")
SHEET_NAME = os.getenv("SHEET_NAME")
MIN_BALANCE = float(os.getenv("MIN_BALANCE", "0"))
FROM_WALLET_COLUMN = os.getenv("FROM_WALLET_NAME")
WALLET_SECRET_COLUMN = os.getenv("WALLET_SECRET_NAME")
TO_WALLET_COLUMN = os.getenv("TO_WALLET_NAME")

NETWORKS = {
    "op": {"rpc": os.getenv("OP_RPC"), "chain_id": 10},
    "arb": {"rpc": os.getenv("ARB_RPC"), "chain_id": 42161},
    "base": {"rpc": os.getenv("BASE_RPC"), "chain_id": 8453},
}

SOURCE_WALLET_FILES = ("from_wallet.txt", "from_wallets.txt")
USED_WALLETS_FILE = "used_wallets.txt"


def require_env() -> None:
    required_values = {
        "TELEGRAM_TOKEN": TELEGRAM_TOKEN,
        "TELEGRAM_CHAT_ID": TELEGRAM_CHAT_ID,
        "GOOGLE_CREDS_FILE": GOOGLE_CREDS_FILE,
        "SPREADSHEET_NAME": SPREADSHEET_NAME,
        "SHEET_NAME": SHEET_NAME,
        "FROM_WALLET_NAME": FROM_WALLET_COLUMN,
        "WALLET_SECRET_NAME": WALLET_SECRET_COLUMN,
        "TO_WALLET_NAME": TO_WALLET_COLUMN,
    }
    missing = [key for key, value in required_values.items() if not value]
    if missing:
        raise ValueError(f"Missing required environment variables: {', '.join(missing)}")


def get_source_wallets_file() -> str:
    for path in SOURCE_WALLET_FILES:
        if os.path.exists(path):
            return path
    raise FileNotFoundError(
        "Source wallets file not found. Create 'from_wallet.txt' or 'from_wallets.txt'."
    )


def build_sheet():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_name(GOOGLE_CREDS_FILE, scope)
    client = gspread.authorize(creds)
    return client.open(SPREADSHEET_NAME).worksheet(SHEET_NAME)


def load_used_wallets() -> set[str]:
    if not os.path.exists(USED_WALLETS_FILE):
        return set()
    with open(USED_WALLETS_FILE, "r", encoding="utf-8") as file:
        return set(file.read().splitlines())


def load_available_wallets() -> list[str]:
    source_file = get_source_wallets_file()
    used_wallets = load_used_wallets()

    with open(source_file, "r", encoding="utf-8") as file:
        all_wallets = [wallet.strip() for wallet in file.readlines() if wallet.strip()]

    return [wallet for wallet in all_wallets if wallet not in used_wallets]


def send_telegram(bot: telebot.TeleBot, message: str) -> None:
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except Exception as exc:
        print(f"Telegram send failed: {exc}")


def get_wallet_data(sheet, wallet_address: str) -> tuple[str | None, str | None]:
    records = sheet.get_all_records(
        expected_headers=[
            FROM_WALLET_COLUMN,
            WALLET_SECRET_COLUMN,
            TO_WALLET_COLUMN,
        ]
    )
    for record in records:
        if record[FROM_WALLET_COLUMN].lower() == wallet_address.lower():
            return record[WALLET_SECRET_COLUMN], record[TO_WALLET_COLUMN]
    return None, None


def check_and_send(sheet, bot: telebot.TeleBot, wallet: str) -> bool:
    secret, recipient = get_wallet_data(sheet, wallet)
    if not secret or not recipient:
        print(f"Wallet {wallet} was not found in the sheet or is missing recipient data.")
        return False

    sent_any = False
    for network, data in NETWORKS.items():
        if not data["rpc"]:
            continue

        w3 = Web3(Web3.HTTPProvider(data["rpc"]))
        account = w3.eth.account.from_key(secret)
        balance = w3.eth.get_balance(account.address)
        eth_balance = Web3.from_wei(balance, "ether")
        gas_price = int(w3.eth.gas_price * 1.2)

        print(f"{wallet} | {network} balance: {eth_balance} ETH")
        time.sleep(1)

        if eth_balance <= MIN_BALANCE:
            continue

        send_value = int(balance * 0.999 - gas_price * 21000)
        if send_value <= 0:
            print(f"Skipped {wallet} on {network}: balance is too low after gas cost.")
            continue

        tx = {
            "to": w3.to_checksum_address(recipient),
            "value": send_value,
            "gas": 21000,
            "gasPrice": gas_price,
            "nonce": w3.eth.get_transaction_count(account.address),
            "chainId": data["chain_id"],
        }
        signed_tx = w3.eth.account.sign_transaction(tx, secret)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        tx_hash_hex = Web3.to_hex(tx_hash)

        print(f"Sent from {wallet} to {recipient} on {network}: {tx_hash_hex}")
        send_telegram(
            bot,
            f"Transfer sent on {network}\n"
            f"Amount: {eth_balance} ETH\n"
            f"From: {wallet}\n"
            f"To: {recipient}\n"
            f"Tx: {tx_hash_hex}",
        )
        sent_any = True

    return sent_any


def mark_wallet_as_used(wallet: str) -> None:
    with open(USED_WALLETS_FILE, "a", encoding="utf-8") as file:
        file.write(wallet + "\n")


def main() -> None:
    require_env()
    bot = telebot.TeleBot(TELEGRAM_TOKEN)
    sheet = build_sheet()
    available_wallets = load_available_wallets()

    while available_wallets:
        wallet = random.choice(available_wallets)
        try:
            success = check_and_send(sheet, bot, wallet)
            available_wallets.remove(wallet)

            if success:
                mark_wallet_as_used(wallet)
                sleep_time = random.randint(600, 7200)
                send_telegram(bot, f"Next run in {sleep_time // 60} minutes.")
                print(f"Sleeping for {sleep_time} seconds.")
                time.sleep(sleep_time)
        except Exception as exc:
            print(f"Error while processing {wallet}: {exc}")
            send_telegram(bot, f"Error while processing {wallet}: {exc}")
            available_wallets.remove(wallet)

    send_telegram(bot, "All wallets processed.")


if __name__ == "__main__":
    main()
