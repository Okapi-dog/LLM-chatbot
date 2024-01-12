import os
import re
import tempfile
from time import sleep
from typing import Final

import boto3
from boto3.dynamodb.conditions import Attr
from config import dotenv_setting  # noqa # api_keyの読み込み
from langchain.output_parsers import BooleanOutputParser
from langchain.prompts import PromptTemplate
from langchain.schema import BaseOutputParser, StrOutputParser
from langchain.schema.document import Document
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings
from langchain_openai.chat_models import ChatOpenAI

# S3からダウンロードするファイルの設定
BUCKET_NAME: Final = "vector-store-s3"
TABLE_NAME: Final = "ScrapingPhoneStatus"
BENCHMARK_TABLE_NAME: Final = "Benchmark"
FAISS_FILE_PATH: Final = "index.faiss"
PKL_FILE_PATH: Final = "index.pkl"


class DynamoDB:
    """DynamoDBからデータを取得するクラス"""

    __slots__ = ["__dynamodb", "__table", "__phone_column_name", "__cpu_column_name"]

    def __init__(self, table_name: str) -> None:
        self.__dynamodb = boto3.resource("dynamodb", region_name="ap-northeast-1")
        self.__table = self.__dynamodb.Table(table_name)
        self.__phone_column_name = "Name" if table_name == BENCHMARK_TABLE_NAME else "機種"
        self.__cpu_column_name = "Processor" if table_name == BENCHMARK_TABLE_NAME else "CPU"

    def fetch_all(self) -> list[dict[str, str]]:
        # DynamoDBから全データを取得
        benchmark_dicts = self.__table.scan()["Items"]
        if not benchmark_dicts:
            raise ValueError("DynamoDB ScrapingPhoneStatus: データがありません")
        return benchmark_dicts

    def fetch_by_name(self, phone_name: str) -> list[dict[str, str]]:
        # phone_nameに合致するデータを取得
        benchmark_dicts = self.__table.scan(FilterExpression=Attr(self.__phone_column_name).eq(phone_name))["Items"]
        if not benchmark_dicts:
            raise ValueError("DynamoDB ScrapingPhoneStatus: データがありません")
        return benchmark_dicts

    def fetch_by_contained_cpu(self, cpu: str) -> list[dict[str, str]]:
        # cpuが含まれるデータを取得
        return self.__table.scan(FilterExpression=Attr(self.__cpu_column_name).contains(cpu))["Items"]


class Retrieval:
    """S3からベンチマークデータを取得するクラス"""

    __slots__ = ["__s3", "__n_search", "__table_name", "__vector_store", "__retriever"]

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

    def retrieve(self, query: str) -> list[dict[str, str]]:
        # S3からベンチマークデータを取得して辞書型に変換
        benchmark_documents: list[Document] = self.__retriever.get_relevant_documents(query)
        return [convert_to_dict(benchmark_document.page_content) for benchmark_document in benchmark_documents]


def convert_to_dict(input_str: str) -> dict[str, str]:
    result_dict = {}
    # 正規表現でkeyとvalueを取得
    pairs = re.findall(r"([^:|]+):([^|]*)", input_str)
    for key, value in pairs:
        result_dict[key.strip()] = value.strip()
    return result_dict


class PhoneIdentifier:
    """スマホの名前を特定するクラス"""

    __slots__ = ["__phone_name", "__model", "__output_parser"]

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

    def select_phone(self, benchmark_phone_names: list[str]) -> str:
        # GPTでphone_nameに最も近いbenchmark_phone_nameを選択
        prompt = PromptTemplate.from_template(
            """以下のリストから、指定されたスマートフォンモデル({phone_name})に最も近いスマートフォンモデル名を選択してください。選択したモデル名のみを回答として提供してください。

            スマートフォンモデル名のリスト: {benchmark_phone_names}

            例:
            スマートフォンモデル: OPPO Reno9 A
            スマートフォンモデル名のリスト: ['Oppo Reno 10x Zoom', 'Oppo Reno', 'Oppo Reno2', 'Oppo Reno Z']
            回答: Oppo Reno2
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


def clean_snapdragon_cpu(snapdragon_cpu: str) -> str:
    # Snapdragon XXXの部分を抽出
    cleaned_snapdragon_cpu: re.Match[str] | None = re.search(r"(Snapdragon \d+[G\+]*\+?)", snapdragon_cpu)
    if cleaned_snapdragon_cpu is None:
        raise ValueError("DynamoDB ScrapingPhoneStatus: SnapdragonのCPU名がありません")
    return cleaned_snapdragon_cpu.group(1)


def integrate_phone_dict(
    benchmark_dict: dict[str, str], phone_dict: dict[str, str], answers: list[dict[str, str]]
) -> None:
    benchmark_dict_cp = benchmark_dict.copy()
    del benchmark_dict_cp["Name"]
    del benchmark_dict_cp["Processor"]
    answer_dict = phone_dict | benchmark_dict_cp
    answers.append(answer_dict)


if __name__ == "__main__":
    scraping_phone_status_db = DynamoDB(TABLE_NAME)
    benchmark_db = DynamoDB(BENCHMARK_TABLE_NAME)
    # answers: 統合後のデータ, match_list: benchmarkがマッチしたかどうか
    answers: list[dict[str, str]] = []
    match_list: list[bool] = []

    # DynamoDBからデータを取得
    phones: list[dict[str, str]] = scraping_phone_status_db.fetch_all()

    for phone_dict in phones:
        # phone_nameの取得
        phone_name: str | None = phone_dict.get("機種")
        if phone_name is None:
            raise ValueError("DynamoDB ScrapingPhoneStatus: 機種名がありません")
        cleaned_phone_name = clean_phone_name(phone_name)
        print(f"No.{len(answers)+1}: {cleaned_phone_name}")

        # S3のベンチマークベクトルデータから似た名前のスマホを複数個取得
        retrieval_benchmark = Retrieval()
        benchmarks: list[dict[str, str]] = retrieval_benchmark.retrieve(cleaned_phone_name)
        benchmark_phone_names: list[str] = [benchmark_dict["Name"] for benchmark_dict in benchmarks]

        # benchmark_phone_namesの中にcleaned_phone_nameがあればGPTを経由せずに統合してスキップ
        if cleaned_phone_name in benchmark_phone_names:
            print(f"    同名: {cleaned_phone_name}")
            # マッチ率の計算用
            match_list.append(True)
            benchmark_dicts = benchmark_db.fetch_by_name(cleaned_phone_name)
            integrate_phone_dict(benchmark_dicts[0], phone_dict, answers)
            print("\n---------------------------------------------------\n")
            continue

        # GPTでphone_nameに最も近いbenchmark_phone_nameを選択
        benchmark_phone_name = PhoneIdentifier(
            phone_name=cleaned_phone_name, model="gpt-4-1106-preview", output_parser=StrOutputParser()
        ).select_phone(benchmark_phone_names)
        print(f"    類似: {benchmark_phone_name}")

        # GPTで同じ機種かどうかを判定
        is_phone_equal = PhoneIdentifier(
            phone_name=cleaned_phone_name, model="gpt-4-1106-preview", output_parser=BooleanOutputParser()
        ).is_phone_same_model(benchmark_phone_name)
        # GPT-4の1分あたり10,000トークンのレート制限回避
        sleep(5)
        print(f"    GPTによる同一判定: {is_phone_equal}")

        # 同一の場合統合
        if is_phone_equal:
            benchmark_dicts = benchmark_db.fetch_by_name(benchmark_phone_name)
            integrate_phone_dict(benchmark_dicts[0], phone_dict, answers)
            # マッチ率の計算用
            match_list.append(True)
            print("\n---------------------------------------------------\n")
            continue

        # 同名でない場合、CPUで統合を試みる
        # phone_cpuの取得
        print()
        phone_cpu: str | None = phone_dict.get("CPU")
        if phone_cpu is None:
            raise ValueError("DynamoDB ScrapingPhoneStatus: CPUがありません")

        if "Snapdragon" in phone_cpu:
            # Snapdragon XXXの部分を抽出
            phone_cpu = clean_snapdragon_cpu(phone_cpu)

        # DynamoDBからphone_cpuが含まれるデータを取得
        print(f"    CPU: {phone_cpu}")
        benchmark_dicts: list[dict[str, str]] = benchmark_db.fetch_by_contained_cpu(phone_cpu)

        # 同CPUのスマホがあれば統合
        if benchmark_dicts:
            integrate_phone_dict(benchmark_dicts[0], phone_dict, answers)
            # マッチ率の計算用
            match_list.append(True)
            print(f"    同CPU: {phone_cpu}")
            print("\n---------------------------------------------------\n")
            continue

        # 同じCPUのスマホがない場合、そのまま追加してマッチ率を下げる
        answers.append(phone_dict)
        match_list.append(False)
        print("    同CPU: なし")
        print("\n---------------------------------------------------\n")
        continue

    # 統合したデータをembedding
    embedding = OpenAIEmbeddings()
    answers = ["".join(f"{key}:{value} | " for key, value in answer_dict.items()) for answer_dict in answers]
    vector_store = FAISS.from_texts(answers, embedding)
    vector_store.save_local("IntegratedPhoneStatus")
    print(f"マッチ率: {(match_list.count(True) / len(match_list)) * 100}%")
    # CPU同一判定実装前のマッチ率: 57.89473684210527%
    # CPU同一判定実装後のマッチ率: 63.33333333333333%
    # SnapdragonCPUキャッチ実装後のマッチ率: 77.44360902255639%
    # DynamoDBのcontain scan実装後のマッチ率: 92.4812030075188%
