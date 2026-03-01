"""
notify.py — Send SMS/MMS via Twilio.
"""

import os


def send_sms(message: str):
    """Send plain SMS."""
    from twilio.rest import Client
    client = _client()
    if not client:
        return
    msg = client.messages.create(
        body=message,
        from_=os.environ["TWILIO_FROM"],
        to=os.environ["TWILIO_TO"],
    )
    print(f"  [SMS] Sent — SID: {msg.sid}")


def send_mms(image_urls: list[str], caption: str = ""):
    """Send each image as a separate MMS."""
    from twilio.rest import Client
    client = _client()
    if not client:
        return

    for i, url in enumerate(image_urls, 1):
        body = caption if i == 1 else ""
        msg = client.messages.create(
            body=body,
            from_=os.environ["TWILIO_FROM"],
            to=os.environ["TWILIO_TO"],
            media_url=[url],
        )
        print(f"  [MMS {i}/{len(image_urls)}] Sent — SID: {msg.sid}")


def _client():
    sid   = os.environ.get("TWILIO_ACCOUNT_SID")
    token = os.environ.get("TWILIO_AUTH_TOKEN")
    if not all([sid, token]):
        print("  [SMS] Twilio credentials not set — skipping")
        return None
    from twilio.rest import Client
    return Client(sid, token)
