from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult


class TokenUsageCallback(BaseCallbackHandler):
    """
    Captures token usage from every LLM call within a chain run.
    Works with ChatGoogleGenerativeAI — reads usage_metadata from AIMessage.
    Accumulates across all parallel LLM calls (answer + sentiment).
    """

    def __init__(self):
        self.input_tokens: int = 0
        self.output_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    def on_llm_end(self, response: LLMResult, **_kwargs) -> None:
        for gen_list in response.generations:
            for gen in gen_list:
                if hasattr(gen, "message") and hasattr(gen.message, "usage_metadata"):
                    usage = gen.message.usage_metadata or {}
                    self.input_tokens += usage.get("input_tokens", 0)
                    self.output_tokens += usage.get("output_tokens", 0)
                elif hasattr(gen, "generation_info") and gen.generation_info:
                    usage = gen.generation_info.get("usage_metadata", {})
                    self.input_tokens += usage.get("input_tokens", 0)
                    self.output_tokens += usage.get("output_tokens", 0)
