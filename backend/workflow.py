from typing import TypedDict

from langgraph.graph import (
    StateGraph,
    END
)

from agent import llm

# AGENTS
from agents.router_agent import (
    router_agent
)

from agents.resume_agent import (
    resume_agent
)

from agents.research_agent_node import (
    research_agent
)

from agents.career_agent import (
    career_agent
)

from agents.interview_agent import (
    interview_agent
)

# STATE
class AgentState(TypedDict):

    user_input: str
    resume_text: str
    response: str

    selected_agent: str
    retrieved_memories: list
    retrieved_chunks: list


# NODES
def router_node(state: AgentState):

    user_input = state["user_input"]

    selected_agent = router_agent(
        user_input
    )

    return {
        "selected_agent": selected_agent
    }


def resume_node(state: AgentState):

    user_input = state["user_input"]

    resume_text = state.get(
        "resume_text",
        ""
    )

    response = resume_agent(
        user_input,
        resume_text
    )

    return {
        "response": response,
        "selected_agent": "resume",
        "retrieved_memories": [],
        "retrieved_chunks": []
    }


def research_node(state: AgentState):

    user_input = state["user_input"]

    response, retrieved_chunks = research_agent(
        user_input,
        return_chunks=True
    )

    return {
        "response": response,
        "selected_agent": "research",
        "retrieved_memories": [],
        "retrieved_chunks": retrieved_chunks
    }


def interview_node(state: AgentState):

    user_input = state["user_input"]

    response = interview_agent(
        user_input
    )

    return {
        "response": response,
        "selected_agent": "interview",
        "retrieved_memories": [],
        "retrieved_chunks": []
    }


def career_node(state: AgentState):

    user_input = state["user_input"]

    response = career_agent(
        user_input
    )

    return {
        "response": response,
        "selected_agent": "career",
        "retrieved_memories": [],
        "retrieved_chunks": []
    }


# CONDITIONAL ROUTING FUNCTION
def route_agent(state: AgentState):

    agent = state.get("selected_agent", "career")

    if "resume" in agent:

        return "resume"

    elif "research" in agent:

        return "research"

    elif "interview" in agent:

        return "interview"

    else:

        return "career"


# BUILD GRAPH
graph = StateGraph(AgentState)

# ADD NODES
graph.add_node(
    "router",
    router_node
)

graph.add_node(
    "resume",
    resume_node
)

graph.add_node(
    "research",
    research_node
)

graph.add_node(
    "interview",
    interview_node
)

graph.add_node(
    "career",
    career_node
)

# FLOW
graph.set_entry_point("router")

# CONDITIONAL EDGE
graph.add_conditional_edges(
    "router",
    route_agent,
    {
        "resume": "resume",
        "research": "research",
        "interview": "interview",
        "career": "career"
    }
)

# CONNECT CHANNELS TO END
graph.add_edge("resume", END)
graph.add_edge("research", END)
graph.add_edge("interview", END)
graph.add_edge("career", END)

# COMPILE
app_workflow = graph.compile()