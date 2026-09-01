from contextlib import asynccontextmanager
import logging
import os

from dotenv import load_dotenv
from fastapi import FastAPI,Request
from langgraph.checkpoint.mysql.aio import AIOMySQLSaver

from models.session import ChatRequest,ChatResponse
from agent.graph import create_idlefish_graph
from langchain.messages import HumanMessage
from agent.context import IdlefishContext
import uvicorn
from common.logger import setup_logging

load_dotenv()
logger = logging.getLogger(__name__)
# 初始化日志
setup_logging()

DB_URI = os.getenv("DB_URL")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """创建数据库生命周期"""
    async with AIOMySQLSaver.from_conn_string(DB_URI) as checkpointer:
        await checkpointer.setup()
        app.state.graph = await create_idlefish_graph(checkpointer)
        logger.info("数据库与Graph初始化成功")
        yield
    logger.info("数据库与Graph关闭")


app = FastAPI(title = "IdlefishAgent",
              description = "闲鱼客服机器人",
              version = "v0.1",
              lifespan= lifespan
              )


@app.post("/chat")
async def chat(request:Request,chat_request:ChatRequest):
    """聊天接口"""
    query = chat_request.message
    logger.info(f"================用户消息:{query}===================")
    graph = request.app.state.graph
    context = IdlefishContext(product_id = chat_request.product_id,user_id = chat_request.user_id)
    config = {"configurable":{"thread_id":chat_request.user_id}}
    response = await graph.ainvoke({"messages":[HumanMessage(query)]},context = context,config = config)
    logger.info(f"================商家回复:{response['messages'][-1].content}===================")
    return  ChatResponse(message = response["messages"][-1].content,user_id = chat_request.user_id,product_id = chat_request.product_id)



if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=8001,reload=True)