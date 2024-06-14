# Batch Imports
import asyncio
import random
from typing import Dict, List, Union

import aiohttp
import requests
from openai.types.chat import ChatCompletion, ChatCompletionChunk

from llmstudio.cli import start_server
from llmstudio.config import ENGINE_HOST, ENGINE_PORT


class LLM:
    def __init__(self, model_id: str, **kwargs):
        start_server()
        self.provider, self.model = model_id.split("/")
        self.session_id = kwargs.get("session_id")
        self.api_key = kwargs.get("api_key")
        self.api_endpoint = kwargs.get("api_endpoint")
        self.api_version = kwargs.get("api_version")
        self.base_url = kwargs.get("base_url")
        self.temperature = kwargs.get("temperature")
        self.top_p = kwargs.get("top_p")
        self.top_k = kwargs.get("top_k")
        self.max_tokens = kwargs.get("max_tokens")
        self.failed_requests = 0
        self.pause = False

    def chat(self, input: str, is_stream: bool = False, **kwargs):
        response = requests.post(
            f"http://{ENGINE_HOST}:{ENGINE_PORT}/api/engine/chat/{self.provider}",
            json={
                "model": self.model,
                "session_id": self.session_id,
                "api_key": self.api_key,
                "api_endpoint": self.api_endpoint,
                "api_version": self.api_version,
                "base_url": self.base_url,
                "chat_input": input,
                "is_stream": is_stream,
                "parameters": {
                    "temperature": self.temperature,
                    "top_p": self.top_p,
                    "top_k": self.top_k,
                    "max_tokens": self.max_tokens,
                },
                **kwargs,
            },
            stream=is_stream,
            headers={"Content-Type": "application/json"},
        )

        response.raise_for_status()

        if is_stream:
            return self.generate_chat(response)
        else:
            return ChatCompletion(**response.json())

    def generate_chat(self, response):
        for chunk in response.iter_content(chunk_size=None):
            if chunk:
                yield ChatCompletionChunk(**chunk.decode("utf-8"))

    async def async_chat(self, input: str, is_stream=False, **kwargs):
        if is_stream:
            return self.async_stream(input)
        else:
            return await self.async_non_stream(input)

    async def chat_coroutine(
        self,
        input: Union[str, List[Dict[str, str]]],
        semaphore: asyncio.Semaphore,
        max_retries: int = 5,
    ):
        async with semaphore:
            for i in range(max_retries):
                try:
                    # If the pause flag is set, wait for a while
                    if self.pause:
                        await asyncio.sleep(60)  # Wait for 60 seconds
                        self.pause = False  # Reset the pause flag
                        self.failed_requests = 0  # Reset the failed requests counter

                    # Proceed with the request
                    response = await self.async_chat(input)
                    return response

                except Exception:
                    self.failed_requests += 1
                    if self.failed_requests >= 5:  # If 5 or more requests have failed
                        self.pause = True  # Set the pause flag
                    if i < max_retries - 1:  # i is zero indexed
                        wait_time = (
                            2**i
                        ) + random.random()  # Exponential backoff with jitter
                        await asyncio.sleep(wait_time)
                    else:
                        return None

    async def batch_chat_coroutine(
        self,
        inputs: List[Union[str, List[Dict[str, str]]]],
        num_coroutines: int = 5,
        max_retries: int = 5,
    ) -> List[str]:
        semaphore = asyncio.Semaphore(num_coroutines)
        responses = await asyncio.gather(
            *[
                self.chat_coroutine(input, semaphore=semaphore, max_retries=max_retries)
                for input in inputs
            ]
        )
        return responses

    def batch_chat(
        self,
        inputs: List[Union[str, List[Dict[str, str]]]],
        num_coroutines: int = 5,
        max_retries: int = 5,
    ) -> List[str]:
        return asyncio.run(
            self.batch_chat_coroutine(inputs, num_coroutines, max_retries)
        )

    async def async_non_stream(self, input: str, **kwargs):
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"http://{ENGINE_HOST}:{ENGINE_PORT}/api/engine/chat/{self.provider}",
                json={
                    "model": self.model,
                    "api_key": self.api_key,
                    "api_secret": self.api_endpoint,
                    "api_region": self.api_version,
                    "chat_input": input,
                    "is_stream": False,
                    **kwargs,
                },
                headers={"Content-Type": "application/json"},
            ) as response:
                response.raise_for_status()

                return ChatCompletion(**await response.json())

    async def async_stream(self, input: str, **kwargs):
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"http://{ENGINE_HOST}:{ENGINE_PORT}/api/engine/chat/{self.provider}",
                json={
                    "model": self.model,
                    "api_key": self.api_key,
                    "api_secret": self.api_endpoint,
                    "api_region": self.api_version,
                    "chat_input": input,
                    "is_stream": True,
                    **kwargs,
                },
                headers={"Content-Type": "application/json"},
            ) as response:
                response.raise_for_status()

                async for chunk in response.content.iter_any():
                    if chunk:
                        yield ChatCompletionChunk(**await chunk.decode("utf-8"))
