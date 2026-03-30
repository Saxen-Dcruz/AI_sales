import os
import asyncio
from livekit import agents
from livekit.agents import AgentSession, RoomInputOptions, Agent
from livekit.agents.llm import function_tool
from livekit.plugins import google, noise_cancellation, silero

# Import Pydantic settings instead of config_loader
from app.core.config import settings
from app.agents.tools.rag_chain import RAGManager

# Global RAG manager
rag_manager = None

# Define the tool as a global function (like in your working code)
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

class Assistant(Agent):
    def __init__(self) -> None:
        # Use Pydantic dot-notation!
        super().__init__(
            instructions=settings.AGENT.instructions, 
            tools=[query_rag_database]
        )

async def entrypoint(ctx: agents.JobContext):
    global rag_manager
    
    # Pydantic already validated our keys on startup! 
    # If GOOGLE_API_KEY was missing, the app would have safely crashed immediately.

    # Initialize RAG manager
    rag_manager = RAGManager()
    rag_init_task = asyncio.create_task(rag_manager.initialize_rag())

    # Configure Google Components
    vad = silero.VAD.load() 
    
    session = AgentSession(
        stt=google.STT(),                                       
        llm=google.LLM(model=settings.AGENT.models.llm.model),  # Pulling from config.py
        tts=google.TTS(),                                       
        vad=vad,
    )

    room_input_options = RoomInputOptions()
    if settings.AGENT.voice_processing.noise_cancellation:
        room_input_options.noise_cancellation = noise_cancellation.BVC()

    assistant = Assistant()

    await session.start(
        room=ctx.room,
        agent=assistant,
        room_input_options=room_input_options,
    )

    print(f"\n{settings.AGENT.name} is starting up...")

    # Wait for RAG initialization
    try:
        await asyncio.wait_for(rag_init_task, timeout=65.0)
    except asyncio.TimeoutError:
        print("⚠️ RAG initialization taking longer than expected...")

    print("✅ Agent is fully ready!")

    await session.generate_reply(
        instructions="Greet the user warmly and explain you can answer RDL-specific questions."
    )

if __name__ == "__main__":
    agents.cli.run_app(agents.WorkerOptions(entrypoint_fnc=entrypoint))
