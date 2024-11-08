from llmstudio_tracker.tracker import TrackingConfig
from llmstudio.server import start_servers
start_servers()

from llmstudio.providers import LLM
from llmstudio_proxy.provider import ProxyConfig

# from llmstudio_core.providers import LLMCore as LLM
# from llmstudio.providers import LLM

llm = LLM(provider="openai", 
          proxy_config=ProxyConfig(host="0.0.0.0", port="8001"),
          tracking_config=TrackingConfig(host="0.0.0.0", port="8002"),
          session_id="sync")

result = llm.chat("Write a paragfraph about space", model="gpt-4o",)
print(result)

llm = LLM(provider="openai", 
          proxy_config=ProxyConfig(host="0.0.0.0", port="8001"),
          tracking_config=TrackingConfig(host="0.0.0.0", port="8002"),
          session_id="sync stream")
response = llm.chat("Write a paragfraph about space", model="gpt-4o", is_stream=True)
for i, chunk in enumerate(response):
    if i%20==0:
        print("\n")
    if not chunk.metrics:
        print(chunk.chat_output_stream, end="", flush=True)
    else:
        print("\n\n## Metrics:")
        print(chunk.metrics)


import asyncio

# stream
print("\nasync stream")

async def async_stream():
    llm = LLM(provider="openai", 
          proxy_config=ProxyConfig(host="0.0.0.0", port="8001"),
          tracking_config=TrackingConfig(host="0.0.0.0", port="8002"),
          session_id="async stream")
    
    response_async_stream = await llm.achat("Write a paragfraph about space", model="gpt-4o", is_stream=True)
    async for p in response_async_stream:
        
        # pprint(p.choices[0].delta.content==p.chat_output)
        # print("metrics: ", p.metrics)
        # print(p)
        if not p.metrics:
            print(p.chat_output_stream, end="", flush=True)
        else:
            print(p.metrics)
asyncio.run(async_stream())

async def async_chat():
    llm = LLM(provider="openai", 
          proxy_config=ProxyConfig(host="0.0.0.0", port="8001"),
          tracking_config=TrackingConfig(host="0.0.0.0", port="8002"),
          session_id="async")
    response_async = await llm.achat("Write a paragfraph about space", model="gpt-4o", is_stream=False)
    print(response_async)
    
asyncio.run(async_chat())


async def async_chat():
    llm = LLM(provider="openai", 
          proxy_config=ProxyConfig(host="0.0.0.0", port="8001"),
          tracking_config=TrackingConfig(host="0.0.0.0", port="8002"))
    response_async = await llm.achat("Write a paragfraph about space", model="gpt-4o", is_stream=False)
    print(response_async)
    
asyncio.run(async_chat())