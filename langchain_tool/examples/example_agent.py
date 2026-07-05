"""
Example LangChain agent that uses The Factory tools.

Before running:
    pip install langchain-the-factory langchain-openai
    export OPENAI_API_KEY="sk-..."
    export THE_FACTORY_PRIVATE_KEY="your_base58_solana_private_key"

Then:
    python example_agent.py
"""
import os
import sys

from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI

from langchain_the_factory import FactoryToolkit


def main():
    private_key = os.environ.get("THE_FACTORY_PRIVATE_KEY")
    if not private_key:
        print("ERROR: set THE_FACTORY_PRIVATE_KEY environment variable.")
        sys.exit(1)

    if not os.environ.get("OPENAI_API_KEY"):
        print("ERROR: set OPENAI_API_KEY environment variable.")
        sys.exit(1)

    # Initialize the toolkit
    toolkit = FactoryToolkit(private_key_base58=private_key)
    tools = toolkit.get_tools()

    print(f"Loaded {len(tools)} tools:")
    for t in tools:
        print(f"  - {t.name}")
    print()

    # Build the agent
    prompt = ChatPromptTemplate.from_messages([
        ("system", (
            "You are a helpful assistant with access to real-time data tools. "
            "Each tool call costs between $0.01 and $0.05 USD. Be judicious — "
            "only call a tool if the user actually needs that data. "
            "If a tool fails, explain what went wrong and suggest alternatives."
        )),
        ("user", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ])

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    agent = create_openai_tools_agent(llm, tools, prompt)
    executor = AgentExecutor(agent=agent, tools=tools, verbose=True, max_iterations=5)

    # Example queries
    queries = [
        "What's the weather in Milano for the next 3 days?",
        "Should I exchange EUR to JPY today? Check the trend over the last 7 days.",
        "How active is the facebook/react repo on GitHub right now?",
    ]

    for q in queries:
        print("=" * 60)
        print(f"USER: {q}")
        print("=" * 60)
        result = executor.invoke({"input": q})
        print(f"\nFINAL ANSWER: {result['output']}\n")

    toolkit.close()


if __name__ == "__main__":
    main()
