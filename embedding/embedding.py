import pickle
import re
from typing import Final

import boto3
from boto3.dynamodb.conditions import Attr
from config import dotenv_setting  # noqa # api_keyの読み込み
from langchain.embeddings import OpenAIEmbeddings
from langchain.vectorstores import FAISS

BUCKET_NAME: Final = "vector-store-s3"
TABLE_NAME: Final = "Benchmark"  # Benchmarkデータをembeddingしたい場合はBenchmarkに変更
PICKLE_FILE_PATH: Final = "integrated_phone_status.pickle"


class DynamoDB:
    def __init__(self, table_name: str) -> None:
        self.__dynamodb = boto3.resource("dynamodb", region_name="ap-northeast-1")
        self.__table = self.__dynamodb.Table(table_name)

    def fetch(self, phone_name: str | None = None) -> list[dict[str, str]]:
        # DynamoDBから全データまたはphone_nameに合致するデータを取得
        if phone_name is None:
            return self.__table.scan()["Items"]
        return self.__table.scan(FilterExpression=Attr("機種").eq(phone_name))["Items"]


def format_for_embedding(key: str, value: str) -> str:
    # 値が空文字列のペアは除外、キーが機種の場合はSIMフリーを省略
    if not value:
        return ""
    if key == "機種":
        formatted_value = re.sub(r" SIMフリー$", "", value)
        return f"{key}:{formatted_value} | "
    return f"{key}:{value} | "


if __name__ == "__main__":
    phones = DynamoDB(TABLE_NAME).fetch()
    # 統合データのembeddingの場合はこちら
    # with open(PICKLE_FILE_PATH, "rb") as f:
    #     phones: list[dict[str, str]] = pickle.load(f)

    answers = ["".join(format_for_embedding(key, value) for key, value in phone_dict.items()) for phone_dict in phones]
    embedding = OpenAIEmbeddings()
    vector_store = FAISS.from_texts(answers, embedding)
    # バイトデータを保存
    vector_store.save_local(TABLE_NAME)
