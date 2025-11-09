# main.py
from dotenv import load_dotenv
import os
load_dotenv()

from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import BaseModel
from tavily import TavilyClient
from typing import TypedDict, List
import json
from collections import ChainMap

from supabase import create_client

# ======================================
# ✅ Supabase Setup
# ======================================
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
TABLE_NAME = "graph_state"

# ======================================
# ✅ Supabase persistence class (HTTPS version)
# ======================================
class SupabaseSaver:
    def __init__(self, url, key, table_name="graph_state"):
        self.client = create_client(url, key)
        self.table_name = table_name

    def _to_json_safe(self, obj):
        """Recursively convert unsupported objects into JSON-safe types."""
        if isinstance(obj, ChainMap):
            # Convert ChainMap to dict first
            return self._to_json_safe(dict(obj))
        elif isinstance(obj, dict):
            # Recursively process all dict items
            return {str(k): self._to_json_safe(v) for k, v in obj.items()}
        elif isinstance(obj, (list, tuple, set)):
            # Recursively process lists, tuples, and sets
            return [self._to_json_safe(v) for v in obj]
        elif isinstance(obj, (str, int, float, bool)) or obj is None:
            return obj
        else:
            # Convert any other object (e.g., custom classes) to string
            return str(obj)

    def put(self, key, data, *args, **kwargs):
        """Save data to Supabase, ensuring it is JSON-serializable."""
        if isinstance(key, dict) and 'configurable' in key:
            # Handle configuration data specially
            config_data = {
                'tags': key.get('tags', []),
                'metadata': dict(key.get('metadata', {})),
                'callbacks': key.get('callbacks'),
                'recursion_limit': key.get('recursion_limit'),
                'configurable': {
                    'checkpoint_ns': key['configurable'].get('checkpoint_ns', ''),
                    'thread_id': key['configurable'].get('thread_id', '')
                    # Omit __pregel_runtime as it's not JSON serializable
                }
            }
            safe_data = self._to_json_safe(config_data)
        else:
            safe_data = self._to_json_safe(data)
        try:
            self.client.table(self.table_name).upsert({"id": str(key) if not isinstance(key, dict) else key['configurable'].get('thread_id', ''), "data": safe_data}).execute()
        except Exception as e:
            # Optional: log the error or re-raise with more context
            raise RuntimeError(f"Failed to upsert key {key} to Supabase: {e}") from e

    def put_writes(self, *args, **kwargs):
        return self.put(*args, **kwargs)

    def get_tuple(self, key):
        """Retrieve data from Supabase."""
        res = self.client.table(self.table_name).select("data").eq("id", key).execute()
        if res.data and len(res.data) > 0:
            return res.data[0]["data"]
        return None

    def get_next_version(self, *args, **kwargs):
        return 1

memory = SupabaseSaver(SUPABASE_URL, SUPABASE_KEY)

# ======================================
# ✅ LLM & API Setup
# ======================================
tavily = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
model = ChatOpenAI(model="gpt-3.5-turbo", temperature=0)

# ======================================
# ✅ State Definition
# ======================================
class AgentState(TypedDict):
    task: str
    plan: str
    draft: str
    critique: str
    content: List[str]
    revision_number: int
    max_revisions: int

# ======================================
# ✅ Prompts
# ======================================
PLAN_PROMPT = "You are an expert essay planner. Create a clear, structured outline for the topic."
WRITER_PROMPT = "You are an expert essay writer. Write or improve the essay below based on the topic and plan. Use this context: {content}"
REFLECTION_PROMPT = "You are a professor. Provide detailed critique on the essay."
RESEARCH_PLAN_PROMPT = "Generate up to 3 web search queries to gather relevant facts for writing this essay."
RESEARCH_CRITIQUE_PROMPT = "Generate up to 3 search queries to find information for improving the essay after feedback."

class Queries(BaseModel):
    queries: List[str]

# ======================================
# ✅ Nodes (Graph Steps)
# ======================================
def plan_node(state: AgentState):
    messages = [
        SystemMessage(content=PLAN_PROMPT),
        HumanMessage(content=state["task"])
    ]
    response = model.invoke(messages)
    return {"plan": response.content}

def research_plan_node(state: AgentState):
    queries = model.with_structured_output(Queries).invoke([
        SystemMessage(content=RESEARCH_PLAN_PROMPT),
        HumanMessage(content=state["task"])
    ])
    content = []
    for q in queries.queries:
        results = tavily.search(query=q, max_results=2)
        for r in results["results"]:
            content.append(r["content"])
    return {"content": content}

def generation_node(state: AgentState):
    content = "\n\n".join(state["content"] or [])
    messages = [
        SystemMessage(content=WRITER_PROMPT.format(content=content)),
        HumanMessage(content=f"Topic: {state['task']}\n\nPlan: {state['plan']}")
    ]
    response = model.invoke(messages)
    return {"draft": response.content, "revision_number": state["revision_number"] + 1}

def reflection_node(state: AgentState):
    messages = [
        SystemMessage(content=REFLECTION_PROMPT),
        HumanMessage(content=state["draft"])
    ]
    response = model.invoke(messages)
    return {"critique": response.content}

def research_critique_node(state: AgentState):
    queries = model.with_structured_output(Queries).invoke([
        SystemMessage(content=RESEARCH_CRITIQUE_PROMPT),
        HumanMessage(content=state["critique"])
    ])
    content = state["content"] or []
    for q in queries.queries:
        results = tavily.search(query=q, max_results=2)
        for r in results["results"]:
            content.append(r["content"])
    return {"content": content}

def should_continue(state):
    if state["revision_number"] > state["max_revisions"]:
        return END
    return "reflect"

# ======================================
# ✅ Graph Construction
# ======================================
builder = StateGraph(AgentState)
builder.add_node("planner", plan_node)
builder.add_node("research_plan", research_plan_node)
builder.add_node("generate", generation_node)
builder.add_node("reflect", reflection_node)
builder.add_node("research_critique", research_critique_node)

builder.set_entry_point("planner")
builder.add_edge("planner", "research_plan")
builder.add_edge("research_plan", "generate")
builder.add_edge("reflect", "research_critique")
builder.add_edge("research_critique", "generate")
builder.add_conditional_edges("generate", should_continue, {END: END, "reflect": "reflect"})

graph = builder.compile(checkpointer=memory)

# ======================================
# ✅ Run a test
# ======================================
if __name__ == "__main__":
    thread = {"configurable": {"thread_id": "1"}}
    for step in graph.stream({
        "task": "What are the advantages and disadvantages of AI in education?",
        "max_revisions": 2,
        "revision_number": 1,
        "plan": "",
        "draft": "",
        "critique": "",
        "content": []
    }, thread):
        print(json.dumps(step, indent=2))
