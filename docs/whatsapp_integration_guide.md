# WhatsApp Business Integration Guide
## RDL Sales Intelligence Platform

---

## Table of Contents
1. [Why WhatsApp Business Cloud API?](#1-why-whatsapp-business-cloud-api)
2. [How It Will Work in Your App](#2-how-it-will-work-in-your-app)
3. [What You Need Before Starting](#3-what-you-need-before-starting)
4. [Step 1 — Create a Meta Developer Account](#step-1--create-a-meta-developer-account)
5. [Step 2 — Create a Meta Business App](#step-2--create-a-meta-business-app)
6. [Step 3 — Add WhatsApp to Your App](#step-3--add-whatsapp-to-your-app)
7. [Step 4 — Get Your Phone Number ID](#step-4--get-your-phone-number-id)
8. [Step 5 — Create a Permanent Access Token](#step-5--create-a-permanent-access-token)
9. [Step 6 — Configure the Webhook](#step-6--configure-the-webhook)
10. [Step 7 — Connect Account in RDL Dashboard](#step-7--connect-account-in-rdl-dashboard)
11. [Step 8 — Test the Integration](#step-8--test-the-integration)
12. [Understanding Auto Mode vs Draft Mode](#understanding-auto-mode-vs-draft-mode)
13. [Pricing & Free Tier Explained](#pricing--free-tier-explained)
14. [Common Errors & Fixes](#common-errors--fixes)
15. [Going Live Checklist](#going-live-checklist)

---

## 1. Why WhatsApp Business Cloud API?

### Why WhatsApp at all?
India is one of the largest WhatsApp markets in the world. Most B2B buyers — especially from platforms like IndiaMart, TradeIndia, and JustDial — prefer WhatsApp for quick product inquiries over email. Many customers will message you on WhatsApp before or instead of sending an email.

Without integration, those messages sit in a personal WhatsApp app with no AI support, no logging, no lead creation, and no auto-reply.

### Why Meta's Cloud API (not Twilio or other providers)?
There are three ways to use WhatsApp for business:

| Option | Cost | Complexity | Control |
|--------|------|-----------|---------|
| **Meta Cloud API (what we use)** | Free API, pay only per conversation | Medium setup, no hosting | Full control, direct |
| Twilio WhatsApp | ~$0.005/message EXTRA on top of Meta | Easier setup | Less control, Twilio middleman |
| WhatsApp Business App | Free but manual only | No API | Not automatable |

**Meta Cloud API is the right choice** because:
- No per-message fee from a middleman
- Direct access to all WhatsApp features
- Scales without cost explosion
- Same quality as what large companies use (Zomato, Swiggy, banks)

---

## 2. How It Will Work in Your App

Here is the full flow, end to end:

```
Customer sends WhatsApp message
        ↓
Meta pushes it to your server (webhook POST)
        ↓
AI classifies the message (Sales / Support / Grievance / etc.)
        ↓
AI creates a lead in your CRM (if new customer)
        ↓
AI detects which product they're asking about (RAG search)
        ↓
AI generates a reply using your product knowledge base
        ↓
     ┌──────────────────────────────────────┐
     │ No gaps + auto_send ON?              │
     │  YES → Send reply automatically      │
     │  NO  → Save as draft for you to      │
     │         review and approve in UI     │
     └──────────────────────────────────────┘
        ↓
You see all conversations in WhatsApp Inbox page
(Same as Gmail Inbox but for WhatsApp)
```

**Modes:**
- **Auto Mode** — AI replies instantly, no human needed (when it's confident and all questions answered)
- **Draft Mode** — AI writes the reply but holds it. You review, edit if needed, and click "Send via WhatsApp"

---

## 3. What You Need Before Starting

Before you begin the setup steps, make sure you have:

- [ ] A **Facebook account** (personal is fine — used only as admin)
- [ ] A **registered business** or business name (Meta verifies this)
- [ ] A **phone number** that is NOT currently registered on WhatsApp (your business SIM or a virtual number)
  - Why? A phone number can only be on ONE WhatsApp at a time — personal OR business API, not both
  - If your current number is on WhatsApp personal, you need a separate SIM or a virtual number (like a Jio business SIM)
- [ ] Your backend is publicly accessible (your URL: `https://118-139-165-99.nip.io:8443`)
  - Why? Meta needs to reach your server to send you incoming messages via webhook

---

## Step 1 — Create a Meta Developer Account

**Why:** Meta requires all API users to be registered developers. This is a one-time process.

1. Open [https://developers.facebook.com](https://developers.facebook.com) in your browser
2. Click **Get Started** (top right)
3. Log in with your Facebook account
4. Meta will ask you to verify your account — enter your phone number and confirm the OTP
5. Accept the developer terms

**You should see:** The Meta for Developers dashboard with "My Apps" at the top.

---

## Step 2 — Create a Meta Business App

**Why:** The "app" is your server-side integration. It holds your API credentials, webhook settings, and permissions.

1. Go to [https://developers.facebook.com/apps](https://developers.facebook.com/apps)
2. Click **Create App** (green button)
3. On the "What do you want your app to do?" screen, choose **Other**
4. On the next screen, choose **Business** as the app type
   - Why Business? The Business type gives access to WhatsApp Business APIs. Consumer type does not.
5. Fill in:
   - **App name:** `RDL Sales Bot` (or any name)
   - **App contact email:** your email
   - **Business Account:** if you have a Meta Business Manager account, select it. If not, skip for now.
6. Click **Create App** — Meta may ask you to re-enter your Facebook password for security

**You should see:** Your new app's dashboard with a list of products you can add.

---

## Step 3 — Add WhatsApp to Your App

**Why:** By default your Meta app has no capabilities. You must explicitly add WhatsApp to unlock the messaging API.

1. On your app dashboard, scroll down to find **WhatsApp** in the product list
2. Click **Set up** next to WhatsApp
3. Meta will ask you to connect a **WhatsApp Business Account (WABA)**
   - A WABA is the business-level account that owns your WhatsApp phone numbers
   - Click **Create a new business account**
   - Enter your business name (e.g. "RDL Technologies")
   - Click **Continue**
4. Meta creates your WABA and takes you to the WhatsApp setup page

**Copy and save your WABA ID:**
- On the WhatsApp API Setup page, you'll see **WhatsApp Business Account ID**
- It looks like: `123456789012345`
- Save this — you'll need it later

---

## Step 4 — Get Your Phone Number ID

**Why:** Every WhatsApp number has a unique "Phone Number ID" that the API uses to send/receive messages. It's different from the actual phone number.

### Option A — Use the Free Test Number (Recommended for testing first)

Meta gives every new app a free test phone number automatically.

1. On the **WhatsApp → API Setup** page, under **From**, you'll see a number like `+1 555-XXX-XXXX`
2. Below it, you'll see **Phone Number ID** — a long number like `987654321098765`
3. Copy this Phone Number ID

**Limitation of test number:** You can only message 5 specific phone numbers that you manually verify. Good for testing, not for real customers.

### Option B — Add Your Real Business Number (for production)

1. On **WhatsApp → API Setup**, click **Add phone number**
2. Enter the phone number (must NOT be registered on any WhatsApp)
3. Choose verification method: SMS or Voice call
4. Enter the OTP you receive
5. Once verified, the number appears in the **From** dropdown with its own Phone Number ID

**Copy the Phone Number ID** for the number you want to use.

---

## Step 5 — Create a Permanent Access Token

**Why:** Meta gives you a temporary token by default that expires every 24 hours. For a production AI bot that runs automatically, you need a permanent token that never expires.

**This is the most important step — follow carefully.**

1. Open a new tab and go to [https://business.facebook.com](https://business.facebook.com)
2. In the left sidebar, click the **Settings** gear icon (⚙️)
3. Go to **Users** → **System Users**
4. Click **Add** (blue button)
   - **System user name:** `rdl-sales-bot`
   - **System user role:** Admin
   - Click **Create system user**
5. The system user appears in the list. Click on it.
6. Click **Generate New Token** (blue button)
7. On the token creation screen:
   - **Select App:** Choose the app you created in Step 2 (`RDL Sales Bot`)
   - **Token expiration:** Choose **Never**
   - Under **Permissions**, check these two:
     - `whatsapp_business_messaging` ← to send/receive messages
     - `whatsapp_business_management` ← to manage phone numbers and settings
8. Click **Generate Token**
9. **A popup shows your token** — it looks like: `EAAxxxxx...` (very long string)
10. **COPY IT IMMEDIATELY** — Meta only shows it once. If you close the popup without copying, you must generate a new one.

Store it securely (password manager or environment file). This is your permanent access token.

---

## Step 6 — Configure the Webhook

**Why:** Unlike Gmail (where your server polls for new emails), WhatsApp works the opposite way — Meta's servers push new messages to your server in real time. The webhook is the URL Meta calls when a customer sends you a message.

### Part A — Set Your Webhook URL in Meta

1. Go back to your Meta app: [https://developers.facebook.com/apps](https://developers.facebook.com/apps) → select your app
2. In the left sidebar, go to **WhatsApp** → **Configuration**
3. Under **Webhook**, click **Edit**
4. Fill in:
   - **Callback URL:** `https://118-139-165-99.nip.io:8443/api/v1/whatsapp/webhook`
   - **Verify Token:** Choose any secret string you want, for example: `rdl_wa_verify_2026`
     - Why? When Meta calls your webhook for the first time, it sends this token. Your server checks it matches what you configured, proving it's really Meta calling you.
5. Click **Verify and Save**
   - Meta will immediately call your server to verify. Your backend will respond correctly.
   - If verification fails, your backend is not reachable — check that docker is running and the URL is correct.

### Part B — Subscribe to Message Events

After saving the webhook URL:
1. Under **Webhook fields**, find **messages** and click **Subscribe**
   - Why? By default Meta doesn't send you anything. You must subscribe to specific event types. "messages" is the one that fires when a customer sends you a WhatsApp message.
2. You can also subscribe to **message_deliveries** and **message_reads** (optional — for delivery receipts)

**You should see:** The webhook shows a green checkmark and "Subscribed" next to "messages".

---

## Step 7 — Connect Account in RDL Dashboard

**Why:** Your backend needs to know your WhatsApp credentials to send replies and verify incoming webhooks. You store these in the RDL app (not hardcoded in code).

1. Open your RDL Sales dashboard
2. Go to **WhatsApp Inbox** in the left sidebar (once the integration is re-enabled)
3. Click **+ Connect Account** (top right)
4. Fill in the form:

| Field | What to enter | Where to find it |
|-------|--------------|-----------------|
| **Phone Number ID** | The long number ID of your WhatsApp number | WhatsApp → API Setup → Phone Number ID |
| **WABA ID** | Your WhatsApp Business Account ID | WhatsApp → API Setup → WhatsApp Business Account |
| **Display Phone Number** | Your actual phone number | e.g. `+919876543210` |
| **Display Name** | Name shown in UI | e.g. "RDL Technologies Sales" |
| **Permanent Access Token** | The `EAAxxxx...` token from Step 5 | Paste it here |
| **Webhook Verify Token** | The secret string you set in Step 6 | e.g. `rdl_wa_verify_2026` |
| **Enable Auto-Send** | Checkbox | Turn ON for full automation, OFF for draft-only mode |

5. Click **Connect Account**

Your WhatsApp account is now connected. The dashboard will show your phone number as an account pill at the top of the inbox.

---

## Step 8 — Test the Integration

### Test 1 — Verify webhook is receiving messages

1. On the Meta Developer dashboard: **WhatsApp → API Setup**
2. Under **To**, click **Add phone number** and add your personal mobile number
3. Click **Send message** — Meta sends a test message to your personal WhatsApp
4. Open your RDL WhatsApp Inbox — the conversation should appear

### Test 2 — Test the full AI flow

From your personal WhatsApp, send a message to the business number:
```
"Hi, I need pricing for a data logger, quantity 10"
```

Within a few seconds you should see:
- The message appear in your RDL WhatsApp Inbox
- A lead auto-created in Lead Management
- AI classifies it as "Sales"
- AI detects the product from your knowledge base
- AI generates a draft reply with pricing

If **auto_send is ON** → the reply is sent automatically to your WhatsApp.
If **auto_send is OFF** → the draft appears in the inbox for you to review and approve.

### Test 3 — Test Draft Approval

1. Turn off auto_send on your account (edit account → uncheck Enable Auto-Send)
2. Send another test inquiry from your personal WhatsApp
3. In the RDL inbox, you'll see the AI draft in amber
4. Edit it if needed → click **Send via WhatsApp**
5. Check your personal WhatsApp — the message arrives

---

## Understanding Auto Mode vs Draft Mode

| | Auto Mode | Draft Mode |
|-|-----------|------------|
| **What happens** | AI sends reply immediately | AI writes reply, you approve it |
| **When to use** | High-volume simple inquiries | New product, sensitive customers, complex replies |
| **How to enable** | Check "Enable Auto-Send" on account | Uncheck "Enable Auto-Send" on account |
| **Override** | If AI finds knowledge gaps, it holds for review even in auto mode | Always holds |

### When does Auto Mode hold a draft anyway?
Even with auto_send ON, the AI will hold a draft for review if:
- It couldn't answer one or more of the customer's questions (knowledge gap)
- The message is a Support or Grievance complaint (always needs human)
- The AI was unavailable (LLM quota exceeded)

### Knowledge Gaps
If a customer asks something your knowledge base doesn't have (e.g. "what's the warranty?"):
1. AI drafts the reply but marks it as "has gaps"
2. You see the unanswered question highlighted in red in the inbox
3. You fill in the answer → it gets saved to your knowledge base permanently
4. AI regenerates the reply with the new knowledge
5. You approve and send

This means your AI gets smarter with every conversation.

---

## Pricing & Free Tier Explained

### What is a "conversation"?
A conversation is a **24-hour window** between you and one customer. All messages exchanged within that window count as 1 conversation — whether it's 2 messages or 20.

### Monthly costs (India pricing, June 2026)

| Type | When | Cost per conversation |
|------|------|----------------------|
| **Service** (customer messages you first) | Customer inquiries, IndiaMart leads | **FREE up to 1,000/month** |
| **Utility** (you message customer about an order) | Order updates, shipping notifications | ~₹0.40 |
| **Marketing** (you message cold leads) | Promotional outreach | ~₹1.20 |
| **Authentication** (OTP) | Login OTPs | ~₹0.30 |

### For your use case
Since customers message you first (from IndiaMart, TradeIndia, etc.) → **Service conversations = Free**.

**Example monthly bill at different volumes:**
- 200 inquiries/month → **₹0** (within free 1,000)
- 800 inquiries/month → **₹0** (within free 1,000)
- 1,500 inquiries/month → 500 paid × ₹0.40 = **~₹200/month**
- 5,000 inquiries/month → 4,000 paid × ₹0.40 = **~₹1,600/month**

### Do you need to add a credit card?
- **For testing (5 verified numbers):** No card needed
- **For real customers:** Yes, add a card in Meta Business Manager → Billing. Meta gives you a free $5 credit when you first add a payment method.

---

## Common Errors & Fixes

### "Webhook verification failed"
**Cause:** Meta called your webhook but got no response or wrong response.
**Fix:**
- Make sure your backend docker container is running: `docker compose ps`
- Make sure the URL is correct and HTTPS is working
- The verify token in Meta must exactly match what you entered in the RDL app

### "Message not delivered" / no message in inbox
**Cause:** Webhook is not subscribed to "messages" events.
**Fix:**
- Meta → WhatsApp → Configuration → Webhook fields → subscribe to "messages"

### "Message sending failed: (#131030)"
**Cause:** The recipient number is not in your test whitelist (when using the free test number).
**Fix:**
- Add the recipient's number: Meta → API Setup → To → Add phone number
- Or: Switch to your verified real business number

### "Invalid OAuth access token"
**Cause:** Using a temporary token that expired (24h tokens expire).
**Fix:**
- Generate a new permanent System User token (Step 5 above)
- Update the access token in your RDL WhatsApp account settings

### "Business verification required"
**Cause:** Meta requires business verification to remove the 5-number limit.
**Fix:**
- Go to [business.facebook.com](https://business.facebook.com) → Settings → Business Info → Start Verification
- Upload: GST certificate, or bank statement, or business registration document
- Takes 1-3 business days

---

## Going Live Checklist

Before going live with real customers, verify each item:

- [ ] Meta app is in **Live mode** (toggle at top of app dashboard — switch from Development to Live)
  - Why? In Development mode, only people with developer roles can interact with your bot
- [ ] Business verification is **approved** in Meta Business Manager
- [ ] Your real business phone number is **verified** and set as the active number
- [ ] Permanent System User token is **saved** in RDL dashboard (not the temporary one)
- [ ] Webhook shows **green checkmark** and is subscribed to "messages"
- [ ] Payment method added in Meta Business Manager → Billing
- [ ] Tested full flow: incoming message → AI reply → appears on customer WhatsApp
- [ ] Decided on Auto Mode vs Draft Mode per your team's preference
- [ ] Your team knows how to use the RDL WhatsApp Inbox (approve drafts, fill knowledge gaps)

---

## Quick Reference — Credentials You Need

| Credential | Where to Find | Example Format |
|-----------|--------------|---------------|
| Phone Number ID | WhatsApp → API Setup → Phone Number ID | `987654321098765` |
| WABA ID | WhatsApp → API Setup → WhatsApp Business Account | `123456789012345` |
| Access Token | Business.facebook.com → System Users → Generate Token | `EAAxxxxxxxxxxxxx...` |
| Verify Token | You create this yourself | Any secret string, e.g. `rdl_wa_2026` |

---

*Document prepared for RDL Technologies — WhatsApp Business Cloud API (Meta) v21.0*
