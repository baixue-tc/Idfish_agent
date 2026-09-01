from langchain.tools import tool
from .prompt import RAG_AGENT_PROMPT
from dotenv import load_dotenv
from langchain.tools import ToolRuntime
from langchain.agents import create_agent
from rag.retriever import search
from cache.cache import set_cache,get_cache
from agent.context import IdlefishContext
import logging

load_dotenv()

logger = logging.getLogger(__name__)

@tool
def search_knowledge_base(query:str,runtime:ToolRuntime[IdlefishContext]):
    """用于知识库检索"""
    # 查询缓存
    cached_key = f"rag:{runtime.context.product_id},{query}"
    cached = get_cache(cached_key)
    if cached:
        logger.info(f"缓存命中{cached_key}")
        return cached
    # 检索文档
    docs = search(f"产品名称:{runtime.context.product_id},{query}")
    if not docs:
        return "没有找到相关文档"
    # 拼接文档
    results = "\n\n".join([doc["content"] for doc in docs])
    # 保存缓存
    set_cache(cached_key,results,ttl = 600)
    logger.info("缓存未命中,保存缓存")
    return results
@tool
def to_human():
    """将当前会话转为人工处理"""
    return "需要人工处理"

rag_agent = create_agent(model = "deepseek-v4-flash",
                         tools = [search_knowledge_base,to_human,],
                         system_prompt = RAG_AGENT_PROMPT
                         )