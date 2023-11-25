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
        text = " ".join(str(value) for value in item.values())
        vector = FAISS.from_texts(text, embedding)
        pickle.dump(vector, f)
