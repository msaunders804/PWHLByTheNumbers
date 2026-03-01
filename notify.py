"""
notify.py — Send SMS via Twilio.
"""

import os


def send_sms(message: str):
    """Send SMS using Twilio credentials from environment."""
    from twilio.rest import Client

    account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
    auth_token  = os.environ.get("TWILIO_AUTH_TOKEN")
    from_number = os.environ.get("TWILIO_FROM")
    to_number   = os.environ.get("TWILIO_TO")

    if not all([account_sid, auth_token, from_number, to_number]):
        print("  [SMS] Twilio credentials not set — skipping")
        return

    client = Client(account_sid, auth_token)
    msg = client.messages.create(
        body=message,
        from_=from_number,
        to=to_number
    )
    print(f"  [SMS] Sent — SID: {msg.sid}")
