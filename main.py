import imaplib
import email
from email.header import decode_header
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import firebase_admin
from firebase_admin import credentials, firestore

# Firebase initialization
cred = credentials.Certificate('credentials.json')  # Path to your Firebase credentials JSON file
firebase_admin.initialize_app(cred)
db = firestore.client()
emails_ref = db.collection('captured_emails')  # Collection to store emails

# Email and sender details
EMAIL_ACCOUNT = "najafali32304@gmail.com"
EMAIL_PASSWORD = "lumh szck uoht ymre"
SPECIFIC_SENDER = "agentiapay@gmail.com"

# FastAPI app setup
app = FastAPI()

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://psychic-spoon-jj94wjrj5gg4fj5x4-3000.app.github.dev"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# home end point
@app.get("/")
def Home():
    return {"status":"ok"}
@app.get("/health")
def health_check():
    return {"status": "ok"}
    
# Pydantic model to capture ID from frontend
class getId(BaseModel):
    id: str

# Decode email header
def decode_header_value(value):
    if not value:
        return ""
    decoded_parts = decode_header(value)
    decoded_value, encoding = decoded_parts[0]
    if isinstance(decoded_value, bytes):
        return decoded_value.decode(encoding or "utf-8", errors="ignore")
    return decoded_value

# Extract email body
def get_email_body(msg):
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain" and not part.get("Content-Disposition"):
                return part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8")
    else:
        return msg.get_payload(decode=True).decode(msg.get_content_charset() or "utf-8")

# LLM response for transaction ID verification
from google import genai
client = genai.Client(api_key="AIzaSyAxz3kNZLBz2PH124b-pfqVuulj960QvKo")

# Endpoint to poll emails
@app.get("/poll-emails")
def poll_emails():
    try:
        # Connect to Gmail IMAP server
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(EMAIL_ACCOUNT, EMAIL_PASSWORD)
        mail.select("inbox")

        # Search for unseen emails
        result, data = mail.search(None, "UNSEEN")
        email_ids = data[0].split()

        new_emails = []
        
        # Loop through each email
        for eid in email_ids:
            res, msg_data = mail.fetch(eid, "(RFC822)")
            if res == "OK":
                raw_email = msg_data[0][1]
                msg = email.message_from_bytes(raw_email)
                sender = decode_header_value(msg.get("From"))
                
                if SPECIFIC_SENDER in sender:
                    body = get_email_body(msg)
                    new_emails.append(body)

                    # Store email in Firestore (instead of appending to .txt file)
                    email_data = {
                        'body': body
                    }
                    emails_ref.add(email_data)

        # Logout from the email server
        mail.logout()
        return {"status": "emails captured and stored in Firestore"}

    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)


# Endpoint to verify transaction ID
@app.post("/id")
def Id(userId: getId):
    # Fetch emails from Firestore to search for the Transaction ID
    emails = emails_ref.stream()
    email_texts = ""
    for email_doc in emails:
        email_data = email_doc.to_dict()
        email_texts += email_data.get('body', '')  # Concatenate all email bodies

    # Use the LLM to check the transaction ID in the emails
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=f"""
        Search for the given Transaction ID: '{userId.id}' within the string representation of the provided data: '{email_texts}'.
        If the ID is found, return the string "payment successful".
        Otherwise, return "make payment first". response output must be in one line. You are AI, so follow these instructions.
        """
    )

    llm_response = str(response.text)
    print(llm_response)
    return llm_response.strip()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
