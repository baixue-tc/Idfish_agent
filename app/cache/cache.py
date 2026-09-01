import redis
import os
from dotenv import load_dotenv

load_dotenv()
redis_client = redis.Redis(
    host = os.getenv("HOST", "localhost"),
    port = int(os.getenv("REDIS_PORT", 6379)),
    decode_responses = True
)

def set_cache(key:str,value:str,ttl:int):
    "保存缓存"
    redis_client.set(key,value,ttl)

def get_cache(key:str):
    "获取缓存"
    return redis_client.get(key)

def delete_cache(key:str):
    "删除缓存"
    redis_client.delete(key)
