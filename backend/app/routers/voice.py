"""
voice.py — Voice Bridge API router.

Endpoints:
  POST /voice/rooms                      Create room; returns join URL + office phone
  GET  /voice/rooms/{room}               Session status
  GET  /voice/rooms/{room}/token         Fresh participant token
  POST /voice/rooms/{room}/webhook       LiveKit server events (HMAC-verified)
  POST /voice/rooms/{room}/escalate      Manual escalation trigger
  GET  /voice/call/{room}?token=xxx      Browser call page (inline HTML, no React needed)
  GET  /voice/review/{session_id}        Feedback form page (signed URL)
  POST /voice/review/{session_id}        Submit feedback (form POST)
  GET  /voice/feedback/quick             GET with ?session_id=&sig=&rating= (one-click rating)
  GET  /voice/analytics                  Full analytics
  POST /voice/internal/session-end       Called by AI agent at call end (internal key)
"""

import json
import logging
import threading
from datetime import datetime

from app.models.call import Call, CallDirection, CallStatus
from app.services.call_service import process_transcript
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_db
from app.core.config import settings
from app.models.user import User
from app.models.voice_session import VoiceSession, VoiceSessionStatus
from app.schema.voice import (
    CreateVoiceRoomRequest, CreateVoiceRoomResponse, EscalationResponse,
    EscalateRequest, FeedbackOut, FreshTokenResponse,
    SubmitFeedbackRequest, VoiceAnalyticsResponse, VoiceSessionOut,
)
from app.services import voice_room_service as vrs
from app.services import voice_feedback_service as vfs
from app.services import escalation_service as esc

router = APIRouter(prefix="/voice", tags=["Voice Bridge"])
logger = logging.getLogger("rdl_app_logger")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _session_to_out(session: VoiceSession) -> VoiceSessionOut:
    _, join_url = _refresh_join_url(session)
    return VoiceSessionOut(
        id                = session.id,
        room_name         = session.room_name,
        channel_origin    = session.channel_origin,
        channel_ref_id    = session.channel_ref_id,
        lead_id           = session.lead_id,
        status            = session.status,
        join_url          = join_url,
        token_expires_at  = session.token_expires_at,
        joined_at         = session.joined_at,
        ended_at          = session.ended_at,
        duration_seconds  = session.duration_seconds,
        unanswered_count  = session.unanswered_count,
        escalation_type   = session.escalation_type,
        escalation_ref    = session.escalation_ref,
        feedback_sent     = session.feedback_sent,
        created_at        = session.created_at,
    )


def _refresh_join_url(session: VoiceSession) -> tuple[str, str]:
    token    = session.participant_token
    base     = settings.VOICE_BASE_URL.rstrip("/")
    join_url = f"{base}/api/v1/voice/call/{session.room_name}?token={token}"
    return token, join_url


# ── Room endpoints ────────────────────────────────────────────────────────────

@router.post("/rooms", response_model=CreateVoiceRoomResponse, status_code=201)
def create_room(
    payload: CreateVoiceRoomRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a LiveKit room and return the browser join URL + office phone (Option 2)."""
    try:
        session, join_url = vrs.create_room(
            db,
            channel_origin = payload.channel_origin,
            owner_id       = current_user.id,
            lead_id        = payload.lead_id,
            channel_ref_id = payload.channel_ref_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=429, detail=str(exc))

    return CreateVoiceRoomResponse(
        session     = _session_to_out(session),
        join_url    = join_url,
        office_phone = settings.COMPANY_PHONE,
        message     = "Room ready. Send join_url to customer.",
    )


@router.get("/rooms/{room_name}", response_model=VoiceSessionOut)
def get_room_status(
    room_name: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    session = db.query(VoiceSession).filter(VoiceSession.room_name == room_name).first()
    if not session:
        raise HTTPException(status_code=404, detail="Voice session not found")
    return _session_to_out(session)


@router.get("/rooms/{room_name}/token", response_model=FreshTokenResponse)
def get_fresh_token(
    room_name: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Generate a fresh 15-min participant token for an existing session."""
    session = db.query(VoiceSession).filter(VoiceSession.room_name == room_name).first()
    if not session:
        raise HTTPException(status_code=404, detail="Voice session not found")
    if session.status not in (VoiceSessionStatus.PENDING, VoiceSessionStatus.ACTIVE):
        raise HTTPException(status_code=400, detail="Session is no longer active")

    token, expires_at = vrs.refresh_participant_token(session)
    session.participant_token = token
    session.token_expires_at  = expires_at
    db.commit()

    return FreshTokenResponse(room_name=room_name, token=token, expires_at=expires_at)


@router.post("/rooms/{room_name}/escalate", response_model=EscalationResponse)
def escalate_session(
    room_name: str,
    payload: EscalateRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Manually trigger escalation to GMeet or office call."""
    session = db.query(VoiceSession).filter(VoiceSession.room_name == room_name).first()
    if not session:
        raise HTTPException(status_code=404, detail="Voice session not found")

    ref = esc.offer_escalation_options(db, session, escalation_type=payload.escalation_type)
    return EscalationResponse(
        escalation_type = session.escalation_type,
        escalation_ref  = ref,
        message         = "Escalation sent via customer's original channel",
    )


# ── LiveKit webhook ───────────────────────────────────────────────────────────

@router.post("/rooms/{room_name}/webhook", status_code=200)
async def livekit_webhook(
    room_name: str,
    request: Request,
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(None),
):
    """
    Receives LiveKit server-side events.
    Verified via JWT signed with LIVEKIT_API_SECRET.
    Events handled: participant_joined, room_finished.
    """
    body = await request.body()

    if not vrs.verify_livekit_webhook_signature(body, authorization or ""):
        raise HTTPException(status_code=401, detail="Invalid LiveKit webhook signature")

    try:
        event = json.loads(body)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    event_type = event.get("event", "")

    if event_type == "participant_joined":
        # First real participant (not the agent) means customer joined
        participant = event.get("participant", {})
        if not participant.get("identity", "").startswith("rdl-ai-agent"):
            vrs.mark_session_active(db, room_name)
            logger.info(f"[VOICE WEBHOOK] participant_joined: {room_name}")

    elif event_type == "room_finished":
        session = db.query(VoiceSession).filter(VoiceSession.room_name == room_name).first()
        if session:
            duration = event.get("room", {}).get("duration", None)
            vrs.complete_session(
                db,
                room_name,
                duration_seconds = int(duration) if duration else None,
            )
            # Schedule feedback dispatch (non-blocking)
            def _send_fb():
                from app.database.core import SessionLocal
                with SessionLocal() as fb_db:
                    s = fb_db.query(VoiceSession).filter(VoiceSession.id == session.id).first()
                    if s:
                        vfs.send_feedback_request(fb_db, s)
            t = threading.Timer(300, _send_fb)  # 5 min delay
            t.daemon = True
            t.start()
            logger.info(f"[VOICE WEBHOOK] room_finished: {room_name}")

    return {"ok": True}


# ── Internal agent→backend endpoint ──────────────────────────────────────────

@router.post("/internal/session-end", include_in_schema=False)
async def internal_session_end(
    request: Request,
    db: Session = Depends(get_db),
    x_internal_key: Optional[str] = Header(None, alias="X-Internal-Key"),
):
    """
    Called by the AI agent process at call end to push transcript + unanswered count.

    Full pipeline (same as regular phone calls):
    1. Save transcript + unanswered_count to voice_sessions
    2. Create a Call record (always — gaps or not)
    3. Run process_transcript() → structured extraction (intent/urgency/product_interest/
       ai_summary/sentiment), knowledge gap extraction, lead score update,
       post-call email + WhatsApp follow-up
    4. Link Call.voice_session_id so analytics can join back
    """
    expected_key = settings.JWT_SECRET_KEY[:16]
    if x_internal_key != expected_key:
        raise HTTPException(status_code=401, detail="Invalid internal key")

    body = await request.json()
    session_id = body.get("session_id")
    transcript = body.get("transcript", "")
    unanswered = int(body.get("unanswered_count", 0))

    session = db.query(VoiceSession).filter(VoiceSession.id == session_id).first()
    if not session:
        return {"ok": False, "reason": "session not found"}

    # 1. Persist to voice_sessions
    session.transcript       = transcript
    session.unanswered_count = unanswered
    if session.status == VoiceSessionStatus.ACTIVE:
        session.status   = VoiceSessionStatus.COMPLETED
        session.ended_at = datetime.utcnow()

    # Auto-escalate if still active and threshold reached
    if session.status == VoiceSessionStatus.ACTIVE:
        esc.check_and_auto_escalate(db, session)

    db.flush()

    # 2 + 3. Create a Call record and run the full post-call pipeline
    if transcript.strip():
        try:
            # Build a Call row linked to this voice session
            call = Call(
                owner_id         = session.owner_id,
                lead_id          = session.lead_id,
                direction        = CallDirection.INBOUND,
                status           = CallStatus.COMPLETED,
                livekit_room     = session.room_name,
                voice_session_id = session.id,
                # Origin tag so call analytics can filter voice calls
                notes            = f"[voice-bridge] channel={session.channel_origin}",
            )
            db.add(call)
            db.flush()  # get call.id before process_transcript uses it

            # process_transcript does: structured extraction (intent/urgency/product_interest),
            # ai_summary, sentiment, gap extraction, lead score update,
            # post-call email, post-call WhatsApp
            process_transcript(db, call, transcript)
            logger.info(
                f"[VOICE] process_transcript complete: session={session_id} "
                f"call={call.id} intent={call.intent} gaps={len(call.followup_gaps or [])}"
            )
        except Exception as exc:
            logger.warning(f"[VOICE] process_transcript failed: {exc}")

    db.commit()
    logger.info(f"[VOICE] Session-end committed: session={session_id} unanswered={unanswered}")
    return {"ok": True}


# ── Browser call page ─────────────────────────────────────────────────────────

_CALL_PAGE_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <title>RDL AI Voice Assistant</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      background: linear-gradient(135deg, #0f172a 0%, #1e3a5f 100%);
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      color: #fff;
    }}
    .card {{
      background: rgba(255,255,255,0.08);
      backdrop-filter: blur(16px);
      border: 1px solid rgba(255,255,255,0.15);
      border-radius: 20px;
      padding: 48px 40px;
      max-width: 440px;
      width: 100%;
      text-align: center;
      box-shadow: 0 20px 60px rgba(0,0,0,0.4);
    }}
    .logo {{ font-size: 2.2rem; font-weight: 800; letter-spacing: -1px; margin-bottom: 4px; }}
    .logo span {{ color: #38bdf8; }}
    .subtitle {{ color: #94a3b8; font-size: 0.9rem; margin-bottom: 36px; }}
    .avatar {{
      width: 96px; height: 96px; border-radius: 50%;
      background: linear-gradient(135deg, #0ea5e9, #6366f1);
      display: flex; align-items: center; justify-content: center;
      margin: 0 auto 24px;
      position: relative;
    }}
    .avatar svg {{ width: 48px; height: 48px; fill: #fff; }}
    .pulse {{
      position: absolute; inset: -6px;
      border-radius: 50%;
      border: 2px solid #38bdf8;
      opacity: 0;
      animation: none;
    }}
    .pulse.active {{ animation: pulse 1.5s ease-out infinite; }}
    @keyframes pulse {{
      0%  {{ transform: scale(1);   opacity: 0.8; }}
      100%{{ transform: scale(1.5); opacity: 0; }}
    }}
    #status {{ font-size: 1.1rem; font-weight: 600; margin-bottom: 8px; }}
    #sub-status {{ color: #94a3b8; font-size: 0.85rem; margin-bottom: 32px; min-height: 20px; }}
    .btn {{
      border: none; border-radius: 12px; cursor: pointer;
      font-size: 1rem; font-weight: 600; padding: 14px 32px;
      transition: all 0.2s; width: 100%; display: block; margin-bottom: 12px;
    }}
    .btn-primary {{
      background: linear-gradient(135deg, #0ea5e9, #6366f1);
      color: #fff;
    }}
    .btn-primary:hover {{ opacity: 0.9; transform: translateY(-1px); }}
    .btn-danger {{
      background: rgba(239,68,68,0.15);
      border: 1px solid rgba(239,68,68,0.4);
      color: #f87171;
    }}
    .btn-danger:hover {{ background: rgba(239,68,68,0.25); }}
    .btn:disabled {{ opacity: 0.4; cursor: not-allowed; transform: none; }}
    .mute-btn {{
      background: rgba(255,255,255,0.08);
      border: 1px solid rgba(255,255,255,0.15);
      color: #e2e8f0;
      font-size: 0.9rem;
      margin-bottom: 12px;
    }}
    .escalation-banner {{
      background: rgba(251,146,60,0.15);
      border: 1px solid rgba(251,146,60,0.4);
      border-radius: 12px;
      padding: 16px;
      margin-top: 16px;
      display: none;
      font-size: 0.85rem;
      color: #fdba74;
    }}
    .escalation-banner a {{ color: #fb923c; text-decoration: underline; }}
    .powered {{ margin-top: 28px; color: #475569; font-size: 0.75rem; }}
  </style>
</head>
<body>
<div class="card">
  <div class="logo">RDL<span>.</span>ai</div>
  <div class="subtitle">Voice AI Assistant — RDL Technologies</div>

  <div class="avatar">
    <div class="pulse" id="pulse"></div>
    <svg viewBox="0 0 24 24"><path d="M12 1a5 5 0 0 1 5 5v5a5 5 0 0 1-10 0V6a5 5 0 0 1 5-5zm0 13a7 7 0 0 0 7-7H5a7 7 0 0 0 7 7zm-1 2v3H8v2h8v-2h-3v-3h-2z"/></svg>
  </div>

  <div id="status">Connecting…</div>
  <div id="sub-status">Please wait while we set up your call</div>

  <button class="btn btn-primary" id="startBtn" onclick="startCall()" disabled>
    🎙️ Connect & Start Talking
  </button>
  <button class="btn mute-btn" id="muteBtn" onclick="toggleMute()" style="display:none">
    🔇 Mute
  </button>
  <button class="btn btn-danger" id="endBtn" onclick="endCall()" style="display:none">
    End Call
  </button>

  <div class="escalation-banner" id="escalationBanner">
    <strong>Having trouble getting an answer?</strong><br>
    Our team is here to help:<br>
    <a href="tel:{COMPANY_PHONE}">{COMPANY_PHONE}</a> &nbsp;|&nbsp;
    <a href="{MEET_URL}" target="_blank">Join Google Meet with expert</a>
  </div>

  <div class="powered">Powered by RDL Technologies AI Platform</div>
</div>

<script src="https://cdn.jsdelivr.net/npm/livekit-client/dist/livekit-client.umd.min.js"></script>
<script>
  const ROOM_NAME   = "{ROOM_NAME}";
  const TOKEN       = "{TOKEN}";
  const WS_URL      = "{WS_URL}";
  const REFRESH_URL = "{REFRESH_URL}";

  let room = null;
  let muted = false;
  let localTrack = null;
  const statusEl  = document.getElementById("status");
  const subEl     = document.getElementById("sub-status");
  const startBtn  = document.getElementById("startBtn");
  const muteBtn   = document.getElementById("muteBtn");
  const endBtn    = document.getElementById("endBtn");
  const pulseEl   = document.getElementById("pulse");
  const escalEl   = document.getElementById("escalationBanner");

  function setStatus(s, sub) {{
    statusEl.textContent = s;
    if (sub !== undefined) subEl.textContent = sub;
  }}

  async function startCall() {{
    startBtn.disabled = true;
    setStatus("Connecting…", "Requesting microphone access…");
    try {{
      room = new LivekitClient.Room({{ adaptiveStream: true, dynacast: true }});

      room.on(LivekitClient.RoomEvent.Connected, () => {{
        setStatus("Connected", "Speak now — the AI is listening");
        pulseEl.classList.add("active");
        muteBtn.style.display = "block";
        endBtn.style.display  = "block";
      }});
      room.on(LivekitClient.RoomEvent.Disconnected, () => {{
        setStatus("Call ended", "Thank you for speaking with us!");
        pulseEl.classList.remove("active");
        muteBtn.style.display = "none";
        endBtn.style.display  = "none";
      }});
      room.on(LivekitClient.RoomEvent.DataReceived, (payload) => {{
        try {{
          const msg = JSON.parse(new TextDecoder().decode(payload));
          if (msg.type === "escalation") {{
            escalEl.style.display = "block";
          }}
        }} catch(e) {{}}
      }});

      await room.connect(WS_URL, TOKEN);
      localTrack = await LivekitClient.createLocalAudioTrack({{ echoCancellation: true, noiseSuppression: true }});
      await room.localParticipant.publishTrack(localTrack);
    }} catch(err) {{
      setStatus("Could not connect", err.message || "Check microphone permissions");
      startBtn.disabled = false;
    }}
  }}

  function toggleMute() {{
    if (!localTrack) return;
    muted = !muted;
    localTrack.mute(muted);
    muteBtn.textContent = muted ? "🎙️ Unmute" : "🔇 Mute";
  }}

  function endCall() {{
    if (room) room.disconnect();
    setStatus("Call ended", "Thank you for speaking with us!");
    pulseEl.classList.remove("active");
    muteBtn.style.display = "none";
    endBtn.style.display  = "none";
  }}

  // Auto-enable the start button after page load
  window.addEventListener("load", () => {{
    setStatus("Ready to connect", "Click below to start your AI voice call");
    startBtn.disabled = false;
  }});
</script>
</body>
</html>
"""


@router.get("/call/{room_name}", response_class=HTMLResponse, include_in_schema=False)
def voice_call_page(
    room_name: str,
    token: str = Query(..., description="Participant JWT issued by create_room"),
    db: Session = Depends(get_db),
):
    """
    Browser call page — served inline without React.
    Customer opens this URL; the LiveKit JS SDK auto-connects their mic.
    """
    session = db.query(VoiceSession).filter(VoiceSession.room_name == room_name).first()
    if not session:
        return HTMLResponse("<h1>Session not found or expired.</h1>", status_code=404)

    if session.status == VoiceSessionStatus.EXPIRED:
        return HTMLResponse("<h1>This call link has expired. Please request a new one.</h1>", status_code=410)

    # Validate token matches what we issued
    if token != session.participant_token:
        return HTMLResponse("<h1>Invalid or expired call token.</h1>", status_code=401)

    meet_url   = session.escalation_ref or ""
    base       = settings.VOICE_BASE_URL.rstrip("/")
    refresh_url = f"{base}/api/v1/voice/rooms/{room_name}/token"

    html = _CALL_PAGE_HTML.format(
        ROOM_NAME   = room_name,
        TOKEN       = token,
        WS_URL      = settings.LIVEKIT_PUBLIC_WS_URL,
        REFRESH_URL = refresh_url,
        COMPANY_PHONE = settings.COMPANY_PHONE,
        MEET_URL    = meet_url or "#",
    )
    return HTMLResponse(html)


# ── Feedback form page ────────────────────────────────────────────────────────

_FEEDBACK_PAGE_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <title>Rate Your Experience — RDL Technologies</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      background: linear-gradient(135deg, #0f172a 0%, #1e3a5f 100%);
      min-height: 100vh; display: flex; align-items: center; justify-content: center;
    }}
    .card {{
      background: rgba(255,255,255,0.08); backdrop-filter: blur(16px);
      border: 1px solid rgba(255,255,255,0.15); border-radius: 20px;
      padding: 48px 40px; max-width: 440px; width: 100%; text-align: center;
      box-shadow: 0 20px 60px rgba(0,0,0,0.4); color: #fff;
    }}
    .logo {{ font-size: 2rem; font-weight: 800; margin-bottom: 4px; }}
    .logo span {{ color: #38bdf8; }}
    h2 {{ font-size: 1.4rem; margin: 24px 0 8px; }}
    p {{ color: #94a3b8; font-size: 0.9rem; margin-bottom: 28px; }}
    .stars {{ display: flex; justify-content: center; gap: 12px; margin-bottom: 28px; }}
    .star {{
      font-size: 2.8rem; cursor: pointer; transition: transform 0.15s;
      filter: grayscale(1); opacity: 0.4;
    }}
    .star:hover, .star.selected {{ filter: none; opacity: 1; transform: scale(1.1); }}
    textarea {{
      width: 100%; background: rgba(255,255,255,0.07); border: 1px solid rgba(255,255,255,0.15);
      border-radius: 10px; color: #e2e8f0; font-size: 0.95rem;
      padding: 12px; resize: vertical; min-height: 80px; font-family: inherit;
      margin-bottom: 20px;
    }}
    textarea::placeholder {{ color: #64748b; }}
    .btn {{
      border: none; border-radius: 12px; cursor: pointer;
      font-size: 1rem; font-weight: 600; padding: 14px 32px;
      width: 100%; background: linear-gradient(135deg, #0ea5e9, #6366f1); color: #fff;
    }}
    .btn:disabled {{ opacity: 0.5; cursor: not-allowed; }}
    .thanks {{ font-size: 1.3rem; font-weight: 700; color: #4ade80; margin: 24px 0 8px; }}
    #form-area, #thanks-area {{ transition: opacity 0.3s; }}
    #thanks-area {{ display: none; }}
    .powered {{ margin-top: 24px; color: #475569; font-size: 0.75rem; }}
  </style>
</head>
<body>
<div class="card">
  <div class="logo">RDL<span>.</span>ai</div>

  <div id="form-area">
    <h2>How was your AI voice call?</h2>
    <p>Your feedback is anonymous — no login needed. Takes 10 seconds.</p>

    <div class="stars" id="stars">
      <span class="star" data-v="1" onclick="selectRating(1)">⭐</span>
      <span class="star" data-v="2" onclick="selectRating(2)">⭐</span>
      <span class="star" data-v="3" onclick="selectRating(3)">⭐</span>
      <span class="star" data-v="4" onclick="selectRating(4)">⭐</span>
      <span class="star" data-v="5" onclick="selectRating(5)">⭐</span>
    </div>

    <textarea id="comment" placeholder="Any comments? (optional)"></textarea>

    <button class="btn" id="submitBtn" onclick="submitFeedback()" disabled>
      Submit Rating
    </button>
  </div>

  <div id="thanks-area">
    <div class="thanks">Thank you! 🎉</div>
    <p>Your feedback helps us make every call better.<br>
    The RDL team will be in touch if you requested a follow-up.</p>
  </div>

  <div class="powered">Powered by RDL Technologies AI Platform</div>
</div>

<script>
  let selectedRating = 0;
  const SESSION_ID = "{SESSION_ID}";
  const SIG        = "{SIG}";

  function selectRating(v) {{
    selectedRating = v;
    document.querySelectorAll(".star").forEach((s, i) => {{
      s.classList.toggle("selected", i < v);
    }});
    document.getElementById("submitBtn").disabled = false;
  }}

  async function submitFeedback() {{
    const btn = document.getElementById("submitBtn");
    btn.disabled = true;
    btn.textContent = "Submitting…";
    const comment = document.getElementById("comment").value.trim();

    try {{
      const res = await fetch(`/api/v1/voice/review/${{SESSION_ID}}?sig=${{SIG}}`, {{
        method: "POST",
        headers: {{ "Content-Type": "application/json" }},
        body: JSON.stringify({{ rating: selectedRating, comment: comment || null }}),
      }});
      if (res.ok) {{
        document.getElementById("form-area").style.display   = "none";
        document.getElementById("thanks-area").style.display = "block";
      }} else {{
        btn.disabled = false;
        btn.textContent = "Submit Rating";
        alert("Something went wrong. Please try again.");
      }}
    }} catch(e) {{
      btn.disabled = false;
      btn.textContent = "Submit Rating";
    }}
  }}
</script>
</body>
</html>
"""


@router.get("/review/{session_id}", response_class=HTMLResponse, include_in_schema=False)
def feedback_form_page(
    session_id: UUID,
    sig: str = Query(...),
    db: Session = Depends(get_db),
):
    """
    Serve the branded feedback form page.
    URL is unique per session, signed with HMAC-SHA256.
    No login needed — the signature is the authorization.
    """
    if not vfs.verify_signature(str(session_id), sig):
        return HTMLResponse("<h1>Invalid or expired feedback link.</h1>", status_code=401)

    session = db.query(VoiceSession).filter(VoiceSession.id == session_id).first()
    if not session:
        return HTMLResponse("<h1>Session not found.</h1>", status_code=404)

    existing = db.query(
        __import__("app.models.voice_session", fromlist=["VoiceCallFeedback"]).VoiceCallFeedback
    ).filter_by(session_id=session_id).first()
    if existing:
        return HTMLResponse(
            "<html><body style='font-family:sans-serif;text-align:center;margin-top:60px'>"
            "<h2>✅ Thank you!</h2><p>Your feedback has already been received.</p></body></html>"
        )

    html = _FEEDBACK_PAGE_HTML.format(SESSION_ID=str(session_id), SIG=sig)
    return HTMLResponse(html)


@router.post("/review/{session_id}", response_model=FeedbackOut)
async def submit_feedback_form(
    session_id: UUID,
    payload: SubmitFeedbackRequest,
    sig: str = Query(...),
    db: Session = Depends(get_db),
):
    """Accept feedback form submission (HMAC-signed URL — no auth token required)."""
    if not vfs.verify_signature(str(session_id), sig):
        raise HTTPException(status_code=401, detail="Invalid or expired feedback link")

    try:
        fb = vfs.submit_feedback(db, session_id, payload.rating, comment=payload.comment, channel_used="web")
        return fb
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("/feedback/quick", include_in_schema=False)
def quick_rating(
    session_id: UUID = Query(...),
    sig: str = Query(...),
    rating: int = Query(..., ge=1, le=5),
    db: Session = Depends(get_db),
):
    """One-click rating via link (no form required — for simple WA/email tap)."""
    if not vfs.verify_signature(str(session_id), sig):
        return HTMLResponse("<h1>Invalid link.</h1>", status_code=401)
    try:
        vfs.submit_feedback(db, session_id, rating, channel_used="link_click")
    except Exception:
        pass
    return HTMLResponse(
        "<html><body style='font-family:sans-serif;text-align:center;margin-top:60px;color:#1e3a5f'>"
        f"<h2>⭐ Thank you for your {rating}/5 rating!</h2>"
        "<p>Your feedback has been recorded.</p>"
        "</body></html>"
    )


# ── Analytics ─────────────────────────────────────────────────────────────────

@router.get("/analytics", response_model=VoiceAnalyticsResponse)
def voice_analytics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    owner_id: Optional[UUID] = Query(None, description="Super-admin only: scope to one user"),
):
    """Full voice call analytics — channel breakdown, escalation rates, feedback scores."""
    if owner_id and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Super-admin only")

    scope = None if current_user.is_superuser and not owner_id else (owner_id or current_user.id)
    data  = vrs.get_voice_analytics(db, owner_id_filter=scope)

    return VoiceAnalyticsResponse(
        total_sessions         = data["total_sessions"],
        active_now             = data["active_now"],
        completed              = data["completed"],
        escalated              = data["escalated"],
        expired                = data["expired"],
        avg_duration_seconds   = data["avg_duration_seconds"],
        avg_unanswered_questions = data["avg_unanswered_questions"],
        escalation_rate        = data["escalation_rate"],
        avg_feedback_score     = data["avg_feedback_score"],
        feedback_response_rate = data["feedback_response_rate"],
        by_channel             = data["by_channel"],
        by_escalation          = data["by_escalation"],
        knowledge_gaps_captured = data["knowledge_gaps_captured"],
    )
