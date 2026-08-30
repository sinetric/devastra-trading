import requests
import json

url = "https://data.alpaca.markets/v1beta1/screener/stocks/movers?top=10"

response = requests.get(url, headers=headers)

print(response.text)

with open("response.json", "w") as json_file:
    json.dump(response.text, json_file, indent=4)