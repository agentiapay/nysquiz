import asyncio
import email
from email.header import decode_header
from aioimaplib import IMAP4_SSL
from fastapi import FastAPI
from fastapi.responses import JSONResponse

EMAIL_ACCOUNT = "najafali32304@gmail.com"
EMAIL_PASSWORD = "lumh szck uoht ymre"
SPECIFIC_SENDER = "agentiapay@gmail.com"

app = FastAPI()
captured_emails = []

def decode_header_value(value):
    if not value:
        return ""  # Return empty string if value is None or empty
    decoded_parts = decode_header(value)
    if not decoded_parts:
        return ""
    decoded_value, encoding = decoded_parts[0]
    if isinstance(decoded_value, bytes):
        return decoded_value.decode(encoding or 'utf-8', errors='ignore')
    return decoded_value

def get_email_body(msg):
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain" and not part.get("Content-Disposition"):
                return part.get_payload(decode=True).decode(part.get_content_charset() or 'utf-8')
    else:
        return msg.get_payload(decode=True).decode(msg.get_content_charset() or 'utf-8')

async def listen_for_emails():
    while True:
        try:
            client = IMAP4_SSL("imap.gmail.com")
            await client.wait_hello_from_server()
            await client.login(EMAIL_ACCOUNT, EMAIL_PASSWORD)
            await client.select("INBOX")

            print(f"🔄 Listening for new emails from: {SPECIFIC_SENDER}")

            while True:
                idle = await client.idle_start(timeout=29 * 60)  # Gmail kills idle after ~30 min
                while client.has_pending_idle():
                    msg = await client.wait_server_push()
                    if msg and b"EXISTS" in msg[1]:
                        await client.idle_done()
                        await asyncio.wait_for(idle, timeout=5)

                        result, data = await client.search("UNSEEN")
                        if result == "OK":
                            for uid in data[0].split():
                                res, msg_data = await client.fetch(uid, "(RFC822)")
                                if res == "OK":
                                    raw_email = msg_data[1][1]
                                    email_msg = email.message_from_bytes(raw_email)

                                    sender = decode_header_value(email_msg.get("From"))
                                    if SPECIFIC_SENDER in sender:
                                        subject = decode_header_value(email_msg.get("Subject"))
                                        body = get_email_body(email_msg)

                                        captured_emails.append({
                                            "From": sender,
                                            "Subject": subject,
                                            "Body": body
                                        })

                                        print("\n📩 New Email Received:")
                                        print(f"From: {sender}")
                                        print(f"Subject: {subject}")
                                        print(f"Body: {body}")
                        break

        except Exception as e:
            print(f"⚠️ Error occurred: {e}. Retrying in 5 seconds...")
            await asyncio.sleep(5)
@app.get("/")
async def home():
    return {"status":"ok"}
@app.on_event("startup")
async def start_email_listener():
    asyncio.create_task(listen_for_emails())

@app.get("/emails")
def get_emails():
    return JSONResponse(content=captured_emails)
