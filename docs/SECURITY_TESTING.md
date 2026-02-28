# Security Testing Guide - QatarWork Platform

## IMPORTANT WARNING

This guide is for **AUTHORIZED SECURITY TESTING ONLY** on your own development/testing environment.

**DO NOT** run these tests against:
- Production systems
- Systems you don't own
- Without explicit authorization

---

## Testing Versions Available

### 1. Production Version (main.py)
**Use for:** Normal operation, production deployment
**Features:**
- Full rate limiting (5/min auth, 100/min general)
- All security features enabled
- Production-ready

**Run with:**
```bash
uvicorn main:app --reload
```

### 2. Testing Version (main_testing.py)
**Use for:** Security testing with OWASP ZAP, Burp Suite, etc.
**Features:**
- Rate limiting DISABLED
- Security headers still active
- NOT FOR PRODUCTION

**Run with:**
```bash
uvicorn main_testing:app --reload
```

---

## OWASP ZAP Testing

### Setup

1. **Start Testing Server:**
   ```bash
   uvicorn main_testing:app --reload
   ```
   
   You should see:
   ```
   ⚠️  STARTING IN TESTING MODE - RATE LIMITING DISABLED ⚠️
   Security middleware initialized (TESTING MODE - NO RATE LIMITING)
   ```

2. **Open OWASP ZAP**

3. **Configure ZAP:**
   - Target URL: `http://127.0.0.1:8000`
   - Mode: Standard or Attack mode

---

## Recommended Tests

### 1. Automated Scan
```
ZAP > Automated Scan
Target: http://127.0.0.1:8000
```

**What it tests:**
- SQL Injection
- XSS (Cross-Site Scripting)
- Path Traversal
- CSRF
- Security Headers
- Cookie Security

### 2. Spider + Active Scan
```
ZAP > Spider: http://127.0.0.1:8000
Wait for completion...
ZAP > Active Scan: http://127.0.0.1:8000
```

**More thorough** - discovers all endpoints first

### 3. Manual Testing with ZAP Proxy

**Setup ZAP as Proxy:**
```
Browser Proxy Settings:
HTTP Proxy: 127.0.0.1
Port: 8080
```

**Manual test scenarios:**
1. Register account
2. Login
3. Upload documents
4. Send messages
5. Create jobs
6. Make bookings

ZAP will record and analyze all traffic.

---

## Test Coverage

### Authentication & Authorization

#### Test Cases:
- [ ] SQL injection in login form
- [ ] Brute force login attempts (now possible without rate limiting)
- [ ] Session hijacking attempts
- [ ] JWT token manipulation
- [ ] Privilege escalation (worker → admin)
- [ ] Password reset vulnerabilities

#### Expected Results:
- SQL injection blocked (ORM protection)
- Brute force possible (rate limiting disabled for testing)
- Session hijacking prevented (HTTP-only cookies)
- JWT manipulation detected (signature verification)
- Privilege escalation blocked (RBAC)

---

### Input Validation

#### Test Cases:
- [ ] XSS in registration fields
- [ ] XSS in job descriptions
- [ ] XSS in chat messages
- [ ] HTML injection
- [ ] SQL injection in search
- [ ] Path traversal in file uploads
- [ ] Malicious file uploads

#### Expected Results:
- XSS blocked (template auto-escaping + CSP)
- SQL injection blocked (parameterized queries)
- Path traversal prevented (sanitized filenames)
- File upload validation (check MIME types)

---

### File Upload Security

#### Test Cases:
- [ ] Upload .php, .exe, .sh files
- [ ] Upload oversized files (>10MB)
- [ ] Upload files with path traversal (../../etc/passwd)
- [ ] Double extension attacks (.jpg.php)

#### Test with:
```bash
curl -X POST http://127.0.0.1:8000/profile/documents/qid \
  -H "Cookie: session=<your-token>" \
  -F "side=front" \
  -F "file=@malicious.php"
```

#### Expected Results:
- Only .jpg, .jpeg, .png, .pdf allowed
- Files >10MB rejected
- Path traversal blocked
- Files stored outside web root

---

### Encryption Testing

#### Test Cases:
- [ ] Intercept messages in transit
- [ ] Check database for plaintext messages
- [ ] Try to decrypt messages without private key
- [ ] Man-in-the-middle attacks

#### Tools:
```bash
# Check database for encrypted content
sqlite3 qatar_work.db "SELECT content FROM messages LIMIT 5;"
```

#### Expected Results:
- Messages encrypted in database
- No plaintext in database
- HTTPS required for production

---

### API Security

#### Test Cases:
- [ ] CSRF attacks on state-changing operations
- [ ] Missing authentication on endpoints
- [ ] Insecure direct object references (IDOR)
- [ ] Mass assignment vulnerabilities

#### Example IDOR Test:
```bash
# Try to access another user's documents
curl http://127.0.0.1:8000/admin/documents/999/qid_front.jpg \
  -H "Cookie: session=<non-admin-token>"
```

#### Expected Results:
- 403 Forbidden (authorization check)
- Document access restricted to owner + admin
- RBAC enforced

---

### Security Headers

#### Test with:
```bash
curl -I http://127.0.0.1:8000
```

#### Expected Headers:
```http
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
Referrer-Policy: strict-origin-when-cross-origin
Content-Security-Policy: default-src 'self'; ...
```

**All should be present**

---

### WebSocket Security

#### Test Cases:
- [ ] WebSocket hijacking
- [ ] Message injection
- [ ] Authentication bypass
- [ ] Message flooding

#### Tools:
```bash
# wscat tool
npm install -g wscat
wscat -c "ws://127.0.0.1:8000/chats/ws/1?user_id=1"
```

#### Expected Results:
- Authentication required
- User can only access their own chats
- ⚠️  Message flooding possible (rate limiting disabled)

---

## ZAP Scan Results

### Understanding Alert Levels

| Level | Meaning | Action Required |
|-------|---------|-----------------|
| 🔴 High | Critical vulnerability | Fix immediately |
| 🟠 Medium | Significant risk | Fix soon |
| 🟡 Low | Minor issue | Consider fixing |
| ℹ️ Info | Best practice | Optional |

### Expected False Positives

Some ZAP alerts may be **false positives** for this app:

1. **"SQL Injection Possible"** in URLs with IDs
   - **False Positive** - Using ORM (SQLAlchemy)

2. **"Missing Anti-CSRF Tokens"** on GET requests
   - **Expected** - CSRF only needed for state-changing operations

3. **"Session cookie without Secure flag"**
   - **Expected in development** - Enable HTTPS in production

4. **"Incomplete or Missing Content-Security-Policy"**
   - **May need tuning** - Adjust CSP based on requirements

---

## Manual Testing Checklist

### Authentication
- [ ] Register with SQL injection in username: `admin'--`
- [ ] Register with XSS in name: `<script>alert(1)</script>`
- [ ] Login with wrong password 100 times (brute force test)
- [ ] Try to access admin panel as regular user
- [ ] Manipulate JWT token

### Authorization
- [ ] Access other user's chat: `/chats/999`
- [ ] View other user's documents: `/admin/documents/999/qid.jpg`
- [ ] Edit other user's profile
- [ ] Approve own verification application

### Input Validation
- [ ] Upload PHP file as profile picture
- [ ] Upload 100MB file
- [ ] Enter HTML in job description
- [ ] Enter JavaScript in bio

### Business Logic
- [ ] Book a job without sufficient funds
- [ ] Complete booking without worker confirmation
- [ ] Approve verification without uploading documents
- [ ] Send negative payment amount

---

## Reporting Vulnerabilities

### After Testing

1. **Document findings** in ZAP report:
   ```
   ZAP > Report > Generate HTML Report
   ```

2. **Categorize by severity:**
   - Critical (immediate fix)
   - High (fix before production)
   - Medium (fix soon)
   - Low (nice to have)

3. **Include:**
   - Vulnerability description
   - Steps to reproduce
   - Impact assessment
   - Recommended fix

---

## Clean Up After Testing

### 1. Stop Testing Server
```bash
# Press CTRL+C in terminal
```

### 2. Switch Back to Production Version
```bash
# Use main.py for normal operation
uvicorn main:app --reload
```

### 3. Clear Test Data
```bash
# Delete test accounts/data if needed
python seed.py  # Re-seed database
```

---

## Production Deployment Reminder

**CRITICAL:** Before deploying to production:

- [ ] Use `main.py` (NOT `main_testing.py`)
- [ ] Verify rate limiting is ENABLED
- [ ] Enable HTTPS
- [ ] Set strong SECRET_KEY
- [ ] Enable database encryption
- [ ] Configure WAF
- [ ] Set up monitoring

---

## Security Testing Tools

### Recommended Tools

1. **OWASP ZAP** (GUI)
   - Best for: Comprehensive scanning
   - Free and open source

2. **Burp Suite Community** (GUI)
   - Best for: Manual testing
   - Professional version has more features

3. **sqlmap** (CLI)
   - Best for: SQL injection testing
   ```bash
   sqlmap -u "http://127.0.0.1:8000/auth/login" --data="email=test@test.com&password=test"
   ```

4. **nikto** (CLI)
   - Best for: Web server scanning
   ```bash
   nikto -h http://127.0.0.1:8000
   ```

5. **nmap** (CLI)
   - Best for: Port scanning
   ```bash
   nmap -sV 127.0.0.1
   ```

---

## Contact

**Security Issues:** nbstaha@gmail.com

**Testing Questions:** Check ***documentation/SECURITY.md*** for more details

---

Last Updated: February 28, 2026
Testing Version: 1.0.0