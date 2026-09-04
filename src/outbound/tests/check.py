import requests
from src.outbound.header import get_header
from src.utils.jsonParser import create_json_file, parse_json_file

def check_greeks():
    resp = requests.get(
        "https://data.alpaca.markets/v1beta1/options/snapshots/AAPL",
        headers=get_header(),
        params={"feed": "indicative"},
    )

    if (resp.status_code == 200):
        data = resp
        print("Greeks data fetched successfully.")

        create_json_file("greeks_data.json", data)  # Save the data to a JSON file

check_greeks()