# Email Verification Setup Guide

## Option 1: Gmail (Recommended for Testing)

### Step 1: Enable 2-Factor Authentication
1. Go to your Google Account: https://myaccount.google.com/
2. Select "Security"
3. Enable "2-Step Verification"

### Step 2: Create App Password
1. Go to https://myaccount.google.com/apppasswords
2. Select "Mail" and "Other (Custom name)"
3. Name it "QatarWork"
4. Click "Generate"
5. **Copy the 16-character password** (e.g., `abcd efgh ijkl mnop`)

### Step 3: Set Environment Variables

**Windows (PowerShell):**
```powershell
$env:SMTP_EMAIL="your-email@gmail.com"
$env:SMTP_PASSWORD="your-app-password"
```

**Linux/Mac:**
```bash
export SMTP_EMAIL="your-email@gmail.com"
export SMTP_PASSWORD="your-app-password"
```

**Or create `.env` file in project root:**
```env
SMTP_EMAIL=your-email@gmail.com
SMTP_PASSWORD=abcdefghijklmnop
```

Then install python-dotenv:
```bash
pip install python-dotenv
```

And add to `main.py`:
```python
from dotenv import load_dotenv
load_dotenv()
```

### Step 4: Restart Server
```bash
uvicorn main:app --reload
```

Now emails will be sent to real email addresses!

---

## Option 2: SendGrid (Production Ready)

### Step 1: Create Account
1. Go to https://sendgrid.com/
2. Sign up (free tier: 100 emails/day)
3. Verify your email

### Step 2: Create API Key
1. Go to Settings → API Keys
2. Click "Create API Key"
3. Give it a name: "QatarWork"
4. Select "Full Access"
5. Copy the API key

### Step 3: Update Code
In `email_service.py`, replace Gmail SMTP with SendGrid:

```python
import sendgrid
from sendgrid.helpers.mail import Mail, Email, To, Content

def send_verification_email(to_email: str, verification_code: str, full_name: str) -> bool:
    SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY", "")
    
    sg = sendgrid.SendGridAPIClient(api_key=SENDGRID_API_KEY)
    from_email = Email("noreply@qatarwork.com")
    to_email = To(to_email)
    subject = "QatarWork - Email Verification Code"
    content = Content("text/html", html_body)
    
    mail = Mail(from_email, to_email, subject, content)
    response = sg.client.mail.send.post(request_body=mail.get())
    return response.status_code == 202
```

---

## Option 3: Mailgun (Alternative)

Similar to SendGrid, but with different API:
- Free tier: 5,000 emails/month for 3 months
- https://www.mailgun.com/

---

## Testing

After setup, register a new account:
1. Fill registration form with YOUR real email
2. Click "Create Account"
3. Check your email inbox
4. Copy the 6-digit code
5. Enter it on verification page
6. Account created!

---

## Troubleshooting

**"Authentication failed":**
- Make sure you're using an App Password, not your regular Gmail password
- Double-check the email and password are correct

**"Email not received":**
- Check spam/junk folder
- Verify SMTP credentials are set correctly
- Check server console for error messages

**"SMTP NOT CONFIGURED" message:**
- Environment variables not set
- Restart server after setting variables
- Make sure variables are in correct format (no quotes in PowerShell)

---

## Current Behavior

- **WITH credentials:** Real emails sent via Gmail
- **WITHOUT credentials:** Code printed to console (fallback for testing)
