import httpx
import time

url = "http://127.0.0.1:8000/api/chat"
payload = {"message": "Order me a pizza"}

for i in range(20):
    try:
        r = httpx.post(url, json=payload, timeout=10.0)
        print('STATUS', r.status_code)
        print(r.text)
        break
    except Exception as e:
        print('retry', i, e)
        time.sleep(0.5)
