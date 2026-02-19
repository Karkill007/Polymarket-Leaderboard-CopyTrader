# Polymarket-Leaderboard-CopyTrader

## Polymarket Copytrading Bot

This bot automatically mirrors high-performing traders from the Polymarket leaderboard using a consensus-based strategy and controlled risk management.

## Strategy Overview

Scans the Polymarket leaderboard and filters traders with:

100+ trades

$100k+ total profit

Stores qualified traders in a local database.

Analyzes the top 30 traders from the database.

Aggregates their open positions to identify markets where:

At least 3 traders are participating

The position side (YES/NO) is unanimous

Filters markets where:

Average price < 0.60

Current price < 0.60

Executes trades automatically if all conditions are met.

## Risk Management

If balance < $500 → places $2 fixed bets

If balance ≥ $500 → bets 3% of total account balance

## Installation
Clone the repository
git clone https://github.com/Karkill007/Polymarket-Leaderboard-CopyTrader
cd Polymarket-Leaderboard-CopyTrader

Install required dependencies
pip install -r requirements.txt

## Environment Variables

You must configure the following environment variables:

POLYMARKET_PRIVATE_KEY
POLYMARKET_WALLET_ADDRESS

Linux / macOS
export POLYMARKET_PRIVATE_KEY="your_private_key"
export POLYMARKET_WALLET_ADDRESS="your_wallet_address"

Windows (PowerShell)
setx POLYMARKET_PRIVATE_KEY "your_private_key"
setx POLYMARKET_WALLET_ADDRESS "your_wallet_address"
