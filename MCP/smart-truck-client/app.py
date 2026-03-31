"""
Smart-Truck MCP Chatbot — Streamlit UI powered by Groq LLM.
Connects to Backend MCP Server (port 8002) and ML MCP Server (port 8003).
Shows available tools and which tools were used per query.
"""

import os
import json
import asyncio
import streamlit as st
from dotenv import load_dotenv

from langchain_groq import ChatGroq
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_core.messages import (
    HumanMessage, AIMessage, ToolMessage, SystemMessage,
)

load_dotenv()

# ── MCP Server Configuration ────────────────────────────────────────────────

UV_PATH = os.getenv(
    "UV_PATH",
    "C:/Users/Sanjoy Chattopadhyay/AppData/Local/Programs/Python/Python313/Scripts/uv.exe",
)

SERVERS_DIR = os.path.join(os.path.dirname(__file__), "..", "smart-truck-servers")
SERVERS_DIR = os.path.normpath(SERVERS_DIR)

SERVERS = {
    "backend": {
        "transport": "stdio",
        "command": UV_PATH,
        "args": [
            "run", "--directory", SERVERS_DIR,
            "fastmcp", "run", "backend_server.py",
        ],
    },
    "ml": {
        "transport": "stdio",
        "command": UV_PATH,
        "args": [
            "run", "--directory", SERVERS_DIR,
            "fastmcp", "run", "ml_server.py",
        ],
    },
}

SYSTEM_PROMPT = """You are the Smart-Truck Fleet Assistant. You help fleet managers query data, analyze performance, and run ML predictions.

You have access to two categories of tools:

**Backend Tools** — Query fleet data from the database:
  Dashboard (fleet summary, daily trends, top drivers, route heatmap, alerts),
  Drivers (list, detail, trips, trends, driving patterns),
  Vehicles (list, detail, trips),
  Trips (list with filters, stats, detail),
  Routes (list, detail analysis),
  Admin (migration status, refresh summaries).

**ML Tools** — Run ML predictions and manage models:
  ETA prediction, anomaly detection, driver scoring, demand forecasting,
  trip forecasting, route optimization, hub analysis, driver recommendation,
  model management (list, compare, details, train, cache).

When calling tools:
- Use the right tool for the query. Prefer specific tools over generic list tools.
- For driver/vehicle lookups by name, first use list_drivers/list_vehicles with search param to find the ID, then use the detail tool.
- After tools return data, give a clear, concise answer. Format numbers nicely.
- If a tool fails, explain what went wrong and suggest alternatives.
"""

# ── Streamlit Page Config ────────────────────────────────────────────────────

st.set_page_config(
    page_title="Smart-Truck Fleet Assistant",
    page_icon="🚛",
    layout="wide",
)


# ── Async Helper ─────────────────────────────────────────────────────────────

def run_async(coro):
    """Run an async coroutine from sync Streamlit context."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ── Initialize Session ──────────────────────────────────────────────────────

def initialize():
    """One-time setup: LLM, MCP client, tool binding."""
    # LLM
    st.session_state.llm = ChatGroq(
        model="llama-3.3-70b-versatile",
        temperature=0,
    )

    # MCP tools
    st.session_state.mcp_client = MultiServerMCPClient(SERVERS)
    tools = run_async(st.session_state.mcp_client.get_tools())
    st.session_state.tools = tools
    st.session_state.tool_by_name = {t.name: t for t in tools}

    # Classify tools by server
    backend_tools = []
    ml_tools = []
    for t in tools:
        name = t.name
        # Tools from backend_server vs ml_server
        if any(
            name.startswith(p)
            for p in [
                "get_fleet", "get_daily", "get_top_drivers", "get_route_heatmap",
                "get_recent_alerts", "list_drivers", "get_driver", "list_vehicles",
                "get_vehicle", "list_trips", "get_trip", "list_routes",
                "get_route_detail", "get_migration", "refresh_summaries",
            ]
        ):
            backend_tools.append(name)
        else:
            ml_tools.append(name)

    st.session_state.backend_tools = sorted(backend_tools)
    st.session_state.ml_tools = sorted(ml_tools)

    # Bind tools to LLM
    st.session_state.llm_with_tools = st.session_state.llm.bind_tools(tools)

    # Conversation
    st.session_state.history = [SystemMessage(content=SYSTEM_PROMPT)]
    st.session_state.chat_display = []  # List of dicts for rendering
    st.session_state.initialized = True


if "initialized" not in st.session_state:
    with st.spinner("Connecting to MCP servers..."):
        initialize()

# ── Sidebar: Available Tools ────────────────────────────────────────────────

with st.sidebar:
    st.header("Available Tools")

    total = len(st.session_state.tools)
    st.metric("Total Tools", total)

    with st.expander(f"Backend Tools ({len(st.session_state.backend_tools)})", expanded=False):
        for name in st.session_state.backend_tools:
            tool = st.session_state.tool_by_name[name]
            desc = tool.description.split(".")[0] if tool.description else ""
            st.markdown(f"**`{name}`**  \n{desc}")

    with st.expander(f"ML Tools ({len(st.session_state.ml_tools)})", expanded=False):
        for name in st.session_state.ml_tools:
            tool = st.session_state.tool_by_name[name]
            desc = tool.description.split(".")[0] if tool.description else ""
            st.markdown(f"**`{name}`**  \n{desc}")

    st.divider()
    if st.button("Clear Chat"):
        st.session_state.history = [SystemMessage(content=SYSTEM_PROMPT)]
        st.session_state.chat_display = []
        st.rerun()

# ── Main Chat Area ──────────────────────────────────────────────────────────

st.title("🚛 Smart-Truck Fleet Assistant")
st.caption("Ask anything about your fleet — I'll use the right tools automatically.")

# Render chat history
for entry in st.session_state.chat_display:
    role = entry["role"]
    with st.chat_message(role):
        st.markdown(entry["content"])
        if "tools_used" in entry and entry["tools_used"]:
            tools_str = ", ".join(f"`{t}`" for t in entry["tools_used"])
            st.caption(f"Tools used: {tools_str}")

# Chat input
user_text = st.chat_input("Ask about your fleet...")

if user_text:
    # Display user message
    with st.chat_message("user"):
        st.markdown(user_text)
    st.session_state.chat_display.append({"role": "user", "content": user_text})
    st.session_state.history.append(HumanMessage(content=user_text))

    # Get LLM response
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            first = run_async(
                st.session_state.llm_with_tools.ainvoke(st.session_state.history)
            )

        tool_calls = getattr(first, "tool_calls", None)

        if not tool_calls:
            # Direct answer — no tools needed
            st.markdown(first.content or "")
            st.session_state.history.append(first)
            st.session_state.chat_display.append({
                "role": "assistant",
                "content": first.content or "",
                "tools_used": [],
            })
        else:
            # Execute tools
            st.session_state.history.append(first)

            tools_used = []
            tool_msgs = []

            for tc in tool_calls:
                name = tc["name"]
                args = tc.get("args") or {}
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except Exception:
                        pass

                tools_used.append(name)
                st.caption(f"Calling `{name}({json.dumps(args, default=str)})`...")

                try:
                    tool = st.session_state.tool_by_name[name]
                    result = run_async(tool.ainvoke(args))
                    result_str = json.dumps(result, default=str)
                    # Truncate very large results to avoid context overflow
                    if len(result_str) > 8000:
                        result_str = result_str[:8000] + '... [truncated]'
                    tool_msgs.append(
                        ToolMessage(tool_call_id=tc["id"], content=result_str)
                    )
                except Exception as e:
                    tool_msgs.append(
                        ToolMessage(
                            tool_call_id=tc["id"],
                            content=json.dumps({"error": str(e)}),
                        )
                    )

            st.session_state.history.extend(tool_msgs)

            # Final LLM response using tool results
            with st.spinner("Analyzing results..."):
                final = run_async(
                    st.session_state.llm.ainvoke(st.session_state.history)
                )

            st.markdown(final.content or "")

            tools_str = ", ".join(f"`{t}`" for t in tools_used)
            st.caption(f"Tools used: {tools_str}")

            st.session_state.history.append(AIMessage(content=final.content or ""))
            st.session_state.chat_display.append({
                "role": "assistant",
                "content": final.content or "",
                "tools_used": tools_used,
            })
