import os
import re
import tempfile
from typing import Final

import boto3
from boto3.dynamodb.conditions import Attr
from config import dotenv_setting  # noqa # api_keyの読み込み
from langchain.chat_models import ChatOpenAI
from langchain.embeddings import OpenAIEmbeddings
from langchain.output_parsers import BooleanOutputParser
from langchain.prompts import PromptTemplate
from langchain.schema.document import Document
from langchain.vectorstores import FAISS

# S3からダウンロードするファイルの設定
BUCKET_NAME: Final = "vector-store-s3"
TABLE_NAME: Final = "ScrapingPhoneStatus"
BENCHMARK_TABLE_NAME: Final = "Benchmark"
FAISS_FILE_PATH: Final = "index.faiss"
PKL_FILE_PATH: Final = "index.pkl"


class Retrieval:
    def __init__(self, table_name: str = TABLE_NAME, n_search: int = 4) -> None:
        # boto3 S3クライアントの作成
        self.__s3 = boto3.client("s3")
        self.__n_search = n_search
        self.__table_name = table_name

        # 一時ディレクトリの作成
        with tempfile.TemporaryDirectory() as tmp_dir:
            # S3からファイルをダウンロード
            self.__s3.download_file(
                BUCKET_NAME, os.path.join(self.__table_name, FAISS_FILE_PATH), os.path.join(tmp_dir, FAISS_FILE_PATH)
            )
            self.__s3.download_file(
                BUCKET_NAME, os.path.join(self.__table_name, PKL_FILE_PATH), os.path.join(tmp_dir, PKL_FILE_PATH)
            )
            embedding = OpenAIEmbeddings()
            # FAISSインデックスのロード
            self.__vector_store = FAISS.load_local(tmp_dir, embedding)
        # 検索エンジンの設定
        self.__retriever = self.__vector_store.as_retriever(search_kwargs={"k": self.__n_search})

    def retrieve(self, query: str) -> dict[str, str]:
        return self.__retriever.get_relevant_documents(query)


class DynamoDB:
    def __init__(self, table_name: str) -> None:
        self.__dynamodb = boto3.resource("dynamodb", region_name="ap-northeast-1")
        self.__table = self.__dynamodb.Table(table_name)
        self.__column_name = "Name" if table_name == BENCHMARK_TABLE_NAME else "機種"

    def fetch(self, phone_name: str | None = None) -> list[dict[str, str]]:
        # DynamoDBから全データまたはphone_nameに合致するデータを取得
        if phone_name is None:
            return self.__table.scan()["Items"]
        return self.__table.scan(FilterExpression=Attr(self.__column_name).eq(phone_name))["Items"]


def convert_to_dict(input_str: str) -> dict[str, str]:
    result_dict = {}
    # 正規表現でkeyとvalueを取得
    pairs = re.findall(r"([^:|]+):([^|]*)", input_str)
    for pair in pairs:
        # 値が空文字列でない場合のみ辞書に追加することで不要な情報を削除("撥水": ""など)
        if pair[1].strip():
            key, value = pair
            result_dict[key.strip()] = value.strip()
    return result_dict


def is_phone_same_model(phone_name: str, benchmark_phone_name: str) -> bool:
    # GPTで同じ機種かどうかを判定
    prompt = PromptTemplate.from_template(
        """phone_nameとbenchmark_phone_nameが同じ機種を指しているかを判定してYESかNOのみを返してください。容量やSIMの有無は関係ありません。
        phone_name: {phone_name}
        benchmark_phone_name: {benchmark_phone_name}
        """
    )
    model = ChatOpenAI(model="gpt-3.5-turbo-1106", temperature=0)
    output_parser = BooleanOutputParser()
    chain = prompt | model | output_parser
    is_equal_to_phone = chain.invoke({"phone_name": phone_name, "benchmark_phone_name": benchmark_phone_name})
    return is_equal_to_phone


if __name__ == "__main__":
    answers = []
    phones_list = DynamoDB(TABLE_NAME).fetch()

    for phone_dict in phones_list:
        phone_name = phone_dict.get("機種")
        if phone_name is None:
            raise ValueError("DynamoDB ScrapingPhoneStatus: 機種名がありません。")
        print(f"ScrapingPhoneStatus: {phone_name}")

        retrieval_benchmark = Retrieval(table_name=BENCHMARK_TABLE_NAME, n_search=1)
        answer_benchmark: Document = retrieval_benchmark.retrieve(phone_name)[0]  # phone_nameと同じ機種を検索
        answer_benchmark_dict = convert_to_dict(answer_benchmark.page_content)
        benchmark_phone_name = answer_benchmark_dict.get("Name")
        if benchmark_phone_name is None:
            raise ValueError("S3 Benchmark: Nameがありません。")
        print(f"Benchmark S3: {benchmark_phone_name}")

        is_phone_equal = is_phone_same_model(phone_name, benchmark_phone_name)  # GPTで同じ機種かどうか判定
        print(f"同じ機種かどうか: {is_phone_equal}")
        if is_phone_equal:
            benchmark_dict: dict[str, str] = DynamoDB(BENCHMARK_TABLE_NAME).fetch(benchmark_phone_name)[0]
            print(f"Benchmark DB: {benchmark_dict}")
            print("---------------------------------------------------")
            answer_dict = phone_dict | benchmark_dict
            answers.append(answer_dict)
        else:
            print("---------------------------------------------------")
            answers.append(phone_dict)

    # 統合したデータをembedding
    embedding = OpenAIEmbeddings()
    answers = ["".join(f"{key}:{value} | " for key, value in answer_dict.items()) for answer_dict in answers]
    print(f"embedding answers: {answers}")
    vector_store = FAISS.from_texts(answers, embedding)
    vector_store.save_local("IntegratedPhoneStatus")
