#import requests

#API_KEY = "783045f8fc50a065978f55282dd358db0b790716"
#url = "https://cryptopanic.com/api/v1/post/"
#params = {"auth_token": API_KEY, "currencies": "BTC", "filter": "important"}

#response = requests.get(url, params=params)
#print(response.status_code)
#print(response.json())

import requests

API_KEY = "783045f8fc50a065978f55282dd358db0b790716"
url = "https://cryptopanic.com/api/developer/v2/posts/"
params = {
    "auth_token": API_KEY,
    "currencies": "BTC,ETH,SOL,LINK",
    "filter": "important"
}

try:
    response = requests.get(url, params=params, timeout=10)
    print(f"Status: {response.status_code}")
    print(response.text)
except Exception as e:
    print(f"Error: {e}")