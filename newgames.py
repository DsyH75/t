import uuid
import asyncio
import aiohttp
import time

DEBUG = False
MAX_RETRIES = 20
OUTPUT_FILE = "1"
LOOP_DELAY = 2 * 60  # Delay between complete cycles in seconds (2 minutes)

games = {
  "Cafe Dash": {
        "appToken": "bc0971b8-04df-4e72-8a3e-ec4dc663cd11",
        "promoId": "bc0971b8-04df-4e72-8a3e-ec4dc663cd11",
        "delay": 20,
        "retry": 20,
        "keys": 4,
  },
  "Zoopolis": {
        "appToken": "b2436c89-e0aa-4aed-8046-9b0515e1c46b",
        "promoId": "b2436c89-e0aa-4aed-8046-9b0515e1c46b",
        "delay": 20,
        "retry": 20,
        "keys": 4,
    },
    "Gangs Wars": {
        "appToken": "b6de60a0-e030-48bb-a551-548372493523",
        "promoId": "c7821fa7-6632-482c-9635-2bd5798585f9",
        "delay": 20,
        "retry": 20,
        "keys": 4,
    },
}


def debug(*args):
    if DEBUG:
        print(*args)


def info(*args):
    print(*args)


async def fetch_api(session, path, auth_token=None, body=None):
    url = f"https://api.gamepromo.io{path}"
    headers = {}

    if auth_token:
        headers["authorization"] = f"Bearer {auth_token}"

    if body is not None:
        headers["content-type"] = "application/json"

    async with session.post(url, headers=headers, json=body) as response:
        debug(f"URL: {url}, Headers: {headers}, Body: {body}")
        if response.status != 200:
            error_message = await response.text()
            debug(f"Error {response.status}: {error_message}")
            raise Exception(f"{response.status} {response.reason}: {error_message}")

        return await response.json()


async def get_promo_code(session, game_key):
    game_config = games[game_key]
    client_id = str(uuid.uuid4())

    try:
        login_client_data = await fetch_api(
            session,
            "/promo/login-client",
            body={
                "appToken": game_config["appToken"],
                "clientId": client_id,
                "clientOrigin": "ios",
            },
        )
    except Exception as e:
        info(f"Failed to login client for {game_key}: {e}")
        return None

    auth_token = login_client_data.get("clientToken")
    if not auth_token:
        info(f"Failed to obtain auth token for {game_key}")
        return None

    promo_code = None

    for _ in range(MAX_RETRIES):
        try:
            await asyncio.sleep(game_config["delay"])
            register_event_data = await fetch_api(
                session,
                "/promo/register-event",
                auth_token,
                body={
                    "promoId": game_config["promoId"],
                    "eventId": str(uuid.uuid4()),
                    "eventOrigin": "undefined",
                },
            )
        except Exception as e:
            info(f"Failed to register event for {game_key}: {e}")
            await asyncio.sleep(game_config["retry"])
            continue

        if not register_event_data.get("hasCode"):
            await asyncio.sleep(game_config["retry"])
            continue

        try:
            create_code_data = await fetch_api(
                session,
                "/promo/create-code",
                auth_token,
                body={
                    "promoId": game_config["promoId"],
                },
            )
            promo_code = create_code_data.get("promoCode")
            break
        except Exception as e:
            info(f"Failed to create code for {game_key}: {e}")
            await asyncio.sleep(game_config["retry"])

    if promo_code is None:
        info(f"Unable to get {game_key} promo after {MAX_RETRIES} retries")

    return promo_code


async def main():
    async with aiohttp.ClientSession() as session:
        with open(OUTPUT_FILE, "a") as f:  # ('a' - append mode)
            while True:
                for game_key in games:
                    promo_codes = []
                    for _ in range(games[game_key]["keys"]):
                        code = await get_promo_code(session, game_key)
                        if code:
                            info(f"{code}")
                            promo_codes.append(f"{code}\n")
                    f.writelines(promo_codes)
                info(f"End of cycle. Wait {LOOP_DELAY} second before next cycle.")
                await asyncio.sleep(LOOP_DELAY)


if __name__ == "__main__":
    asyncio.run(main())
