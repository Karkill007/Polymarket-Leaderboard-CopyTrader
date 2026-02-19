import requests
import random
import time
from bs4 import BeautifulSoup
import sqlite3
import json
from datetime import datetime, timedelta, timezone
import os
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, MarketOrderArgs, OrderType, OpenOrderParams, BalanceAllowanceParams, AssetType
from py_clob_client.order_builder.constants import BUY, SELL
from collections import defaultdict, Counter
from zoneinfo import ZoneInfo



DbPath = f'/home/{os.getlogin()}/Documents/Polymarket/users.db'
MEX_TZ = ZoneInfo("America/Mexico_City")



def authentication_client():
    auth_client = ClobClient(
        "https://clob.polymarket.com",
        key=os.getenv("POLYMARKET_PRIVATE_KEY"),
        chain_id=137,
        signature_type=1,
        funder=os.getenv("POLYMARKET_WALLET_ADDRESS")
    )
    creds = auth_client.derive_api_key()
    auth_client.set_api_creds(creds)
    return auth_client



def get_balance():
    client = authentication_client()
    balance = client.get_balance_allowance(BalanceAllowanceParams(asset_type=AssetType.COLLATERAL))
    usdc_balance = int(balance['balance']) / 1e6
    return round(usdc_balance, 2)



def place_order(bet_token_id, amount_bet = 1):
    try:
        client = authentication_client()
        market_order = MarketOrderArgs(
            token_id=bet_token_id,
            amount=amount_bet,
            side=BUY,
            order_type=OrderType.FOK
        )
        signed_market_order = client.create_market_order(market_order)
        response = client.post_order(signed_market_order, OrderType.FOK)
        return response['success']
    except Exception as e:
        return False



def WebRequester(URL):
    try:
        with requests.Session() as s:
            user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0.3 Safari/605.1.15',
            'Mozilla/5.0 (Linux; Android 10; Pixel 3 XL) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.93 Mobile Safari/537.36']
            headers = {
            'User-Agent': random.choice(user_agents),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Connection': 'keep-alive'}
            s.headers.update(headers)
            siteRaw = s.get(URL)
            if siteRaw.status_code == 200:
                return siteRaw.text
            else:
                return False
    except Exception as e:
        return False
        


def extract_leaderboard_data():
    page_content = WebRequester("https://polymarket.com/leaderboard/overall/weekly/profit")
    if page_content != False:
        userList = []
        soup = BeautifulSoup(page_content, 'html.parser')
        for a in soup.select('a[href^="/profile/"]'):
            p = a.find("p", class_="truncate")
            if not p:
                continue
            userList.append({
                "username": p.get_text(strip=True),
                "address": a["href"].split("/profile/")[-1]
            })
        extract_user_info(userList)



def extract_user_info(userList):
    for user in userList:
        finalUserInformation = {}
        finalUserInformation['username'] = user['username']
        finalUserInformation['address'] = user['address']
        userInfo = WebRequester(f"https://data-api.polymarket.com/v1/user-stats?proxyAddress={user['address']}")
        if userInfo != False:
            data = json.loads(userInfo)
            if len(data) > 0:
                finalUserInformation['trades'] = data['trades']
                finalUserInformation['joinDate'] = data['joinDate']
                userInfo = WebRequester(f"https://data-api.polymarket.com/v1/leaderboard?timePeriod=all&orderBy=VOL&limit=1&offset=0&category=overall&user={user['address']}")
                if userInfo != False:
                    data = json.loads(userInfo)
                    if len(data) > 0:
                        finalUserInformation['profit'] = int(data[0]['pnl'])
                        finalUserInformation['vol'] = int(data[0]['vol'])
                        if finalUserInformation.get('trades', 0) > 100 and finalUserInformation.get('profit', 0) > 100000:
                            insert_user_to_db(finalUserInformation)



def check_bet_in_db(bet_slug):
    conn = sqlite3.connect(DbPath)
    cursor = conn.cursor()
    cursor.execute("SELECT slug FROM betsPlaced WHERE slug = ?", (bet_slug,))
    result = cursor.fetchone()
    conn.close()
    return result



def insert_bet(bet_slug):
    conn = sqlite3.connect(DbPath)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS betsPlaced (
            slug TEXT NOT NULL UNIQUE)""")
    cursor.execute("""
            INSERT INTO betsPlaced (slug) VALUES (?)""", (bet_slug,))
    conn.commit()
    conn.close()
    


def insert_user_to_db(user_data):
    conn = sqlite3.connect(DbPath)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            address TEXT PRIMARY KEY,
            username TEXT UNIQUE,
            trades INTEGER,
            profit REAL,
            vol REAL,
            joinDate TEXT
        )
    """)
    cursor.execute("""
        INSERT INTO users (address, username, trades, profit, vol, joinDate)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(address) DO UPDATE SET
            username = excluded.username,
            trades = excluded.trades,
            profit = excluded.profit,
            vol = excluded.vol,
            joinDate = excluded.joinDate
    """, (
        user_data.get("address"),
        user_data.get("username"),
        int(user_data.get("trades", 0)),
        float(user_data.get("profit", 0)),
        float(user_data.get("vol", 0)),
        user_data.get("joinDate")
    ))
    conn.commit()
    conn.close()



def get_all_users_from_db(limit=30):
    conn = sqlite3.connect(DbPath)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT address, username, trades, profit, vol, joinDate
        FROM users
        ORDER BY profit DESC
        LIMIT ?
    """, (limit,))

    users = cursor.fetchall()
    conn.close()
    return users



def get_user_positions(address):
    tradesCleaned = []
    userTradeInfo = WebRequester(f"https://data-api.polymarket.com/positions?user={address}&sortBy=CURRENT&sortDirection=DESC&sizeThreshold=.1&limit=10&offset=0")
    if userTradeInfo != False:
        data = json.loads(userTradeInfo)
        if len(data) > 0:
            for trade in data:
                if trade.get("currentValue", 0) > 1000 and trade.get("curPrice", 0) > 0:
                    tradesCleaned.append(trade)
        return tradesCleaned



def find_average_winners(totalPositions):
    grouped = defaultdict(list)
    for pos in totalPositions:
        key = pos.get("slug") or pos.get("title")
        grouped[key].append(pos)
    results = []
    for key, positions in grouped.items():
        if len(positions) > 3:
            outcomes = [p.get("outcome") for p in positions]
            counts = Counter(outcomes)
            values = [y for y in counts.values()]
            if len(counts) == 1:
                winner, qty = counts.most_common(1)[0]
                total = sum(counts.values())
                results.append({
                    "slug": positions[0].get("slug"),
                    "title": positions[0].get("title"),
                    "winner_outcome": winner,
                    "confidence": round(qty / total, 2)})
    return results



def corate_positions():
    total_positions = []
    users = get_all_users_from_db() 
    for user in users:
        positions = get_user_positions(user[0])
        if positions != None:
            for position in positions:
                total_positions.append(position)
    return find_average_winners(total_positions)



def get_bet_information(bet):
    bet_info = WebRequester(f"https://gamma-api.polymarket.com/markets?slug={bet['slug']}")
    if bet_info != False:
        data = json.loads(bet_info)
        if len(data) > 0:
            outcomes = json.loads(data[0].get('outcomes'))
            outcome_prices = json.loads(data[0].get('outcomePrices'))
            clob_tokens = json.loads(data[0].get('clobTokenIds'))
            betOutcomes = {outcomes[0]: clob_tokens[0], outcomes[1]: clob_tokens[1]}
            return betOutcomes, outcome_prices, data[0].get('acceptingOrders'), data[0].get('startDate')
    


def check_order_to_place(finalBetList):
    for bet in finalBetList:
        bet_info = get_bet_information(bet)
        if bet_info != None:
            if bet_info[2] == True:
                if float(bet_info[1][0]) < 0.6 and float(bet_info[1][1]) < 0.6:
                    bet_token_id = bet_info[0][bet['winner_outcome']]
                    balance_to_use = get_balance()
                    if balance_to_use < 500 and balance_to_use > 5:
                        if check_bet_in_db(bet['slug']) == None:
                            order = place_order(bet_token_id, amount_bet = 5)
                            if order == True:
                                insert_bet(bet['slug'])
                    else:
                        if check_bet_in_db(bet['slug']) == None:
                            if int(balance_to_use * 0.03) < balance_to_use:
                                order = place_order(bet_token_id, amount_bet = int(balance_to_use * 0.03))
                                if order == True:
                                    insert_bet(bet['slug'])



def main():
    last_leaderboard_run = None
    while True:
        now = datetime.now(MEX_TZ)
        today = now.date()
        if now.hour == 4 and last_leaderboard_run != today:
            extract_leaderboard_data()
            last_leaderboard_run = today
        finalBetList = corate_positions()
        check_order_to_place(finalBetList)
        time.sleep(300) 



if __name__ == "__main__":
    main()