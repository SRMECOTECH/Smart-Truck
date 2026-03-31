import asyncio
from langchain_mcp_adapters.client import MultiServerMCPClient
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.messages import ToolMessage
import json

load_dotenv()

SERVERS = {
    "math": {
        "transport": "stdio",
        "command": "C:/Users/Sanjoy Chattopadhyay/AppData/Local/Programs/Python/Python313/Scripts/uv.exe",
        "args": [
            "run",
            "--directory",
            "D:/Projects/MCP/Local-MCP-Math-Server",
            "fastmcp",
            "run",
            "main.py"
        ]
    },
    "expense": {
        "transport": "streamable_http",
        "url":"https://academic-gold-weasel.fastmcp.app/mcp",
"headers": {
        "Authorization": "Bearer fmcp_qF5N1DBU3YSshLbDznfJwgpmECIeB4olMR9efL0HPSk"
    }

    }
}

async def main():

    client = MultiServerMCPClient(SERVERS)
    tools = await client.get_tools()

    named_tools = {tool.name: tool for tool in tools}
    print("Available tools:", list(named_tools.keys()))

    llm = ChatGroq(model="llama-3.3-70b-versatile")
    llm_with_tools = llm.bind_tools(tools)

    prompt = "Add an expense Rs 800 on groceries on 10th march 2026."
    response = await llm_with_tools.ainvoke(prompt)

    if not getattr(response, "tool_calls", None):
        print("\nLLM Reply:", response.content)
        return

    tool_messages = []
    for tc in response.tool_calls:
        tool_name = tc["name"]
        tool_args = tc.get("args") or {}
        tool_id = tc["id"]

        print(f"Calling tool: {tool_name} with args: {tool_args}")

        result = await named_tools[tool_name].ainvoke(tool_args)
        tool_messages.append(
            ToolMessage(tool_call_id=tool_id, content=json.dumps(result))
        )

    final_response = await llm_with_tools.ainvoke(
        [{"role": "user", "content": prompt}, response, *tool_messages]
    )
    print(f"\nFinal response: {final_response.content}")


if __name__ == '__main__':
    asyncio.run(main())