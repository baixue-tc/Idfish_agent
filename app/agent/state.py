from langgraph.graph import add_messages
from typing import TypedDict
from langchain_core.messages import BaseMessage
from typing import Annotated
from .model import IntentRecognition
class IdlefishState(TypedDict):
    # 消息
    messages: Annotated[list[BaseMessage], add_messages]
    # 用户意图分类
    intent:IntentRecognition
    # 外部数据
    product_info:str # 商品信息

