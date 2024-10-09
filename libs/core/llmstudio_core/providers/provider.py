from abc import ABC, abstractmethod
import time
import uuid
from pathlib import Path
from typing import (
    Any,
    AsyncGenerator,
    Coroutine,
    Dict,
    Generator,
    List,
    Optional,
    Tuple,
    Union,
)

from fastapi import HTTPException
import tiktoken
from llmstudio_core.exceptions import ProviderError
from fastapi.responses import JSONResponse, StreamingResponse
from openai.types.chat import (
    ChatCompletion,
    ChatCompletionMessage,
    ChatCompletionMessageToolCall,
    ChatCompletionChunk
)
from openai.types.chat.chat_completion import Choice
from openai.types.chat.chat_completion_message import FunctionCall
from openai.types.chat.chat_completion_message_tool_call import Function
from pydantic import BaseModel, ValidationError


provider_registry = {}


def provider(cls):
    """Decorator to register a new provider."""
    provider_registry[cls._provider_config_name()] = cls

    return cls


class ChatRequest(BaseModel):
    model: str
    chat_input: Any
    is_stream: Optional[bool] = False
    retries: Optional[int] = 0
    parameters: Optional[dict] = None

class ProviderABC(ABC):
    END_TOKEN = "<END_TOKEN>"

    def __init__(self, 
                config: Any, 
                api_key: Optional[str] = None, 
                api_endpoint: Optional[str] = None,
                api_version: Optional[str] = None, 
                base_url: Optional[str] = None,
                tokenizer: Optional[Any] = None):
        self.config = config
        self.API_KEY = api_key
        self.api_endpoint = api_endpoint
        self.api_version = api_version
        self.base_url = base_url
        
        self.tokenizer = tokenizer if tokenizer else self._get_tokenizer()
        self.count = 0
        
    @abstractmethod
    async def achat(
        self, request: ChatRequest
    ) -> Union[StreamingResponse, JSONResponse]:
        raise NotImplementedError("Providers needs to have achat method implemented.")
    
    @abstractmethod
    def achat(
        self, request: ChatRequest
    ) -> Union[StreamingResponse, JSONResponse]:
        raise NotImplementedError("Providers needs to have chat method implemented.")
    
    @staticmethod
    @abstractmethod
    def _provider_config_name():
        raise NotImplementedError("Providers need to implement the '_provider_config_name' property.")


class BaseProvider(ProviderABC):
    END_TOKEN = "<END_TOKEN>"

    async def achat(
        self, request: ChatRequest
    ):
        """Makes a chat connection with the provider's API"""
        try:
            request = self.validate_request(request)
        except ValidationError as e:
            raise HTTPException(status_code=422, detail=e.errors())

        self.validate_model(request)

        for _ in range(request.retries + 1):
            try:
                start_time = time.time()
                response = await self.agenerate_client(request)

                if request.is_stream:
                    response_handler = self.ahandle_response_stream(request, response, start_time)
                    return response_handler
                else:
                    response_handler = self.ahandle_response(request, response, start_time)
                    return await response_handler.__anext__()
            except HTTPException as e:
                if e.status_code == 429:
                    continue  # Retry on rate limit error
                else:
                    raise e  # Raise other HTTP exceptions
            except Exception as e:
                raise HTTPException(
                    status_code=500, detail=str(e)
                )  # Raise other exceptions as HTTP 500
        raise HTTPException(status_code=429, detail="Too many requests")

    def chat(
        self, request: ChatRequest
    ):
        """Makes a chat connection with the provider's API"""
        try:
            request = self.validate_request(request)
        except ValidationError as e:
            raise HTTPException(status_code=422, detail=e.errors())

        self.validate_model(request)

        for _ in range(request.retries + 1):
            try:
                start_time = time.time()
                response = self.generate_client(request)

                if request.is_stream:
                    response_handler = self.handle_response_stream(request, response, start_time)
                    return response_handler
                else:
                    return self.handle_response(request, response, start_time)

            except HTTPException as e:
                if e.status_code == 429:
                    continue  # Retry on rate limit error
                else:
                    raise e  # Raise other HTTP exceptions
            except Exception as e:
                raise ProviderError(str(e))
        raise HTTPException(status_code=429, detail="Too many requests")

    def validate_request(self, request: ChatRequest):
        pass

    def validate_model(self, request: ChatRequest):
        if request.model not in self.config.models:
            raise HTTPException(
                status_code=400,
                detail=f"Model {request.model} is not supported by {self.config.name}",
            )

    async def agenerate_client(
        self, request: ChatRequest
    ) -> Coroutine[Any, Any, Generator]:
        """Generate the provider's client"""

    def handle_response(
        self, request: ChatRequest, response: ChatCompletion, start_time: float
    ) -> ChatCompletion:
        """Handles the response from an API"""
        model = response.model
        
        metrics = self.calculate_metrics(
            usage=response.usage.model_dump(),
            model=request.model,
            start_time=start_time,
            end_time=time.time(),
        )

        response = {
            **response.model_dump(),
            "id": str(uuid.uuid4()),
            "chat_input": (
                request.chat_input
                if isinstance(request.chat_input, str)
                else request.chat_input[-1]["content"]
            ),
            "chat_output": response.choices[0].message.content,
            "context": (
                [{"role": "user", "content": request.chat_input}]
                if isinstance(request.chat_input, str)
                else request.chat_input
            ),
            "provider": self.config.id,
            "model": (
                request.model
                if model and model.startswith(request.model)
                else (model or request.model)
            ),
            "deployment": (
                model
                if model and model.startswith(request.model)
                else (request.model if model != request.model else None)
            ),
            "timestamp": time.time(),
            "parameters": request.parameters,
            "metrics": metrics,
        }

        return ChatCompletion(**response)

    def handle_response_stream(
        self, request: ChatRequest, response: AsyncGenerator, start_time: float
    ) -> Generator:
        """Handles the response from an API"""
        first_token_time = None
        previous_token_time = None
        token_times = []
        token_count = 0
        chunks = []

        for chunk in self.parse_response(response, request=request):
            token_count += 1
            current_time = time.time()
            first_token_time = first_token_time or current_time
            if previous_token_time is not None:
                token_times.append(current_time - previous_token_time)
            previous_token_time = current_time

            chunks.append(chunk)
            chunk = chunk[0] if isinstance(chunk, tuple) else chunk
            if chunk.get("choices")[0].get("finish_reason") != "stop":
                model = chunk.get("model")
                response = {
                            **chunk,
                            "id": str(uuid.uuid4()),
                            "chat_input": (
                                request.chat_input
                                if isinstance(request.chat_input, str)
                                else request.chat_input[-1]["content"]
                            ),
                            "chat_output": chunk.get("choices")[0].get("delta").get("content"),
                            "context": (
                                [{"role": "user", "content": request.chat_input}]
                                if isinstance(request.chat_input, str)
                                else request.chat_input
                            ),
                            "provider": self.config.id,
                            "model": (
                                request.model
                                if model and model.startswith(request.model)
                                else (model or request.model)
                            ),
                            "deployment": (
                                model
                                if model and model.startswith(request.model)
                                else (request.model if model != request.model else None)
                            ),
                            "timestamp": time.time(),
                            "parameters": request.parameters,
                            "metrics": None,
                        }
                yield ChatCompletionChunk(**response)

        chunks = [chunk[0] if isinstance(chunk, tuple) else chunk for chunk in chunks]
        model = next(chunk["model"] for chunk in chunks if chunk.get("model"))

        response, _ = self.join_chunks(chunks, request)

        metrics = self.calculate_metrics_stream(
            request.chat_input,
            response,
            request.model,
            start_time,
            time.time(),
            first_token_time,
            token_times,
            token_count,
        )

        response = {
            **chunk,
            "id": str(uuid.uuid4()),
            "chat_input": (
                request.chat_input
                if isinstance(request.chat_input, str)
                else request.chat_input[-1]["content"]
            ),
            "chat_output": None,
            "context": (
                [{"role": "user", "content": request.chat_input}]
                if isinstance(request.chat_input, str)
                else request.chat_input
            ),
            "provider": self.config.id,
            "model": (
                request.model
                if model and model.startswith(request.model)
                else (model or request.model)
            ),
            "deployment": (
                model
                if model and model.startswith(request.model)
                else (request.model if model != request.model else None)
            ),
            "timestamp": time.time(),
            "parameters": request.parameters,
            "metrics": metrics,
        }

        yield ChatCompletionChunk(**response)

    async def ahandle_response(
        self, request: ChatRequest, response: ChatCompletion, start_time: float
    ) -> AsyncGenerator[ChatCompletion, None]:
        """Handles the response from an API"""
        model = response.model
        
        metrics = self.calculate_metrics(
            usage=response.usage.model_dump(),
            model=request.model,
            start_time=start_time,
            end_time=time.time(),
        )

        response = {
            **response.model_dump(),
            "id": str(uuid.uuid4()),
            "chat_input": (
                request.chat_input
                if isinstance(request.chat_input, str)
                else request.chat_input[-1]["content"]
            ),
            "chat_output": response.choices[0].message.content,
            "context": (
                [{"role": "user", "content": request.chat_input}]
                if isinstance(request.chat_input, str)
                else request.chat_input
            ),
            "provider": self.config.id,
            "model": (
                request.model
                if model and model.startswith(request.model)
                else (model or request.model)
            ),
            "deployment": (
                model
                if model and model.startswith(request.model)
                else (request.model if model != request.model else None)
            ),
            "timestamp": time.time(),
            "parameters": request.parameters,
            "metrics": metrics,
        }

        yield ChatCompletion(**response)

    async def ahandle_response_stream(
        self, request: ChatRequest, response: AsyncGenerator, start_time: float
    ) -> AsyncGenerator[str, None]:
        """Handles the response from an API"""
        first_token_time = None
        previous_token_time = None
        token_times = []
        token_count = 0
        chunks = []

        async for chunk in self.aparse_response(response, request=request):
            token_count += 1
            current_time = time.time()
            first_token_time = first_token_time or current_time
            if previous_token_time is not None:
                token_times.append(current_time - previous_token_time)
            previous_token_time = current_time

            chunks.append(chunk)
            chunk = chunk[0] if isinstance(chunk, tuple) else chunk
            if chunk.get("choices")[0].get("finish_reason") != "stop":
                model = chunk.get("model")
                response = {
                            **chunk,
                            "id": str(uuid.uuid4()),
                            "chat_input": (
                                request.chat_input
                                if isinstance(request.chat_input, str)
                                else request.chat_input[-1]["content"]
                            ),
                            "chat_output": chunk.get("choices")[0].get("delta").get("content"),
                            "context": (
                                [{"role": "user", "content": request.chat_input}]
                                if isinstance(request.chat_input, str)
                                else request.chat_input
                            ),
                            "provider": self.config.id,
                            "model": (
                                request.model
                                if model and model.startswith(request.model)
                                else (model or request.model)
                            ),
                            "deployment": (
                                model
                                if model and model.startswith(request.model)
                                else (request.model if model != request.model else None)
                            ),
                            "timestamp": time.time(),
                            "parameters": request.parameters,
                            "metrics": None,
                        }
                yield ChatCompletionChunk(**response)

        chunks = [chunk[0] if isinstance(chunk, tuple) else chunk for chunk in chunks]
        model = next(chunk["model"] for chunk in chunks if chunk.get("model"))

        response, _ = self.join_chunks(chunks, request)

        metrics = self.calculate_metrics_stream(
            request.chat_input,
            response,
            request.model,
            start_time,
            time.time(),
            first_token_time,
            token_times,
            token_count,
        )

        response = {
            **chunk,
            "id": str(uuid.uuid4()),
            "chat_input": (
                request.chat_input
                if isinstance(request.chat_input, str)
                else request.chat_input[-1]["content"]
            ),
            "chat_output": None,
            "context": (
                [{"role": "user", "content": request.chat_input}]
                if isinstance(request.chat_input, str)
                else request.chat_input
            ),
            "provider": self.config.id,
            "model": (
                request.model
                if model and model.startswith(request.model)
                else (model or request.model)
            ),
            "deployment": (
                model
                if model and model.startswith(request.model)
                else (request.model if model != request.model else None)
            ),
            "timestamp": time.time(),
            "parameters": request.parameters,
            "metrics": metrics,
        }

        yield ChatCompletionChunk(**response)

    def join_chunks(self, chunks, request):

        finish_reason = chunks[-1].get("choices")[0].get("finish_reason")
        if finish_reason == "tool_calls":
            tool_calls = [
                chunk.get("choices")[0].get("delta").get("tool_calls")[0]
                for chunk in chunks[1:-1]
            ]

            tool_call_id = tool_calls[0].get("id")
            tool_call_name = tool_calls[0].get("function").get("name")
            tool_call_type = tool_calls[0].get("function").get("type")
            tool_call_arguments = "".join(
                chunk.get("function", {}).get("arguments", "")
                for chunk in tool_calls[1:]
            )

            try:
                return (
                    ChatCompletion(
                        id=chunks[-1].get("id"),
                        created=chunks[-1].get("created"),
                        model=chunks[-1].get("model"),
                        object="chat.completion",
                        choices=[
                            Choice(
                                finish_reason="tool_calls",
                                index=0,
                                logprobs=None,
                                message=ChatCompletionMessage(
                                    content=None,
                                    role="assistant",
                                    function_call=None,
                                    tool_calls=[
                                        ChatCompletionMessageToolCall(
                                            id=tool_call_id,
                                            function=Function(
                                                arguments=tool_call_arguments,
                                                name=tool_call_name,
                                            ),
                                            type=tool_call_type,
                                        )
                                    ],
                                ),
                            )
                        ],
                    ),
                    tool_call_arguments,
                )
            except Exception as e:
                raise e
        elif finish_reason == "function_call":
            function_calls = [
                chunk.get("choices")[0].get("delta").get("function_call")
                for chunk in chunks[1:-1]
                if chunk.get("choices")
                and chunk.get("choices")[0].get("delta")
                and chunk.get("choices")[0].get("delta").get("function_call")
            ]

            function_call_name = function_calls[0].get("name")
            
            function_call_arguments = ""
            for chunk in function_calls:
                function_call_arguments += chunk.get("arguments")

            return (
                ChatCompletion(
                    id=chunks[-1].get("id"),
                    created=chunks[-1].get("created"),
                    model=chunks[-1].get("model"),
                    object="chat.completion",
                    choices=[
                        Choice(
                            finish_reason="function_call",
                            index=0,
                            logprobs=None,
                            message=ChatCompletionMessage(
                                content=None,
                                role="assistant",
                                tool_calls=None,
                                function_call=FunctionCall(
                                    arguments=function_call_arguments,
                                    name=function_call_name,
                                ),
                            ),
                        )
                    ],
                ),
                function_call_arguments,
            )

        elif finish_reason == "stop" or finish_reason == "length":
            if self.__class__.__name__ in ("OpenAIProvider", "AzureProvider"):
                start_index = 1
            else:
                start_index = 0

            stop_content = "".join(
                filter(
                    None,
                    [
                        chunk.get("choices")[0].get("delta").get("content")
                        for chunk in chunks[start_index:]
                    ],
                )
            )

            return (
                ChatCompletion(
                    id=chunks[-1].get("id"),
                    created=chunks[-1].get("created"),
                    model=chunks[-1].get("model"),
                    object="chat.completion",
                    choices=[
                        Choice(
                            finish_reason="stop",
                            index=0,
                            logprobs=None,
                            message=ChatCompletionMessage(
                                content=stop_content,
                                role="assistant",
                                function_call=None,
                                tool_calls=None,
                            ),
                        )
                    ],
                ),
                stop_content,
            )

    async def aparse_response(
        self, response: AsyncGenerator
    ) -> AsyncGenerator[str, ChatCompletionChunk]:
        pass

    def parse_response(
        self, response: AsyncGenerator
    ) -> ChatCompletionChunk:
        pass

    def calculate_metrics_stream(
        self,
        input: Any,
        output: Any,
        model: str,
        start_time: float,
        end_time: float,
        first_token_time: float,
        token_times: Tuple[float, ...],
        token_count: int,
    ) -> Dict[str, Any]:
        """Calculates metrics based on token times and output"""
        model_config = self.config.models[model]
        input_tokens = len(self.tokenizer.encode(self.input_to_string(input)))
        output_tokens = len(self.tokenizer.encode(self.output_to_string(output)))

        input_cost = self.calculate_cost(input_tokens, model_config.input_token_cost)
        output_cost = self.calculate_cost(output_tokens, model_config.output_token_cost)

        total_time = end_time - start_time
        return {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "cost_usd": input_cost + output_cost,
            "latency_s": total_time,
            "time_to_first_token_s": first_token_time - start_time,
            "inter_token_latency_s": sum(token_times) / len(token_times),
            "tokens_per_second": token_count / total_time,
        }
    
    def calculate_metrics(
        self,
        usage,
        model: str,
        start_time: float,
        end_time: float,
    ) -> Dict[str, Any]:
        """Calculates metrics based on token times and output"""
        model_config = self.config.models[model]
        input_tokens = usage.get("prompt_tokens")
        output_tokens = usage.get("completion_tokens")

        input_cost = self.calculate_cost(input_tokens, model_config.input_token_cost)
        output_cost = self.calculate_cost(output_tokens, model_config.output_token_cost)

        total_time = end_time - start_time
        return {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "cost_usd": input_cost + output_cost,
            "latency_s": total_time,
            "time_to_first_token_s": None,
            "inter_token_latency_s": None,
            "tokens_per_second": usage.get("total_tokens") / total_time,
        }

    def calculate_cost(
        self, token_count: int, token_cost: Union[float, List[Dict[str, Any]]]
    ) -> float:
        if isinstance(token_cost, list):
            for cost_range in token_cost:
                if token_count >= cost_range.range[0] and (
                    token_count <= cost_range.range[1] or cost_range.range[1] is None
                ):
                    return cost_range.cost * token_count
        else:
            return token_cost * token_count
        return 0

    def input_to_string(self, input):
        if isinstance(input, str):
            return input
        else:
            result = []
            for message in input:
                if message.get("content") is not None:
                    if isinstance(message["content"], str):
                        result.append(message["content"])
                    elif (
                        isinstance(message["content"], list)
                        and message.get("role") == "user"
                    ):
                        for item in message["content"]:
                            if item.get("type") == "text":
                                result.append(item.get("text", ""))
                            elif item.get("type") == "image_url":
                                url = item.get("image_url", {}).get("url", "")
                                result.append(url)
            return "".join(result)

    def output_to_string(self, output):
        if output.choices[0].finish_reason == "stop":
            return output.choices[0].message.content
        elif output.choices[0].finish_reason == "tool_calls":
            return output.choices[0].message.tool_calls[0].function.arguments
        elif output.choices[0].finish_reason == "function_call":
            return output.choices[0].message.function_call.arguments

    def get_end_token_string(self, metrics: Dict[str, Any]) -> str:
        return f"{self.END_TOKEN},input_tokens={metrics['input_tokens']},output_tokens={metrics['output_tokens']},cost_usd={metrics['cost_usd']},latency_s={metrics['latency_s']:.5f},time_to_first_token_s={metrics['time_to_first_token_s']:.5f},inter_token_latency_s={metrics['inter_token_latency_s']:.5f},tokens_per_second={metrics['tokens_per_second']:.2f}"

    def _get_tokenizer(self):
        return {}.get(self.config.id, tiktoken.get_encoding("cl100k_base"))
