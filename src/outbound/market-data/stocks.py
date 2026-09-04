import requests
import json
from src.utils.jsonParser import create_json_file, parse_json_file
from src.outbound.header import get_header

def fetch_top_market_movers(dump_to_json, json_file_path):
    url = "https://data.alpaca.markets/v1beta1/screener/stocks/movers?top=10"
    headers = get_header()

    response = requests.get(url, headers=headers)

    if (dump_to_json and json_file_path):
        create_json_file(json_file_path, response)  # Create a JSON file with the response data

    return response.json()  # Return the JSON response directly

