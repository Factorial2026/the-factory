# langchain-the-factory

LangChain Tool integration for [The Factory](https://github.com/Factorial2026/the-factory) — an x402 micropayment agent that sells clean JSON data to AI agents.

## Install

```bash
pip install langchain-the-factory
```

## Quick start

```python
from langchain_the_factory import FactoryToolkit
from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain_openai import ChatOpenAI

# Initialize the toolkit with your Solana keypair
toolkit = FactoryToolkit(
    private_key_base58="YOUR_BASE58_PRIVATE_KEY",
    # optional: token="bulk_..." for pre-paid mode
)

# Get all 6 endpoint tools
tools = toolkit.get_tools()

# Build an agent that can call them
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
agent = create_openai_tools_agent(llm, tools, prompt)
executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

# Ask the agent anything that needs real-world data
executor.invoke({
    "input": "What's the weather in Milano for the next 3 days? "
             "Also check EUR/USD trend over the last 7 days."
})
```

## Available tools

Each of the 6 endpoints becomes a LangChain Tool with auto-generated docstring:

- `get_weather` — `/api/v1/meteo` ($0.01/call)
- `get_fx_rate` — `/api/v1/fx` ($0.02/call)
- `get_transit_arrivals` — `/api/v1/transit` ($0.02/call)
- `get_tech_news` — `/api/v1/news` ($0.02/call)
- `get_stock_price` — `/api/v1/stocks` ($0.05/call)
- `get_github_stats` — `/api/v1/github-stats` ($0.02/call)

## Cost management

Each tool call costs $0.01-0.05. To control spend:

1. **Use bulk packs**: `toolkit = FactoryToolkit(token="bulk_...")` for 10 calls at $0.08.
2. **Use subscription**: $50/mo for 10,000 calls. Best for production agents.
3. **Cache hits are free**: identical queries (same city, same date range) cost nothing
   for 1 hour due to server-side caching.

## LangChain Hub submission

To submit this tool to the official LangChain Hub:

```bash
pip install langchainhub
langchainhub login  # uses your LangChain account
langchainhub push langchain-the-factory
```

After review, the tool will be available at `hub.langchain.com/the-factory`.

## License

MIT
