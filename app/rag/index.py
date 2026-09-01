from langchain_core.documents import Document
from .loader import prepare_document
from pkuseg import pkuseg
from langchain_chroma import Chroma
from langchain_community.embeddings import DashScopeEmbeddings
from dotenv import load_dotenv
import bm25s
from .version import *
from pathlib import Path
import logging
logger = logging.getLogger(__name__)

load_dotenv()
# 读取Excel文件
BASE_DIR = Path(__file__).resolve().parents[2]
VECTOR_PATH = BASE_DIR / "db/chroma_stroe"
BM25_PATH = BASE_DIR / "db/bm25_index"
FILE_PATH = BASE_DIR / "resources/产品.xlsx"
VECTOR_VERSION_PATH = BASE_DIR / "db/vector_version.json"
BM25_VERSION_PATH = BASE_DIR / "db/bm25_version.json"
documents = prepare_document(FILE_PATH)
class DataBase:
    def __init__(self,vector_path,bm25_path,file_path):
        self.seg = pkuseg()
        self.bm25_path = bm25_path
        self.vector_path = vector_path
        self.file_path = file_path
        self.embedding_model =  DashScopeEmbeddings(model = "qwen3.7-text-embedding",
                                            dashscope_api_key = os.getenv("DASHSCOPE_API_KEY"))
        self.vectorstore =  Chroma(collection_name = "idlefish",
                             embedding_function = self.embedding_model,
                             persist_directory = vector_path)
    def create_vectorstore(self,docs:list[Document]):
        """创建向量库"""
        if not index_is_latest(self.file_path,VECTOR_VERSION_PATH):
            logger.info("向量库需要更新,开始更新...")
            date = self.vectorstore.get()
            if date["ids"]:
                self.vectorstore.delete(ids = date["ids"])
            batch_size = 20
            for i in range(0, len(docs), batch_size):
                batch_docs = docs[i:i+batch_size]
                self.vectorstore.add_documents(batch_docs,ids = [doc.metadata["doc_id"] for doc in batch_docs])
            file_hash = get_file_hash(self.file_path)
            save_index(VECTOR_VERSION_PATH,file_hash)
        else:
            logger.info("正在加载向量库...")
        return self.vectorstore

    def create_bm25_index(self,metadata_corpus,k1:float = 1.5,b:float = 0.75):
        """创建bm25索引库"""
        if index_is_latest(self.file_path,BM25_VERSION_PATH):
            logger.info("已有bm25索引库正在加载...")
            _retriever = bm25s.BM25.load(self.bm25_path,load_corpus = True)
        else:
            logger.info("bm25索引库需要更新,开始更新...")
            metadata_token = [self.seg.cut(doc["content"]) for doc in metadata_corpus]
            _retriever = bm25s.BM25(k1 = k1,b = b,corpus = metadata_corpus)
            _retriever.index(metadata_token)
            _retriever.save(self.bm25_path)
            file_hash = get_file_hash(self.file_path)
            save_index(BM25_VERSION_PATH,file_hash)
        return _retriever




db = DataBase(VECTOR_PATH,BM25_PATH,FILE_PATH)
# 向量库
vectorstore = db.create_vectorstore(documents)
# bm25索引库
metadata_corpus = [{"metadata":doc.metadata,"content":doc.page_content} for doc in documents]
bm25_retriever = db.create_bm25_index(metadata_corpus)