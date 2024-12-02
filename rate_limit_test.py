import requests
import time

url = "http://localhost:8000/api/auth/login/"
headers = {
    "Content-Type": "application/json",
}

payload = {
    "username": "testuser",
    "password": "password123",
}


num_requests = 40

# Track failed and successful requests
failed_requests = 0
successful_requests = 0


for i in range(num_requests):
    response = requests.post(url, json=payload, headers=headers)

    # Check if rate limit exceeded (status code 429)
    if response.status_code == 429:
        print(f"Rate limit exceeded at request {i + 1}.")
        break  # Stop after rate limit is exceeded

    if response.status_code == 200:
        successful_requests += 1
    else:
        failed_requests += 1

    print(f"Request {i + 1} status: {response.status_code}")

    # time.sleep(1)

print(f"\nTotal successful requests: {successful_requests}")
print(f"Total failed requests: {failed_requests}")
