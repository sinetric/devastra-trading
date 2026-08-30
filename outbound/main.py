import requests
import json

url = "https://data.alpaca.markets/v1beta1/screener/stocks/movers?top=10"

headers = {
    "accept": "application/json",
    "APCA-API-KEY-ID": "PKDAEDLCFQZDZDVVD75HVL7VSY",
    "APCA-API-SECRET-KEY": "DbGHrFbLK7CUL7qUY78zHeQiop51tb72Tj8fTNxWmm9d"
}

response = requests.get(url, headers=headers)

print(response.text)

with open("response.json", "w") as json_file:
    json.dump(response.text, json_file, indent=4)