from langgraph.types import Command,interrupt
import logging
from .state import IdlefishState
from langchain.messages import ToolMessage, HumanMessage, SystemMessage
from .model import intent_llm
from .prompt import INTENT_PROMPT
from .rag_agent import rag_agent
from .context import IdlefishContext
from langgraph.runtime import Runtime

logger = logging.getLogger(__name__)

async def intent_node(state:IdlefishState)->Command:
    """识别用户意图节点"""
    # 识别用户意图
    intent = await intent_llm.ainvoke([SystemMessage(
        content = INTENT_PROMPT),
         HumanMessage(state["messages"][-1].content)],
        extra_body = {"thinking": {"type": "disabled"}}
    )
    logger.info(f"识别到意图转入节点-> {intent.intent}")
    next_node = intent.intent
    return Command(update = {"intent":intent}, goto = next_node)

async def rag_agent_node(state:IdlefishState,runtime:Runtime[IdlefishContext]):
    """rag_agent节点"""
    results = await rag_agent.ainvoke({"messages":state["messages"]},context = runtime.context)
    new_response = results["messages"][len(state["messages"]):]
    product_info = None
    need_human = False
    for msg in new_response:
        if isinstance(msg,ToolMessage):
            if msg.name == "search_knowledge_base":
                product_info = msg.content
            elif msg.name == "to_human":
                need_human = True
    if need_human:
        logger.info("需要人工处理,转入人工节点")
        return Command(goto = "human_node",update = {"messages":new_response,"product_info":product_info})
    return  {"messages":new_response,"product_info":product_info}

def human_node(state:IdlefishState,runtime:Runtime[IdlefishContext]):
    """人工节点"""
    interrupt({"type":"human_node",
               "user_message":state["messages"][-1].content,
               "product_id":runtime.context.product_id,
               "user_id":runtime.context.user_id,
               "product_info":state.get("product_info",""),
               "message":"请人工处理"}
              )
    return {}