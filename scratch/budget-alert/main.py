import os
import json
import base64
import requests

TELEGRAM_TOKEN   = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

def send_budget_alert(event, context):
    pubsub_message = base64.b64decode(event["data"]).decode("utf-8")
    message_data   = json.loads(pubsub_message)

    budget_name   = message_data.get("budgetDisplayName", "Unknown Budget")
    cost_amount   = message_data.get("costAmount", 0)
    budget_amount = message_data.get("budgetAmount", 0)
    threshold     = message_data.get("alertThresholdExceeded", 0)
    project       = message_data.get("projectId", "Unknown Project")
    currency      = message_data.get("currencyCode", "INR")
    percentage    = int(threshold * 100)

    if percentage == 0:
        print("0% threshold — ignoring")
        return

    if percentage >= 100:
        status = "🔴 LIMIT REACHED — disable APIs immediately"
    elif percentage >= 90:
        status = "🔴 CRITICAL — approaching limit"
    elif percentage >= 50:
        status = "🟡 Monitor your spending"
    else:
        status = "🟢 Within safe range"

    message = f"""
🚨 *GCP Budget Alert*

📊 *Budget:* {budget_name}
🏗️ *Project:* {project}
💰 *Spent:* {currency} {cost_amount:.2f} of {budget_amount:.2f}
⚠️ *Threshold:* {percentage}% reached

{status}

🕐 Check: console.cloud.google.com/billing
"""

    response = requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        json={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    )

    if response.status_code == 200:
        print(f"✅ Alert sent: {percentage}% of budget used")
    else:
        print(f"❌ Failed: {response.text}")
