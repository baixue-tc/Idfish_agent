from sentence_transformers import CrossEncoder
from typing import List
from langchain.chat_models import init_chat_model
import os
from .index import vectorstore,bm25_retriever
from pkuseg import pkuseg
import logging
logger = logging.getLogger(__name__)

seg = pkuseg()
def bm25_search(query:str,k:int = 5 ):
    """bm25检索"""
    token = [seg.cut(query)]
    results,scores = bm25_retriever.retrieve(token,k = k)
    return [results[0,i] for i in range(results.shape[1])]


def rrf_search(ranked_list, k:float = 60):
    """rrf混合检索"""
    rrf_score = {}
    results = {}
    for rank_list in ranked_list:
        for rank,doc in enumerate(rank_list,start = 1):
            doc_id = doc["metadata"]["doc_id"]
            rrf_score[doc_id] = rrf_score.get(doc_id,0) + 1 / (rank + k)
            results[doc_id] = doc
    sorted_docs = sorted(rrf_score.items(),key = lambda x : x[1],reverse = True )
    return [results[doc_id] for doc_id,score in sorted_docs]


ce_model = CrossEncoder("Qwen/Qwen3-Reranker-0.6B",device = "cuda")
def cross_encoder(query,docs:List[dict],top_k:int = 3 ):
    """
    封装的cross_encoder重排器
    :param query:问题
    :param docs: rrf检索文档
    :param top_k: 重排后返回的文档数量
    :return: 重排后的文档
    """
    scores = ce_model.predict([[query,doc["content"]] for doc in docs])
    for i,s in enumerate(scores):
        docs[i]['score'] = s
    sorted_docs = sorted(docs,key = lambda x : x['score'],reverse = True)
    positive_docs = [doc for doc in sorted_docs if doc['score'] > 0 ]
    return positive_docs[:min(top_k,len(positive_docs))]



rewrite_model = init_chat_model(model = "qwen3.8-max",
                        model_provider = "openai",
                        api_key = os.getenv("DASHSCOPE_API_KEY"),
                        base_url = os.getenv("DASHSCOPE_BASE_URL"))

def search(query):
    # 查询优化
    rewrite_prompt = f"""请将下面的问题重写为更利于检索的关键词,要求:抓取问题核心概念并用空格分隔,禁止添加任何解释,直接返回关键字

                                            问题:{query}

                                            关键字:
                                            """
    logger.info(f"原始问题:{query}->优化后问题:{rewrite_prompt}")

    rewrite_query = rewrite_model.invoke(rewrite_prompt).content

    # 向量库检索
    vector_docs = vectorstore.similarity_search(rewrite_query, k=5)

    # bm25检索
    bm25_docs = bm25_search(rewrite_query, k=5)
    # 整理文件
    vector_ds = [{"metadata": doc.metadata, "content": doc.page_content} for doc in vector_docs]
    bm25_ds = [doc for doc in bm25_docs]

    # 混合检索
    rrf_docs = rrf_search([vector_ds, bm25_ds])

    # 重排
    rerank_doc = cross_encoder(rewrite_query, rrf_docs, 3)
    return rerank_doc