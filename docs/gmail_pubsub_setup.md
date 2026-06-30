# Gmail Push Notifications — Google Cloud Pub/Sub Setup
## RDL Sales Intelligence Platform

Instead of polling Gmail every 120 seconds (~720 API calls/day), the backend receives
real-time push notifications via Google Cloud Pub/Sub. New emails arrive in the inbox
within **2–5 seconds** of the customer sending them.

---

## Prerequisites

- Google Cloud project already exists (the one used for Gmail OAuth: **RDL_AI_Sales**)
- Your server has a public HTTPS URL: `https://118.139.165.99.nip.io:8443`
- Backend is running and reachable at that URL
- `gcloud` CLI installed locally, or use the GCP Console web UI

---

## Step 1 — Create the Pub/Sub Topic

**Cloud Console:**
1. Go to [console.cloud.google.com/cloudpubsub/topics](https://console.cloud.google.com/cloudpubsub/topics)
2. Click **Create Topic**
3. Topic ID: `gmail-push`
4. Leave all defaults, click **Create**

**Your full topic name will be:**
```
projects/YOUR_PROJECT_ID/topics/gmail-push
```

Replace `YOUR_PROJECT_ID` with your actual GCP project ID (visible in the top bar of the Console).

---

## Step 2 — Grant Gmail Permission to Publish

Gmail's push notification service uses a Google-managed service account. You must
explicitly grant it permission to publish to your topic.

**Cloud Console:**
1. On the topic page, click the topic name → **Permissions** tab
2. Click **Add Principal**
3. Principal: `gmail-api-push@system.gserviceaccount.com`
4. Role: **Pub/Sub Publisher**
5. Click **Save**

**This is the most commonly missed step.** Without it, `users.watch()` returns 200
but no notifications are ever delivered.

---

## Step 3 — Create the Push Subscription

A push subscription tells Pub/Sub where to send notifications (your webhook endpoint).

**Cloud Console:**
1. Go to [console.cloud.google.com/cloudpubsub/subscriptions](https://console.cloud.google.com/cloudpubsub/subscriptions)
2. Click **Create Subscription**
3. Subscription ID: `gmail-push-sub`
4. Select topic: the `gmail-push` topic you created above
5. Delivery type: **Push**
6. Endpoint URL: `https://118.139.165.99.nip.io:8443/api/v1/gmail/webhook`
7. **Enable authentication** — click the toggle
   - Service account: create a new one or use an existing one
   - Audience: `https://118.139.165.99.nip.io:8443/api/v1/gmail/webhook`
   - This makes Pub/Sub attach a signed OIDC token to every push, which the backend verifies
8. Acknowledgement deadline: **60 seconds**
9. Message retention: **7 days**
10. Click **Create**

---

## Step 4 — Configure Your Backend

Add these two lines to `backend/.env.prod` (already added as placeholders):

```env
# Replace YOUR_PROJECT_ID with your actual GCP project ID
GMAIL_PUBSUB_TOPIC=projects/YOUR_PROJECT_ID/topics/gmail-push

# Must match the Endpoint URL and Audience you set in Step 3
GMAIL_PUBSUB_AUDIENCE=https://118.139.165.99.nip.io:8443/api/v1/gmail/webhook
```

For local dev (`backend/.env.local`), leave both empty — the backend will work without
push notifications (you can still use `POST /gmail/sync` to process emails manually).

---

## Step 5 — Restart the Backend

```bash
docker compose -f docker-compose.yaml -f docker-compose.prod.yaml restart backend
```

On startup you should see in the logs:
```
[GMAIL WEBHOOK] Pub/Sub mode active — topic=projects/.../topics/gmail-push
[GMAIL WEBHOOK] watch registered: developer20@rdltech.in historyId=... expires=...
[GMAIL WEBHOOK] Registered 1/1 watches
```

---

## Step 6 — Verify It Works

1. Send a test email to `developer20@rdltech.in` from another email account
2. Within 5 seconds, check the backend logs for:
   ```
   [GMAIL WEBHOOK] Notification for developer20@rdltech.in historyId=...
   [GMAIL WEBHOOK] developer20@rdltech.in: 1/1 messages processed
   ```
3. Check the Gmail Inbox in the app — the email should appear immediately

**If the email doesn't appear:**
- Check the Pub/Sub subscription: go to Cloud Console → Pub/Sub → Subscriptions → `gmail-push-sub` → **View messages** — if messages are stuck there, the backend isn't acknowledging
- Check backend logs for errors
- Verify the HTTPS URL is accessible: `curl -k https://118.139.165.99.nip.io:8443/health`

---

## How It Works (Technical)

```
Customer sends email
        ↓
Gmail detects new INBOX message
        ↓
Gmail publishes to Pub/Sub topic: projects/.../topics/gmail-push
  Payload: { emailAddress, historyId }
        ↓
Pub/Sub pushes to POST /api/v1/gmail/webhook (with OIDC JWT)
        ↓
Backend verifies JWT (GMAIL_PUBSUB_AUDIENCE must match)
        ↓
Backend calls Gmail users.history().list(startHistoryId=stored_id)
        ↓
Fetches each new message + runs through LangGraph email workflow
        ↓
Email appears in inbox (Sales/Support/Grievance classified + AI draft)
```

**Watch renewal:** Gmail `users.watch()` tokens expire after 7 days. The backend
automatically renews any watch expiring within 25 hours (checked every 6 hours at startup).

---

## Watch Endpoints Reference

| Event | What happens |
|---|---|
| Backend starts | Registers `users.watch()` for all active Gmail accounts |
| Watch expires (7 days) | Auto-renewed by the renewal loop (every 6 hours check) |
| New Gmail account connected | Watch registered automatically when the OAuth callback completes |
| `POST /gmail/sync` | Manual fallback — still works even with Pub/Sub active |

---

## Troubleshooting

### "historyId too old" error in logs
The stored `historyId` is stale (usually after the DB was wiped). Fix:
```bash
# Clear all watch_history_id so the next notification triggers re-registration
docker compose exec db psql -U admin -d rdl_sales \
  -c "UPDATE email_accounts SET watch_history_id = NULL, watch_expiry = NULL;"
# Then restart backend to re-register watches
docker compose restart backend
```

### Pub/Sub shows messages but backend doesn't receive them
- Your self-signed cert may not be trusted by Google's Pub/Sub push service
- Google requires a valid TLS cert for push endpoints — use Let's Encrypt or
  set up a reverse proxy with a trusted cert in front of `8443`
- Workaround: use `ngrok` or Cloudflare Tunnel for a trusted HTTPS URL during testing

### Watch registration fails with "Topic not found"
- Verify the topic name in `GMAIL_PUBSUB_TOPIC` matches exactly (case-sensitive)
- Verify `gmail-api-push@system.gserviceaccount.com` has Publisher role on the topic (Step 2)

### No notifications arriving
- Verify the push subscription Endpoint URL is exactly `https://118.139.165.99.nip.io:8443/api/v1/gmail/webhook`
- Verify authentication is enabled on the subscription with the correct audience
- Check `GMAIL_PUBSUB_AUDIENCE` in `.env.prod` matches the endpoint URL exactly (no trailing slash)
