# %% [markdown]
# # Langchain integration

# %% [markdown]
# ### LLMstudio setup

# %%
import os
from llmstudio.langchain import ChatLLMstudio
from llmstudio.llm import LLM

llm = LLM(provider="openai")
chat_llm = ChatLLMstudio(llm=llm, model = "gpt-4o-mini", parameters={"temperature":0})
# chat_llm = ChatLLMstudio(model_id='vertexai/gemini-1.5-flash', temperature=0)

# %% [markdown]
# ### Langchain setup

# %%
from langchain.tools import tool
from langchain.agents import AgentType, initialize_agent

# %%
print("\n", chat_llm.invoke('Hello'))

# %% [markdown]
# ### Example 1: Train ticket

# %%
@tool
def get_departure(ticket_number: str):
    """Use this to fetch the departure time of a train"""
    return "12:00 AM"

@tool
def buy_ticket(destination: str):
    """Use this to buy a ticket"""
    return "Bought ticket number 123456"


def assistant(question: str)->str:
    tools = [get_departure, buy_ticket]
    print(tools)

    #rebuild agent with new tools
    agent_executor = initialize_agent(
        tools, chat_llm, agent=AgentType.OPENAI_FUNCTIONS, verbose = True, debug = True
    )

    response = agent_executor.invoke({"input": question})

    return response

# %%
assistant('When does my train depart? My ticket is 1234')


# %%
assistant('Buy me a ticket to Madrid and tell the departure time')

# %% [markdown]
# ### Example 2: Start a party

# %%
@tool
def power_disco_ball(power: bool) -> bool:
    """Powers the spinning disco ball."""
    print(f"Disco ball is {'spinning!' if power else 'stopped.'}")
    return True

@tool
def start_music(energetic: bool, loud: bool, bpm: int) -> str:
    """Play some music matching the specified parameters.
    """
    print(f"Starting music! {energetic=} {loud=}, {bpm=}")
    return "Never gonna give you up."

@tool
def dim_lights(brightness: float) -> bool:
    """Dim the lights.
    """
    print(f"Lights are now set to {brightness:.0%}")
    return True


# %%
def assistant(question: str)->str:
    tools = [power_disco_ball, start_music, dim_lights]
    print(tools)

    #rebuild agent with new tools
    agent_executor = initialize_agent(
        tools, chat_llm, agent=AgentType.OPENAI_FUNCTIONS, verbose = True, debug = True
    )

    response = agent_executor.invoke(
        {
            "input": question
        }
    )

    return response

# %%
assistant('Turn this into a party!')


# azure
llm = LLM(provider="azure", api_key=os.environ["AZURE_API_KEY"], 
                               api_version=os.environ["AZURE_API_VERSION"],
                               api_endpoint=os.environ["AZURE_API_ENDPOINT"])
chat_llm = ChatLLMstudio(llm=llm, model = "gpt-4o-mini", parameters={"temperature":0})
# chat_llm = ChatLLMstudio(model_id='vertexai/gemini-1.5-flash', temperature=0)

# %% [markdown]
# ### Langchain setup

# %%
from langchain.tools import tool
from langchain.agents import AgentType, initialize_agent

# %%
print("\n", chat_llm.invoke('Hello'))

# %% [markdown]
# ### Example 1: Train ticket

# %%
@tool
def get_departure(ticket_number: str):
    """Use this to fetch the departure time of a train"""
    return "12:00 AM"

@tool
def buy_ticket(destination: str):
    """Use this to buy a ticket"""
    return "Bought ticket number 123456"


def assistant(question: str)->str:
    tools = [get_departure, buy_ticket]
    print(tools)

    #rebuild agent with new tools
    agent_executor = initialize_agent(
        tools, chat_llm, agent=AgentType.OPENAI_FUNCTIONS, verbose = True, debug = True
    )

    response = agent_executor.invoke({"input": question})

    return response

# %%
assistant('When does my train depart? My ticket is 1234')


# %%
assistant('Buy me a ticket to Madrid and tell the departure time')

# %% [markdown]
# ### Example 2: Start a party

# %%
@tool
def power_disco_ball(power: bool) -> bool:
    """Powers the spinning disco ball."""
    print(f"Disco ball is {'spinning!' if power else 'stopped.'}")
    return True

@tool
def start_music(energetic: bool, loud: bool, bpm: int) -> str:
    """Play some music matching the specified parameters.
    """
    print(f"Starting music! {energetic=} {loud=}, {bpm=}")
    return "Never gonna give you up."

@tool
def dim_lights(brightness: float) -> bool:
    """Dim the lights.
    """
    print(f"Lights are now set to {brightness:.0%}")
    return True


# %%
def assistant(question: str)->str:
    tools = [power_disco_ball, start_music, dim_lights]
    print(tools)

    #rebuild agent with new tools
    agent_executor = initialize_agent(
        tools, chat_llm, agent=AgentType.OPENAI_FUNCTIONS, verbose = True, debug = True
    )

    response = agent_executor.invoke(
        {
            "input": question
        }
    )

    return response

# %%
assistant('Turn this into a party!')


# azure