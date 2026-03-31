import os
from typing import Annotated, TypedDict, List
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, SystemMessage, ToolMessage
from langgraph.prebuilt import ToolNode
import json
from dotenv import load_dotenv
import time
import sys

# Ensure the root project directory is in the path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from utils.logger import get_api_logger
logger = get_api_logger()

from mcp_tools import MQ_TOOLS

load_dotenv()

# --- State Definition ---
class AgentState(TypedDict):
    """The graph state tracking the conversation history."""
    messages: Annotated[list[BaseMessage], add_messages]

# --- LLM Setup ---
llm = ChatOpenAI(
    model=os.getenv("OPENAI_MODEL", "gpt-4o"), 
    temperature=0
).bind_tools(MQ_TOOLS)

from prompts import MQ_SYSTEM_PROMPT

from prompts import MQ_SYSTEM_PROMPT

system_prompt = SystemMessage(content=MQ_SYSTEM_PROMPT)

# --- Nodes ---
async def chatbot(state: AgentState):
    """The main LLM node that decides whether to answer or call a tool."""
    messages = state["messages"]
    
    # Ensure system prompt is always present
    if not messages or not isinstance(messages[0], SystemMessage):
        messages = [system_prompt] + messages
        
    start_time = time.time()
    response = await llm.ainvoke(messages)
    duration_ms = (time.time() - start_time) * 1000
    
    logger.info("LLM inference complete", extra={"metrics": {"llm_execution_ms": duration_ms}})
    return {"messages": [response]}

# The ToolNode executes the functions automatically if the LLM requests them
tool_node = ToolNode(tools=MQ_TOOLS)

# --- Routing ---
def should_continue(state: AgentState):
    """Determine if we need to call tools or end the conversation."""
    last_message = state["messages"][-1]
    if last_message.tool_calls:
        tool_names = [call['name'] for call in last_message.tool_calls]
        logger.info("Agent decided to call tools", extra={"context": {"tools": tool_names}})
        return "tools"
    
    logger.info("Agent decided to end generation")
    return END

# --- Graph Assembly ---
workflow = StateGraph(AgentState)

workflow.add_node("chatbot", chatbot)
workflow.add_node("tools", tool_node)

workflow.add_edge(START, "chatbot")
workflow.add_conditional_edges("chatbot", should_continue, ["tools", END])
workflow.add_edge("tools", "chatbot")

# Compile the graph
agent = workflow.compile()

async def process_chat(history: List[BaseMessage], session_id: str = "unknown") -> tuple[str, List[str]]:
    """Helper wrapper to invoke the graph from the API."""
    logger.info("Starting graph execution", extra={"context": {"session_id": session_id, "history_len": len(history)}})
    start_time = time.time()
    
    result = await agent.ainvoke({"messages": history})
    
    duration_ms = (time.time() - start_time) * 1000
    logger.info("Graph execution completed", extra={"metrics": {"total_graph_execution_ms": duration_ms}})
    
    # The final message is the LLM's text response
    final_message = result["messages"][-1]
    
    # Extract the names of any tools that were called during this turn
    tools_used = []
    for msg in result["messages"]:
        if isinstance(msg, ToolMessage):
            tools_used.append(msg.name)
            
    # Deduplicate tool names
    tools_used = list(set(tools_used))
            
    return final_message.content, tools_used
