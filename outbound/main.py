import requests
from header import get_header
from jsonParser import create_json_file, parse_json_file
import json

url = "https://data.alpaca.markets/v1beta1/screener/stocks/movers?top=10"
headers = get_header()

response = requests.get(url, headers=headers)

file_path = create_json_file("response.json", response) # Create a JSON file with the response data

print(response.text)