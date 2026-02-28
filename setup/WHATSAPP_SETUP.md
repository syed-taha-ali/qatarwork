# WhatsApp OTP Setup Guide (Whapi.cloud)

## What You'll Need

1. **Whapi.cloud Account**
2. **API Key** from your Whapi.cloud dashboard
3. **Channel ID** from your connected WhatsApp number

---

## Setup Steps

### Step 1: Get Your Credentials

1. Go to https://whapi.cloud/dashboard
2. Find your **API Key**

### Step 2: Add to `.env` File

Add this line to your `.env` file:

```env
# Email (you already have this)
SMTP_EMAIL=your-email@gmail.com
SMTP_PASSWORD=your-app-password

# WhatsApp (ADD THIS)
WHAPI_API_KEY=your-whapi-api-key-here
```


**Note:** You only need the API key! The channel is automatically determined from your API key.

### Step 3: Install Dependencies

```bash
pip install requests
```

(Or run `pip install -r requirements.txt` again)

### Step 4: Restart Server

```bash
uvicorn main:app --reload
```

---

## Testing

### With WhatsApp Configured:

1. Go to `/auth/register`
2. Fill in all fields (including phone number in international format)
   - Examples: `+97450001234` or `50001234` (Qatar assumed)
3. Click "Create Account"
4. Verify email (check your email inbox)
5. **Check your WhatsApp!** You should receive:
   ```
   🔐 QatarWork Verification
   
   Hello [Your Name]!
   
   Your phone verification code is:
   
   123456
   
   This code will expire in 5 minutes.
   ```
6. Enter the OTP code
7. Account created!

### Without WhatsApp (Console Fallback):

If you don't configure WhatsApp yet, the OTP will print to console:

```
============================================================
⚠️  WHATSAPP NOT CONFIGURED - OTP Code (Console)
============================================================
To: +97450001234
Name: Ahmed Hassan
OTP Code: 123456
============================================================
```

---

## Phone Number Format

The system accepts multiple formats and auto-converts:

| Input           | Converted To    |
|-----------------|-----------------|
| `50001234`      | `+97450001234`  |
| `05000 1234`    | `+97450001234`  |
| `974 5000 1234` | `+97450001234`  |
| `+974 5000 1234`| `+97450001234`  |

**Qatar numbers are assumed** if no country code is provided.

---

## Security Features

1. **5-minute expiration** on OTP codes
2. **Sequential verification:** Email → Phone → Account
3. **Cannot skip:** Both verifications required
4. **One-time use:** OTP deleted after successful verification
5. **Rate limiting:** Can resend OTP (generates new code)

---

## Registration Flow

```
Step 1: Fill Registration Form
   ↓
Step 2: Email Verification
   → Code sent to email
   → User enters code
   ↓
Step 3: Phone Verification  
   → OTP sent via WhatsApp
   → User enters OTP
   ↓
Step 4: Account Created!
   → Auto-login
   → Redirect to dashboard
```

---

## Troubleshooting

**"WhatsApp API error: 401"**
- Check your API key is correct
- Make sure there are no extra spaces in `.env`

**"WhatsApp API error: 400"**
- Phone number format issue
- Channel ID might be incorrect

**"Phone number is required"**
- Make sure phone field is filled in registration
- Cannot be left empty

**"OTP not received"**
- Check WhatsApp is connected to internet
- Verify phone number is correct
- Check server console for any errors

**"Console fallback - Code: xxxxxx"**
- WhatsApp credentials not set in `.env`
- Server couldn't reach Whapi.cloud API

---

## Whapi.cloud Limits

**Freemium Sandbox:**
- Free tier available
- Limited messages per month
- Perfect for testing/development

**Production:**
- Upgrade to paid plan for unlimited messages
- More reliable delivery
- Better support

---

## International Numbers

For non-Qatar numbers, include full country code:

- Saudi: `+966 50 123 4567`
- UAE: `+971 50 123 4567`
- USA: `+1 555 123 4567`

---

## Current Status

- Email verification (working)
- Phone verification (ready - needs credentials)
- Profile pictures (working)
- Full registration flow

Add your Whapi.cloud credentials and you're all set!
