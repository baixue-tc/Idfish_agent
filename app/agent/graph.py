
from .context import IdlefishContext
from langgraph.graph import StateGraph,START,END
from .node import intent_node,rag_agent_node,human_node
from .state import IdlefishState




async def create_idlefish_graph(checkpointer):

    idlefish_graph = (StateGraph(
                     IdlefishState,
                     IdlefishContext
    )
             .add_node("intent_node", intent_node)
             .add_node("rag_agent_node", rag_agent_node)
             .add_node("human_node", human_node)
             .add_edge(START, "intent_node")
             .add_edge("rag_agent_node", END)
             .add_edge("human_node", END)
             .compile(checkpointer=checkpointer)
             )
    return idlefish_graph




