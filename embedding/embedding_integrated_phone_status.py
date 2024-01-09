import os
import re
import tempfile
from time import sleep
from typing import Final

import boto3
from boto3.dynamodb.conditions import Attr
from config import dotenv_setting  # noqa # api_keyの読み込み
from langchain.chat_models import ChatOpenAI
from langchain.embeddings import OpenAIEmbeddings
from langchain.output_parsers import BooleanOutputParser
from langchain.prompts import PromptTemplate
from langchain.schema import BaseOutputParser, StrOutputParser
from langchain.schema.document import Document
from langchain.vectorstores import FAISS

# S3からダウンロードするファイルの設定
BUCKET_NAME: Final = "vector-store-s3"
TABLE_NAME: Final = "ScrapingPhoneStatus"
BENCHMARK_TABLE_NAME: Final = "Benchmark"
FAISS_FILE_PATH: Final = "index.faiss"
PKL_FILE_PATH: Final = "index.pkl"


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


class Retrieval:
    def __init__(self, table_name: str = BENCHMARK_TABLE_NAME, n_search: int = 4) -> None:
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


class PhoneIdentifier:
    def __init__(
        self,
        phone_name: str,
        model: str,
        output_parser: BaseOutputParser,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> None:
        self.__phone_name = phone_name
        self.__model = ChatOpenAI(model=model, temperature=temperature, max_tokens=max_tokens)
        self.__output_parser = output_parser

    # def extract_phone_name(self, input_str: str) -> str:
    #     # GPTでブランドやメーカー名を除いたスマホの名前を抽出
    #     prompt = PromptTemplate.from_template(
    #         """スマートフォンの名前(phone_name)からブランド名やメーカー名を除いたモデル名を抽出してください。

    #         例:

    #         """
    #     )

    def select_phone(self, benchmark_phone_names: list[str]) -> str:
        # GPTでphone_nameに最も近いbenchmark_phone_nameを選択
        prompt = PromptTemplate.from_template(
            """指定されたスマートフォンのモデル名(phone_name)を元に、与えられたベンチマークモデル名のリスト(benchmark_phone_names)から最も適切なモデル名を選んでください。選択されたモデル名(benchmark_phone_name)のみを回答として提供してください。
            具体的な例を以下に示します。

            例:
            入力されたスマートフォンの名前: Google Pixel 7 256GB SIMフリー
            ベンチマークのモデル名のリスト: ['Google Pixel 7', 'Google Pixel 7 Pro', 'Google Pixel', 'Google Pixel 4a 5G']
            Google Pixel 7

            対象スマートフォンの名前: {phone_name}
            ベンチマークのモデル名のリスト: {benchmark_phone_names}
            """
        )
        chain = prompt | self.__model | self.__output_parser
        selected_phone = chain.invoke(
            {"phone_name": self.__phone_name, "benchmark_phone_names": benchmark_phone_names}
        )
        return selected_phone

    def is_phone_same_model(self, benchmark_phone_name: str) -> bool:
        # GPTで同じ機種かどうかを判定
        prompt = PromptTemplate.from_template(
            """phone_nameとbenchmark_phone_nameが示しているスマートフォンが同一モデルであるか否かを判断し、結果を単純に「YES」か「NO」で回答してください。
            追加の文字や句読点(例えば「YES.」や「NO.」)は使用しないでください。判断は以下のガイドラインに基づいてください:
            - 異なるモデル名の場合それらは別のモデルとして扱います。
            (例: iPhone 13とiPhone 13 Pro、iPhone 13 Pro Max、iPhone 13 Mini、iPhone 12とiPhone 13など)
            - 性能に直接影響しないブランド名やメーカー名の違いは同一モデルとして扱います。
            (例: Asus、Xiaomi、Sonyなどの有無)
            - 英語と日本語でのモデル名表記の違いは無視し、同じモデルとして扱います。
            (例: iPhone SE (第3世代) 128GB SIMフリーとiPhone SE (3rd generation)など)

            phone_name: {phone_name}
            benchmark_phone_name: {benchmark_phone_name}
            """
        )
        chain = prompt | self.__model | self.__output_parser
        is_phone_equal = chain.invoke({"phone_name": self.__phone_name, "benchmark_phone_name": benchmark_phone_name})
        return is_phone_equal


def clean_phone_name(phone_name: str) -> str:
    # スマホの名前からSIMフリー文言とストレージ容量を削除
    phone_name_without_sim = re.sub(r" SIMフリー$", "", phone_name)
    cleaned_phone_name = re.sub(r" \d+GB$| \d+TB$", "", phone_name_without_sim)
    return cleaned_phone_name


def convert_to_dict(input_str: str) -> dict[str, str]:
    result_dict = {}
    # 正規表現でkeyとvalueを取得
    pairs = re.findall(r"([^:|]+):([^|]*)", input_str)
    for key, value in pairs:
        result_dict[key.strip()] = value.strip()
    return result_dict


if __name__ == "__main__":
    answers = []
    accuracy_list = []

    # DynamoDBからデータを取得
    phones_list = DynamoDB(TABLE_NAME).fetch()
    for phone_dict in phones_list:
        phone_name: str | None = phone_dict.get("機種")
        if phone_name is None:
            raise ValueError("DynamoDB ScrapingPhoneStatus: 機種名がありません")
        cleaned_phone_name = clean_phone_name(phone_name)
        print(f"ScrapingPhoneStatus: {cleaned_phone_name}")

        # S3のベンチマークベクトルデータから似た名前のスマホを検索
        retrieval_benchmark = Retrieval()
        benchmark_documents: list[Document] = retrieval_benchmark.retrieve(cleaned_phone_name)

        # スマホの名前を取得
        answer_benchmarks = []
        benchmark_phone_names = []
        for benchmark_document in benchmark_documents:
            benchmark_dict = convert_to_dict(benchmark_document.page_content)
            benchmark_phone_name: str | None = benchmark_dict.get("Name")
            if benchmark_phone_name is None:
                raise ValueError("S3 Benchmark: Nameがありません。")
            answer_benchmarks.append(benchmark_dict)
            benchmark_phone_names.append(benchmark_phone_name)
        print(f"Benchmark S3: {benchmark_phone_names}")

        # GPTでphone_nameに最も近いbenchmark_phone_nameを選択
        benchmark_phone_name = PhoneIdentifier(
            phone_name=cleaned_phone_name, model="gpt-3.5-turbo-1106", output_parser=StrOutputParser()
        ).select_phone(benchmark_phone_names)
        print(f"選択された機種: {benchmark_phone_name}")
        # GPTで同じ機種かどうかを判定
        is_phone_equal = PhoneIdentifier(
            phone_name=cleaned_phone_name, model="gpt-4-1106-preview", output_parser=BooleanOutputParser()
        ).is_phone_same_model(benchmark_phone_name)
        sleep(3)  # gpt-4の1分あたり10,000トークンのレート制限の回避
        accuracy_list.append(is_phone_equal)
        print(f"同じ機種かどうか: {is_phone_equal}")
        if is_phone_equal:
            # IndexError: list index out of range
            benchmark_dicts: dict[str, str] = DynamoDB(BENCHMARK_TABLE_NAME).fetch(benchmark_phone_name)
            print(f"Benchmark DB: {benchmark_dicts}")
            benchmark_dict = benchmark_dicts[0]
            print("---------------------------------------------------")
            answer_dict = phone_dict | benchmark_dict
            answers.append(answer_dict)
        else:
            print("---------------------------------------------------")
            answers.append(phone_dict)

    # 統合したデータをembedding
    embedding = OpenAIEmbeddings()
    answers = ["".join(f"{key}:{value} | " for key, value in answer_dict.items()) for answer_dict in answers]
    vector_store = FAISS.from_texts(answers, embedding)
    vector_store.save_local("IntegratedPhoneStatus")
    print(f"正答率: {(accuracy_list.count(True) / len(accuracy_list)) * 100}%")
