import pandas as pd
from langchain_core.documents import Document

def prepare_document(filepath):
    df = pd.read_excel(filepath,header = None)
    """准备商品知识库"""
    document = []
    product_name = None
    header = None
    product_data = []
    after_sales = []
    for _, row in df.iterrows():
        values = row.dropna().tolist()
        if not values:
            continue
        # 产品名和售后
        if len(values) == 1 and not any(str(values[0]).startswith(i) for i in ["质保","运费险","是否包邮"]):
            product_name = str(values[0])
            after_sales = []
            product_data = []
            header = None
            continue
        # 表头
        if any(key in values for key in ["型号","最低价格","价格"]):
            header = values
            continue
        # 商品信息及售后
        if header:
            if any(str(v).startswith(("质保","运费险","是否包邮")) for v in values):
                after_sales.append(str(values[0]))
            else:
                data = dict(zip(header, values))
                product_data.append(data)
                continue

        # 售后
        if len(after_sales) == 3 :
            for data in product_data:
                content = []
                content.append(f"商品名称{product_name}")
                for k, v in data.items():
                    content.append(f"{k}:{v}")
                content.extend(after_sales)
                document.append(Document(page_content = ",".join(content),metadata = {"doc_id":str(len(document)+1),"product_name":product_name,"model":data["型号"],"price":data["价格"],"lowest_price":data["最低价格"]}))
    return document