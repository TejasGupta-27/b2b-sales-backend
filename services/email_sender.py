import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from email.mime.text import MIMEText

# ✅ Load environment variables from .env in the same directory
from dotenv import load_dotenv
dotenv_path = os.path.join(os.path.dirname(__file__), "..", ".env")
load_dotenv(dotenv_path)
print("📩 Loaded email:", os.getenv("GMAIL_ADDRESS"))
print("🔑 Loaded app password length:", len(os.getenv("GMAIL_APP_PASSWORD", "")))


def send_quote_email(quote, ppt_path, pdf_path):
    customer_info = quote.get("customer_info", {})
    user_email = customer_info.get("email")
    
    from_email = os.getenv("GMAIL_ADDRESS")
    app_password = os.getenv("GMAIL_APP_PASSWORD")

    if not from_email or not app_password:
        raise ValueError("GMAIL_ADDRESS or GMAIL_APP_PASSWORD environment variables are missing")

    if not user_email:
        raise ValueError("Recipient email is missing in quote customer_info")

    msg = MIMEMultipart()
    msg['From'] = from_email
    msg['To'] = user_email
    msg['Subject'] = f"Your Quotation - {quote.get('quote_title', 'Solution')}"

    body = (
        f"Dear {customer_info.get('contact', 'Customer')},\n\n"
        "Please find attached your quotation and presentation deck.\n\n"
        "Best regards,\nSales Assistant Bot"
    )
    msg.attach(MIMEText(body, 'plain'))

    # Attach files
    for path in [pdf_path, ppt_path]:
        if path and os.path.exists(path):
            with open(path, "rb") as file:
                part = MIMEApplication(file.read(), Name=os.path.basename(path))
                part['Content-Disposition'] = f'attachment; filename="{os.path.basename(path)}"'
                msg.attach(part)
    print(f"Sending email from: {from_email} to: {user_email}")
    server = smtplib.SMTP("smtp.gmail.com", 587)
    server.starttls()
    server.login(from_email, app_password)
    server.send_message(msg)
    server.quit()
    print('Sent email.')

# ----------------------- Test block -----------------------

if __name__ == "__main__":
    # Full paths relative to this script (services/)
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    ppt_path = os.path.join(base_dir, "Data", "presentations", "quote_anon_deck.pptx")
    pdf_path = os.path.join(base_dir, "Data", "quotes", "quote_4d4ead1e.pdf")

    quote = {
        "quote_title": "Vertex Innovations Workstation Proposal",
        "customer_info": {
            "email": "nandininithyasandeep@gmail.com",   # 🔁 Replace with your own test address
            "contact": "Nandini Nithya Sandeep"
        }
    }

    send_quote_email(quote, ppt_path, pdf_path)
