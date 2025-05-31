import requests
import json
import logging
from datetime import datetime, timedelta
import numpy as np
from collections import defaultdict


# logger
def get_logger():
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    handler = logging.FileHandler("rental_roi.log", mode="a")
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger


logger = get_logger()


# Send request, get response, return decoded JSON response
def get_response(url, session: requests.Session):
    request = requests.Request("GET", url=url).prepare()
    response_json = session.send(request, allow_redirects=False)
    if response_json.status_code == 502:
        pass
    response = response_json.json()
    return response


def get_cards(edition, types, rarity, colours, session: requests.Session):
    url = "https://api.splinterlands.com/cards/get_details"
    cards_list = []
    all_cards = get_response(url, session)
    for card in all_cards:
        if card["game_type"] == "splinterlands" and card["editions"] in edition:
            if card["type"] not in types:
                continue
            if card["rarity"] not in rarity:
                continue
            if colours and card["color"] not in colours:
                continue
            cards_list.append(
                {
                    "id": card["id"],
                    "name": card["name"],
                }
            )
    return cards_list


def get_selling_prices(cards, foil, bcx, session: requests.Session):
    url = "https://api.splinterlands.com/market/for_sale_grouped"
    cards_on_market = get_response(url, session)

    card_ids = {
        card["id"] for card in cards
    }  # create a set with all the card ids we are interested in

    cards_list = []

    for card in cards_on_market:
        card_id = card["card_detail_id"]
        if card_id in card_ids and card["foil"] == foil:
            if card["foil"] == 0 or card["foil"] == 1:
                cards_list.append({"id": card_id, "price": card["low_price_bcx"] * bcx})
            else:
                cards_list.append({"id": card_id, "price": card["low_price_bcx"]})

    return cards_list


def get_valid_active_rentals(active_rentals, past_days, foil, bcx):
    valid_active_rentals = []
    for rental in active_rentals:
        rental_time = rental["rental_date"]
        rental_time_formatted = datetime.strptime(rental_time, "%Y-%m-%dT%H:%M:%S.%fZ")

        if rental_time_formatted < past_days:
            continue

        if rental["rental_type"] != "season":
            continue

        if rental["foil"] != foil:
            continue

        if rental["xp"] != bcx:
            continue

        if rental["payment_currency"] != "DEC":
            continue

        valid_active_rentals.append(
            {
                "rental_price": float(rental["buy_price"]),
                "rental_days": rental["rental_days"],
                "card_detail_id": rental["card_detail_id"],
            }
        )

    return valid_active_rentals


def get_active_rentals(cards, foil, bcx, session: requests.Session):
    today = datetime.now()
    past_days = today - timedelta(days=30)

    card_rentals = []
    for card in cards:
        url = f"https://api.splinterlands.com/market/active_rentals?card_detail_id={card['id']}"
        active_rentals = get_response(url, session)
        valid_active_rentals = get_valid_active_rentals(
            active_rentals, past_days, foil, bcx
        )
        card_rentals.append(
            {
                "name": card["name"],
                "id": card["id"],
                "active_rentals": valid_active_rentals,
            }
        )

    return card_rentals


def get_rental_prices(values):
    long_rental_prices = []
    medium_rental_prices = []
    short_rental_prices = []

    for value in values:
        if value["rental_days"] >= 14:
            long_rental_prices.append(value["rental_price"])
        elif 14 > value["rental_days"] >= 11:
            medium_rental_prices.append(value["rental_price"])
        else:
            short_rental_prices.append(value["rental_price"])

    long_rental_price = (
        round(np.percentile(long_rental_prices, 70), 3) if long_rental_prices else 0
    )
    medium_rental_price = (
        round(np.percentile(medium_rental_prices, 70), 3) if medium_rental_prices else 0
    )
    short_rental_price = (
        round(np.percentile(short_rental_prices, 70), 3) if short_rental_prices else 0
    )

    return [
        [long_rental_price, len(long_rental_prices)],
        [medium_rental_price, len(medium_rental_prices)],
        [short_rental_price, len(short_rental_prices)]
    ]


def get_result(cards_list, length):
    result = []

    for card in cards_list:
        name = card["name"]
        rental_price = card["active_rentals"][length][0] if card["active_rentals"] else 0
        selling_price = card.get("price", None)

        if selling_price and rental_price:
            roi = (rental_price * 365) / (selling_price * 1000) * 100
            roi = round(roi, 2)
        else:
            roi = "N/A"

        result.append(
            {
                "name": name,
                "roi": roi,
                "avg rental price": rental_price,
                "cards rented": card["active_rentals"][length][1],
            }
        )

    result = sorted(
        result,
        key=lambda x: x["roi"] if x["roi"] != "N/A" else -float("inf"),
        reverse=True,
    )

    return result


def check_rental_roi(
    edition, types, rarity, foil, bcx, colours, length, session: requests.Session
):
    cards = get_cards(edition, types, rarity, colours, session)

    card_selling_prices = get_selling_prices(cards, foil, bcx, session)

    card_rentals = get_active_rentals(cards, foil, bcx, session)

    for card in card_rentals:
        updated_price = get_rental_prices(card["active_rentals"])
        card["active_rentals"] = updated_price

    merged_cards_dict = defaultdict(dict)

    for d in card_selling_prices + card_rentals:
        merged_cards_dict[d["id"]].update(d)

    merged_cards_list = list(merged_cards_dict.values())

    final_result = get_result(merged_cards_list, length)

    for result in final_result:
        print(result)

    return final_result


def main():
    edition = ["14"]  # Conclave Arcana
    types = ["Monster"]  # "Summoner" and/or "Monster"
    rarity = [1, 3]  # 1, 2, 3, and/or 4
    foil = 0  # 0 rf, 1 gold, 2 gold arcane, 3 black, 4 black arcane
    bcx = 1
    colours = []
    length = 0  # 0, 1 or 2

    try:
        with requests.Session() as session:
            result = check_rental_roi(
                edition, types, rarity, foil, bcx, colours, length, session
            )
    except (json.JSONDecodeError, KeyError) as e:
        logger.error(f"JSON decode error or missing key: {e}")
    except Exception as e:
        logger.error(f"An error occurred: {e}")


if __name__ == "__main__":
    main()
