from livekit.agents import Agent
from livekit.agents import llm

class Assistant(Agent):
    def __init__(self, rag_manager, config):
        self.rag_manager = rag_manager
        instructions = config.get("agent.instructions")
        super().__init__(instructions=instructions)

    @llm.tool()
    async def query_rag_database(self, question: str) -> str:
        """Query the RDL knowledge base for information about products, services, or company details.
        
        Args:
            question: The specific question about RDL Technologies to search for
        """
        return await self.rag_manager.query_rag_database(question)