import imaplib
import email
from email.header import decode_header
from fastapi import FastAPI
from pydantic import BaseModel
from google import genai
from fastapi.middleware.cors import CORSMiddleware
import threading
import time
import select

# Email Settings
IMAP_SERVER = "imap.gmail.com"
EMAIL_ACCOUNT = "najafali32304@gmail.com"
EMAIL_PASSWORD = "mypi yoof teqz gygl"  # Use App Password if 2FA is enabled
SPECIFIC_SENDER = "agentiapay@gmail.com"
emails = "emails.txt"  # File to store captured emails

# FastAPI App
app = FastAPI()

# ✅ Allow frontend requests from GitHub Codespaces & localhost
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  
        "https://legendary-chainsaw-q769g7v7qx6424gwr-8000.app.github.dev"
    ],
    allow_credentials=True,
    allow_methods=["*"],  
    allow_headers=["*"],  
)

# Define Request Model for Transaction ID
class TransactionRequest(BaseModel):
    transaction_id: str

# IMAP IDLE Listener Function
def imap_idle():
    while True:
        try:
            print("📩 Listening for new emails...")
            mail = imaplib.IMAP4_SSL(IMAP_SERVER)
            mail.login(EMAIL_ACCOUNT, EMAIL_PASSWORD)
            mail.select("inbox")

            # Start IMAP IDLE mode
            mail.send(b"IDLE\r\n")
            response = mail.readline()

            # Use select() to wait for changes in the mailbox
            if response.startswith(b"+ idling"):
                while True:
                    ready, _, _ = select.select([mail.socket()], [], [], None)  # Block until an email arrives
                    if ready:
                        mail.send(b"DONE\r\n")  # Exit IDLE mode
                        break  # New email detected, process it

            # Fetch the latest email
            fetch_latest_email()
            mail.close()
            mail.logout()
        except Exception as e:
            print(f"❌ IMAP Error: {e}")
            time.sleep(5)  # Wait and retry if an error occurs

# Fetch Latest Email
def fetch_latest_email():
    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER)
        mail.login(EMAIL_ACCOUNT, EMAIL_PASSWORD)
        mail.select("inbox")

        # Search for unread emails from the specific sender
        _, messages = mail.search(None, f'(UNSEEN FROM "{SPECIFIC_SENDER}")')
        email_ids = messages[0].split()

        if not email_ids:
            return {"status": "no_new_email"}

        latest_email_id = email_ids[-1]  
        _, msg_data = mail.fetch(latest_email_id, "(RFC822)")

        for response_part in msg_data:
            if isinstance(response_part, tuple):
                msg = email.message_from_bytes(response_part[1])
                
                # Decode Subject
                subject, encoding = decode_header(msg["Subject"])[0]
                if isinstance(subject, bytes):
                    subject = subject.decode(encoding or "utf-8")

                # Extract Email Body (Plain Text)
                body = ""
                if msg.is_multipart():
                    for part in msg.walk():
                        content_type = part.get_content_type()
                        content_disposition = str(part.get("Content-Disposition"))

                        if content_type == "text/plain" and "attachment" not in content_disposition:
                            body = part.get_payload(decode=True).decode()
                            break  
                else:
                    body = msg.get_payload(decode=True).decode()

                emails_data = {
                    "status": "success",
                    "subject": subject,
                    "body": body.strip()
                }
                print("✅ New Email Captured:", emails_data)
                
                with open(emails, "a") as add_emails:
                    add_emails.write(str(emails_data) + "\n")

                return emails_data

    except Exception as e:
        return {"status": "error", "message": str(e)}

# Start IMAP IDLE in a separate thread
threading.Thread(target=imap_idle, daemon=True).start()

# API to Retrieve All Saved Emails
@app.get("/get-emails")
async def get_saved_emails_api():
    return {"status": "success", "emails": fetch_latest_email()}

# API to Verify Transaction
@app.post("/id")
async def verify_transaction(request: TransactionRequest):
    transaction_id = request.transaction_id
    print(f"Received Transaction ID: {transaction_id}")

    with open(emails, "r") as data:
        read_data = data.read()

    client = genai.Client(api_key="AIzaSyBo2b6UyVbCepoxQwEgP91FFHx_v-bOAKI")

    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=f"Check if transaction ID {transaction_id} exists in {read_data}. If it exists, return 'Payment Successful'; otherwise, return 'Please make the payment first.' no extra explanation"
    )
    
    llm_response = response.text
    print(llm_response)
    
    return {"status": llm_response}
