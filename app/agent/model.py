from pydantic import BaseModel, Field
from typing import Literal
from langchain.chat_models import init_chat_model

class IntentRecognition(BaseModel):
    intent:Literal["rag_agent_node","human_node"] = Field(description="用户意图分类,下一节点的走向,对应:Rag_agent,人工处理")

llm = init_chat_model("deepseek-v4-flash")

intent_llm = llm.with_structured_output(IntentRecognition)