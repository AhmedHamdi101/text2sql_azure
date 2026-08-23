import requests
import os

PROJECT_ENDPOINT = os.environ["AZURE_FOUNDRY_PROJECT_ENDPOINT"]
API_KEY = os.environ["AZURE_FOUNDRY_API_KEY"]

url = f"{PROJECT_ENDPOINT.rstrip('/')}/deployments?api-version=v1"

headers = {
    "api-key": API_KEY
}

response = requests.get(url, headers=headers)

print("Status:", response.status_code)
print(response.text)