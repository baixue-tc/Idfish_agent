# 创建hash函数
import hashlib
from pathlib import Path
import os
import json
def get_file_hash(file_path):
    """计算文件hash值"""
    md5 = hashlib.md5()
    with open(file_path,'rb') as f:
        while chunk := f.read(8192):
            md5.update(chunk)

    return md5.hexdigest()

def load_index(version_path):
    """当前索引对应的数据版本"""
    path = Path(version_path)
    if not os.path.exists(path):
        return None
    with open(path,'r',encoding= "utf-8") as f:
        data = json.load(f)
    return data.get("file_hash")

def save_index(version_path,file_hash):
    """保存当前文件hash索引"""
    path = Path(version_path)
    path.parent.mkdir(parents=True,exist_ok = True)
    with open(path,'w',encoding= "utf-8") as f:
        json.dump({"file_hash":file_hash},
                  f,
                  ensure_ascii = False,
                  indent = 4)

def index_is_latest(file_path,version_path):
    current_filehash = get_file_hash(file_path)
    before_filehash = load_index(version_path)
    return current_filehash == before_filehash