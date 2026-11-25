import asyncio
import websockets

URL = "wss://ws.derivws.com/websockets/v3?app_id=1089"

async def test():
    try:
        async with websockets.connect(URL) as ws:
            print("SUCCESS: Connected to Deriv WebSocket")
            await ws.send('{"ping": 1}')
            print(await ws.recv())
    except Exception as e:
        print("FAILED:", e)

asyncio.run(test())
