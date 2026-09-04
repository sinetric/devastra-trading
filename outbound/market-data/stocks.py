import requests
import json
from header import get_header

class TopMarketMovers:
    def __init__(self):
        self.url = "https://data.alpaca.markets/v1beta1/screener/stocks/movers?top=10"
        self.headers = get_header()

    def fetch(self):
        response = requests.get(self.url, headers=self.headers)
        return response.json()  # Return the JSON response directly

