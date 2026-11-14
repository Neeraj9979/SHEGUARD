"""Optional Twilio-backed SMS delivery for emergency alerts."""
import os


def send_emergency_sms(to_number, message):
    """Send an SMS if Twilio is configured; otherwise report a safe failure."""
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    from_number = os.getenv("TWILIO_PHONE_NUMBER")

    if not all((account_sid, auth_token, from_number)):
        return {"success": False, "sid": None,
                "error": "Twilio credentials are not configured."}

    try:
        from twilio.rest import Client
        result = Client(account_sid, auth_token).messages.create(
            body=message, from_=from_number, to=to_number
        )
        return {"success": True, "sid": result.sid, "error": None}
    except Exception as exc:
        return {"success": False, "sid": None, "error": str(exc)}
