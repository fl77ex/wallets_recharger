# Wallets recharger
Check ETH in Arbitrum, Optimism, Base and other(?) EVM chains and send from one wallet to other (for grub dust to one or many wallets). Works with Google Sheet and Telegram.
How it work:
1. Need to add wallets for clean to from_wallets.txt
2. Need to add from_wallets, secret, to_wallets to Google sheet
3. Script get random wallet from txt file and search data in Google sheet (secret and address to send) then send transaction, after send tx info to Telegram.
4. Wait random time and repeat.

