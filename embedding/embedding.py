from typing import Final

import boto3
from config import dotenv_setting  # api_keyの読み込み
from langchain.embeddings import OpenAIEmbeddings
from langchain.vectorstores import FAISS

BUCKET_NAME: Final = "vector-store-s3"
TABLE_NAME: Final = "ScrapingPhoneStatus"


if __name__ == "__main__":
    # boto3 S3クライアントとDynamoDBリソースの作成
    dynamodb = boto3.resource("dynamodb", region_name="ap-northeast-1")
    s3 = boto3.client("s3")

    # DynamoDBからテキストデータを取得
    table = dynamodb.Table(TABLE_NAME)
    response = table.scan()
    items = response["Items"]

    # OpenAIEmbeddingsのインスタンスを作成
    embedding = OpenAIEmbeddings()

    item_str = [" ".join(f"{key}:{value}" for key, value in item.items()) for item in items]
    vector_store = FAISS.from_texts(item_str, embedding)
    # バイトデータを保存
    vector_store.save_local("faiss")
