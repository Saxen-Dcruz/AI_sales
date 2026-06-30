"""
voice_agent.py — LiveKit AI voice agent entrypoint.

Enhanced features:
- Reads session metadata from room (session_id, lead_id, channel_origin)
- Tracks unanswered questions; publishes count to Redis after each RAG miss
- Auto-escalates when threshold reached
- Pushes transcript to backend via HTTP at call end
"""
import asyncio
import json
import logging
import os

import httpx
import redis

from livekit import agents
from livekit.agents import AgentSession, RoomInputOptions, Agent
from livekit.agents.llm import function_tool
from livekit.plugins import google, noise_cancellation, silero

from app.core.config import settings
from app.agents.tools.rag_chain import RAGManager

logger = logging.getLogger("rdl_app_logger")

rag_manager = None

# Redis client for publishing escalation events
_r = redis.Redis(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    db=0,
    decode_responses=True,
)

_ESCALATION_KEYWORDS = {
    "speak to human", "connect me to someone", "i need a person",
    "talk to a human", "human agent", "real person", "customer support",
    "transfer me", "speak with someone", "connect me to a representative",
}

_NO_ANSWER_MARKERS = {
    "i don't have", "i do not have", "i'm not sure", "i cannot find",
    "not available in", "unable to find", "no information", "i'll need to check",
    "our team will", "will follow up", "cannot answer",
}


class Assistant(Agent):
    def __init__(self, session_id: str | None = None, unanswered_count: int = 0) -> None:
        super().__init__(instructions=settings.AGENT.instructions, tools=[query_rag_database])
        self._session_id      = session_id
        self._unanswered_count = unanswered_count
        self._transcript_parts: list[str] = []
        self._threshold = settings.VOICE_ESCALATION_THRESHOLD

    def record_turn(self, speaker: str, text: str) -> None:
        self._transcript_parts.append(f"{speaker}: {text}")

    def note_unanswered(self) -> None:
        self._unanswered_count += 1
        if self._session_id:
            _r.publish("voice:unanswered", json.dumps({
                "session_id": self._session_id,
                "unanswered_count": self._unanswered_count,
            }))

    def check_escalation_trigger(self, text: str) -> bool:
        lower = text.lower()
        if any(kw in lower for kw in _ESCALATION_KEYWORDS):
            return True
        if self._unanswered_count >= self._threshold:
            return True
        return False

    def get_transcript(self) -> str:
        return "\n".join(self._transcript_parts)


@function_tool
async def query_rag_database(question: str) -> str:
    """Query the RDL knowledge base for information about products, services, or company details.

    Args:
        question: The specific question about RDL Technologies to search for
    """
    global rag_manager
    if rag_manager is None:
        return "RAG system is not available yet."
    return await rag_manager.query_rag_database(question)


async def _push_transcript(session_id: str, transcript: str, unanswered: int) -> None:
    """HTTP call to the backend to finalize the session."""
    base = settings.VOICE_BASE_URL.rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            await client.post(
                f"{base}/api/v1/voice/internal/session-end",
                json={
                    "session_id": session_id,
                    "transcript": transcript,
                    "unanswered_count": unanswered,
                },
                headers={"X-Internal-Key": settings.JWT_SECRET_KEY[:16]},
            )
    except Exception as exc:
        logger.warning(f"[AGENT] Transcript push failed: {exc}")


async def entrypoint(ctx: agents.JobContext):
    global rag_manager

    # Extract metadata injected into the room by voice_room_service.create_room()
    room_metadata: dict = {}
    try:
        if ctx.room.metadata:
            room_metadata = json.loads(ctx.room.metadata)
    except Exception:
        pass

    session_id     = room_metadata.get("session_id")
    lead_id        = room_metadata.get("lead_id")
    channel_origin = room_metadata.get("channel_origin", "direct")

    rag_manager = RAGManager()
    rag_init_task = asyncio.create_task(rag_manager.initialize_rag())

    vad = silero.VAD.load()
    agent_session = AgentSession(
        stt=google.STT(),
        llm=google.LLM(model=settings.AGENT.models.llm.model),
        tts=google.TTS(),
        vad=vad,
    )

    room_input_options = RoomInputOptions()
    if settings.AGENT.voice_processing.noise_cancellation:
        room_input_options.noise_cancellation = noise_cancellation.BVC()

    assistant = Assistant(session_id=session_id)

    await agent_session.start(
        room=ctx.room,
        agent=assistant,
        room_input_options=room_input_options,
    )

    logger.info(f"[AGENT] {settings.AGENT.name} starting — room={ctx.room.name} session={session_id}")

    try:
        await asyncio.wait_for(rag_init_task, timeout=65.0)
    except asyncio.TimeoutError:
        logger.warning("[AGENT] RAG initialization timed out")

    logger.info("[AGENT] Agent fully ready")

    channel_msg = {
        "whatsapp": "I can also follow up with you on WhatsApp after our conversation.",
        "gmail": "I can also follow up by email after our conversation.",
    }.get(channel_origin, "")

    await agent_session.generate_reply(
        instructions=(
            f"Greet the user warmly, introduce yourself as the RDL Technologies AI assistant, "
            f"and let them know you can answer questions about our products and services. "
            f"{channel_msg}"
        )
    )

    # Track conversation turns for transcript
    @agent_session.on("user_speech_committed")
    def on_user_speech(ev):
        text = ev.transcript or ""
        assistant.record_turn("Customer", text)
        # Check explicit human escalation / sales team request
        if assistant.check_escalation_trigger(text):
            _r.publish("voice:escalate_request", json.dumps({
                "session_id": session_id,
                "channel_origin": channel_origin,
                "trigger": "user_requested",
            }))
            # Agent immediately reassures the customer
            asyncio.create_task(
                agent_session.generate_reply(
                    instructions=(
                        "The customer has asked to speak with a human or the sales team. "
                        f"Tell them warmly: 'Of course! I'm sending our sales team's contact "
                        f"number to your "
                        f"{'WhatsApp' if channel_origin == 'whatsapp' else 'email'} right now. "
                        f"They will reach out to you very shortly. Is there anything else I can "
                        f"help you with in the meantime?'"
                    )
                )
            )

    @agent_session.on("agent_speech_committed")
    def on_agent_speech(ev):
        text = ev.transcript or ""
        assistant.record_turn("Agent", text)
        # Detect when agent couldn't answer
        lower = text.lower()
        if any(marker in lower for marker in _NO_ANSWER_MARKERS):
            assistant.note_unanswered()

    # Wait for session to finish
    await agent_session.wait_for_disconnect()

    transcript = assistant.get_transcript()
    if session_id:
        await _push_transcript(session_id, transcript, assistant._unanswered_count)

    logger.info(f"[AGENT] Session ended: room={ctx.room.name} unanswered={assistant._unanswered_count}")


if __name__ == "__main__":
    agents.cli.run_app(agents.WorkerOptions(
        entrypoint_fnc=entrypoint,
        ws_url=settings.LIVEKIT_WS_URL,
        api_key=settings.LIVEKIT_API_KEY,
        api_secret=settings.LIVEKIT_API_SECRET,
    ))
