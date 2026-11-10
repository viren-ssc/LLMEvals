import asyncio

from deepeval.models import DeepEvalBaseLLM


class RemoteJudge(DeepEvalBaseLLM):
    def __init__(self, gateway):
        self.gateway = gateway
        super().__init__(model=gateway.model_id)

    def load_model(self):
        return self.gateway

    def get_model_name(self):
        return self.gateway.model_id

    def generate(self, prompt, schema=None):
        return self.gateway.generate(prompt, schema)

    async def a_generate(self, prompt, schema=None):
        return await asyncio.to_thread(self.generate, prompt, schema)
