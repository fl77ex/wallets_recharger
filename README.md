# Wallet Recharger

`Wallet Recharger` is a small automation script for collecting native gas funds from multiple EVM wallets and forwarding them to destination wallets listed in a Google Sheet.

The script was built for repetitive treasury-style maintenance tasks such as cleaning up small ETH balances on Optimism, Arbitrum, and Base, while keeping simple operational visibility through Telegram notifications.

## What It Does

- Loads source wallets from a local text file
- Reads wallet metadata from Google Sheets
- Checks native balances on supported EVM networks
- Sends available funds to the configured recipient wallet
- Tracks already processed wallets in a local state file
- Posts success and error notifications to Telegram
- Waits a random amount of time between successful transfers

## Supported Networks

- Optimism
- Arbitrum One
- Base

The network list can be extended through environment variables and the `NETWORKS` mapping in the script.

## Project Structure

```text
wallets_auto_recharger.py   Main automation script
.env.example                Example environment configuration
from_wallet.txt             Source wallets list
used_wallets.txt            Runtime file with processed wallets
```

## How It Works

1. The script loads source wallet addresses from `from_wallet.txt` or `from_wallets.txt`.
2. It opens a Google Sheet containing:
   - source wallet address
   - private key / secret
   - destination wallet address
3. For each wallet, it checks balances on each configured network.
4. If the balance is above the minimum threshold, it sends almost the full balance minus gas.
5. Successful wallets are saved to `used_wallets.txt` to avoid reprocessing.
6. Telegram receives status updates for transfers, errors, and next-run delays.

## Google Sheet Format

The worksheet must contain three columns whose names are configured through environment variables:

- `FROM_WALLET_NAME`
- `WALLET_SECRET_NAME`
- `TO_WALLET_NAME`

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Create your environment file

Copy `.env.example` to `.env` and fill in your values.

### 3. Prepare wallet inputs

Add source wallet addresses to `from_wallet.txt` with one wallet per line.

### 4. Add Google service account credentials

Set `GOOGLE_CREDS_FILE` to the path of your service account JSON file and make sure the spreadsheet is shared with that service account.

### 5. Run the script

```bash
python wallets_auto_recharger.py
```

## Environment Variables

```env
TELEGRAM_TOKEN=
TELEGRAM_CHAT_ID=

GOOGLE_CREDS_FILE=
SPREADSHEET_NAME=
SHEET_NAME=
FROM_WALLET_NAME=
WALLET_SECRET_NAME=
TO_WALLET_NAME=

OP_RPC=
ARB_RPC=
BASE_RPC=

MIN_BALANCE=
```

## Portfolio Notes

This project demonstrates:

- Python scripting for blockchain operations
- Web3 integration for EVM-compatible networks
- Google Sheets as a lightweight operations backend
- Telegram bot notifications for workflow monitoring
- Simple state tracking for idempotent batch processing

## Safety Note

This script works with private keys and sends on-chain transactions. Use it only in environments you control, with secure secret management and careful balance checks before running it against production wallets.
