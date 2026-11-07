import asyncio
import sys
import json
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def main():
    print("Launching MCP Hallucination Checker server over STDIO...\n")
    server_params = StdioServerParameters(
        command=sys.executable,
        args=["server/main.py"]
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            print("Initializing connection...")
            await session.initialize()
            print("Connected successfully!\n")

            hypothesis = "The CEO resigned in Q2, causing a 10% drop in stock."
            premise = "The CEO resigned in Q3, resulting in a sudden 10% stock price jump."
            
            print(f"Hypothesis: {hypothesis}")
            print(f"Premise:    {premise}")
            print("\nCalling verify_logic_chain tool...\n")

            result = await session.call_tool(
                "verify_logic_chain",
                arguments={
                    "request": {
                        "hypothesis": hypothesis,
                        "premise": premise
                    }
                }
            )

            print("================ Server Response ================\n")
            if hasattr(result, "content") and result.content:
                # FastMCP wraps PyDantic responses nicely in the MCP text content
                print(result.content[0].text)
            else:
                print(result)
            print("\n=================================================")

if __name__ == "__main__":
    asyncio.run(main())
