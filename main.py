import imapclient
import email
from email.header import decode_header
import threading
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from google import genai
import aiofiles
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware

class PromtData(BaseModel):
    transaction_id:str

# FastAPI app
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
emails_database = "emails.txt"
# Gmail credentials
EMAIL_ACCOUNT = "najafali32304@gmail.com"
EMAIL_PASSWORD = "lumh szck uoht ymre"  # Use an App Password

# Specific sender's email
SPECIFIC_SENDER = "agentiapay@gmail.com"
client = genai.Client(api_key="AIzaSyBo2b6UyVbCepoxQwEgP91FFHx_v-bOAKI")

# Store captured emails
captured_emails = []
# Function to decode email subject and sender
def decode_header_value(value):
    decoded_value, encoding = decode_header(value)[0]
    if isinstance(decoded_value, bytes):
        decoded_value = decoded_value.decode(encoding if encoding else 'utf-8')
    return decoded_value

# Function to extract plain text content from email
def get_email_body(msg):
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                return part.get_payload(decode=True).decode(part.get_content_charset())
    else:
        return msg.get_payload(decode=True).decode(msg.get_content_charset())

# Function to capture emails using efficient IMAP IDLE
def capture_emails():
    with imapclient.IMAPClient("imap.gmail.com", ssl=True) as client:
        client.login(EMAIL_ACCOUNT, EMAIL_PASSWORD)
        client.select_folder("INBOX")

        print(f"🔄 Listening for new emails from: {SPECIFIC_SENDER} (Efficient IMAP IDLE)")

        while True:
            try:
                # Wait indefinitely for new emails (reducing quota usage)
                client.idle()
                responses = client.idle_check(timeout=None)  # Wait indefinitely
                client.idle_done()

                if responses:
                    # Fetch unseen emails from the specific sender
                    messages = client.search(["UNSEEN", "FROM", SPECIFIC_SENDER])
                    for msg_id in messages:
                        msg_data = client.fetch(msg_id, ["RFC822"])
                        raw_email = msg_data[msg_id][b"RFC822"]

                        # Parse email
                        msg = email.message_from_bytes(raw_email)
                        subject = decode_header_value(msg["Subject"])
                        sender = decode_header_value(msg.get("From"))
                        body = get_email_body(msg)
                        with open(emails_database,"a") as db:
                            db.write(str(body))

                        # Store the captured email
                        captured_emails.append({
                            "From": sender,
                            "Subject": subject,
                            "Body": body,
                        })

                        print(f"\n📩 New Email Received:")
                        print(f"From: {sender}")
                        print(f"Subject: {subject}")
                        print(f"Body: {body}")

            except Exception as e:
                print(f"⚠️ Error: {e}")

# FastAPI route to get the captured emails
@app.get("/emails")
async def get_emails():
    return JSONResponse(content=captured_emails)

# Start email capturing in a background thread on startup
@app.on_event("startup")
async def on_startup():
    threading.Thread(target=capture_emails, daemon=True).start()


@app.post("/id")
async def Id(data:PromtData):
    async with aiofiles.open(emails_database, "r") as f:
        read_data = await f.readlines()

    response = client.models.generate_content(
    model="gemini-2.0-flash", contents=f"""
        You are an AI that strictly follows instructions. 
        Do not return any code, function, or explanation.

        Check if transaction ID '{data.transaction_id}' exists in the following data:
        {str(read_data)}

        If found, respond with exactly: Payment Successful
        If not found, respond with exactly: Please make the payment first

        Do not add extra text or formatting. Respond only with one of the two phrases.
        """
)
    llm_response = response.text
    # print(llm_response)
    # captured_emails.append(llm_response)
    return llm_response

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
