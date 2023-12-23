import pickle

import boto3
from langchain.embeddings import OpenAIEmbeddings
from langchain.vectorstores import FAISS

import dotenv_setting

# DynamoDBからデータを取得
dynamodb = boto3.resource("dynamodb", region_name="ap-northeast-1")
table = dynamodb.Table("ScrapingPhoneStatus")
response = table.scan()
data = response["Items"]

embedding = OpenAIEmbeddings()

# データをベクトル化
with open("vectorstore.pkl", "wb") as f:
    for item in data:
        # 各カラムを一つのテキストとして連結
        item_str = " ".join([f"{key}:{value}" for key, value in item.items()])  
        vector = FAISS.from_texts(item_str, embedding)
        pickle.dump(vector, f)
