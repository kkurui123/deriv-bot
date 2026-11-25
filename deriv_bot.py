import asyncio
import json
import os
import websockets

# ---------------- SETTINGS ----------------
API_TOKEN = os.getenv("DERIV_API_TOKEN", "")

APP_ID = os.getenv("DERIV_APP_ID", "1089")
SYMBOL = os.getenv("DERIV_SYMBOL", "R_100")
STAKE = float(os.getenv("DERIV_STAKE", "10"))
TICKS = int(os.getenv("DERIV_TICKS", "2"))
TRIGGER_DIGIT = int(os.getenv("DERIV_TRIGGER_DIGIT", "0"))
CONTRACT_TYPE = os.getenv("DERIV_CONTRACT_TYPE", "DIGITOVER")
BARRIER = os.getenv("DERIV_BARRIER", "0")
MAX_TRADES = int(os.getenv("DERIV_MAX_TRADES", "20"))
MAX_CONSECUTIVE_LOSSES = int(os.getenv("DERIV_MAX_LOSSES", "3"))

URL = f"wss://ws.derivws.com/websockets/v3?app_id={APP_ID}&l=EN&brand=deriv"
# ------------------------------------------


async def send(ws, data):
    await ws.send(json.dumps(data))
    return json.loads(await ws.recv())


async def main():
    if not API_TOKEN:
        print("ERROR: DERIV_API_TOKEN environment variable is missing.")
        return

    print("Starting Deriv bot...")
    print(f"Symbol: {SYMBOL}")
    print(f"Stake: {STAKE} USD")
    print(f"Duration: {TICKS} ticks")
    print(f"Trigger digit: {TRIGGER_DIGIT}")
    print(f"Contract: {CONTRACT_TYPE} {BARRIER}")
    print(f"Maximum trades: {MAX_TRADES}")
    print(f"Maximum consecutive losses: {MAX_CONSECUTIVE_LOSSES}")

    try:
        async with websockets.connect(
            URL,
            ping_interval=20,
            ping_timeout=20,
            close_timeout=5
        ) as ws:

            auth = await send(ws, {"authorize": API_TOKEN})

            if "error" in auth:
                print("LOGIN ERROR:", auth["error"].get("message"))
                return

            print("Connected successfully as:", auth["authorize"]["email"])

            ticks = await send(ws, {
                "ticks": SYMBOL,
                "subscribe": 1
            })

            if "error" in ticks:
                print("TICK ERROR:", ticks["error"].get("message"))
                return

            print(f"Watching {SYMBOL}. Waiting for last digit {TRIGGER_DIGIT}...")

            trade_count = 0
            consecutive_losses = 0

            while trade_count < MAX_TRADES:
                message = json.loads(await ws.recv())

                if message.get("msg_type") != "tick":
                    continue

                tick = message["tick"]["quote"]
                last_digit = int(str(tick)[-1])

                print(f"Price: {tick} | Last digit: {last_digit}")

                if last_digit != TRIGGER_DIGIT:
                    continue

                trade_count += 1
                print(f"\nDigit {TRIGGER_DIGIT} found. Opening trade {trade_count}...")

                proposal = await send(ws, {
                    "proposal": 1,
                    "amount": STAKE,
                    "basis": "stake",
                    "contract_type": CONTRACT_TYPE,
                    "currency": "USD",
                    "duration": TICKS,
                    "duration_unit": "t",
                    "symbol": SYMBOL,
                    "barrier": BARRIER
                })

                if "error" in proposal:
                    print("PROPOSAL ERROR:", proposal["error"].get("message"))
                    continue

                proposal_id = proposal["proposal"]["id"]
                payout = proposal["proposal"]["payout"]

                print(f"Stake: {STAKE} USD | Potential payout: {payout} USD")

                buy = await send(ws, {
                    "buy": proposal_id,
                    "price": STAKE
                })

                if "error" in buy:
                    print("BUY ERROR:", buy["error"].get("message"))
                    continue

                contract_id = buy["buy"]["contract_id"]
                print(f"Trade opened. Contract ID: {contract_id}")

                while True:
                    result = json.loads(await ws.recv())

                    if result.get("msg_type") == "proposal_open_contract":
                        contract = result["proposal_open_contract"]

                        if (
                            contract.get("contract_id") == contract_id
                            and contract.get("is_sold")
                        ):
                            profit = contract.get("profit", 0)
                            status = "WIN" if profit > 0 else "LOSS"

                            if profit > 0:
                                consecutive_losses = 0
                            else:
                                consecutive_losses += 1

                            print(
                                f"Trade finished: {status} | "
                                f"Profit/Loss: {profit} USD | "
                                f"Consecutive losses: {consecutive_losses}\n"
                            )
                            break

                if consecutive_losses >= MAX_CONSECUTIVE_LOSSES:
                    print("Stopped: maximum consecutive losses reached.")
                    break

            print("Bot stopped.")

    except websockets.exceptions.InvalidStatus as error:
        print("CONNECTION ERROR:", error)
        print("The server rejected the WebSocket connection.")

    except Exception as error:
        print("UNEXPECTED ERROR:", error)


asyncio.run(main())