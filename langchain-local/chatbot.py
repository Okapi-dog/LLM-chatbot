import asyncio
import os
import re
import tempfile
from time import time
from typing import Final

import boto3
from config import dotenv_setting  # api_keyの読み込み
from langchain.chat_models import ChatOpenAI
from langchain.embeddings import OpenAIEmbeddings
from langchain.prompts import PromptTemplate
from langchain.schema import StrOutputParser
from langchain.schema.document import Document
from langchain.vectorstores import FAISS

# S3からダウンロードするファイルの設定
BUCKET_NAME: Final = "vector-store-s3"
FAISS_FILE_PATH: Final = "index.faiss"
PKL_FILE_PATH: Final = "index.pkl"


class Retrieval:
    def __init__(self, n_search: int = 4) -> None:
        # boto3 S3クライアントの作成
        self.__s3 = boto3.client("s3")
        self.__n_search = n_search

        # 一時ディレクトリの作成
        with tempfile.TemporaryDirectory() as tmp_dir:
            # S3からファイルをダウンロード
            self.__s3.download_file(BUCKET_NAME, FAISS_FILE_PATH, os.path.join(tmp_dir, FAISS_FILE_PATH))
            self.__s3.download_file(BUCKET_NAME, PKL_FILE_PATH, os.path.join(tmp_dir, PKL_FILE_PATH))
            embedding = OpenAIEmbeddings()
            # FAISSインデックスのロード
            self.__vector_store = FAISS.load_local(tmp_dir, embedding)
        # 検索エンジンの設定
        self.__retriever = self.__vector_store.as_retriever(search_kwargs={"k": self.__n_search})

    def retrieve(self, query: str) -> dict[str, str]:
        docs = self.__retriever.get_relevant_documents(query)
        return docs
        # pprint(docs)
        # print("---------------------------------------------------")
        # llm = ChatOpenAI(temperature=0, model_name="gpt-3.5-turbo")
        # qa = RetrievalQA.from_chain_type(llm=llm, retriever=self.retriever)
        # answer = qa(query)
        # return answer


async def convert_to_dict(input_str: str) -> dict[str, str]:
    result_dict = {}
    pairs = re.findall(r"([^:|]+):([^|]*)", input_str)
    for pair in pairs:
        if pair[1].strip():
            key, value = pair
            result_dict[key.strip()] = value.strip()
    return result_dict


async def generate_recommendations(request: str, answer_dict: dict[str, str]) -> list[str]:
    prompt = PromptTemplate.from_template(
        """以下のrequestに基づいたおすすめのスマートフォンの情報がanswer_dictに格納されています。answer_dictの情報を基に、requestでユーザーが求める点を中心に推薦文を20字以内で3つ生成してください。推薦文に1.などは必要ありません。
        例は以下の通りです。例は要件に含めないでください。

        例:
            request: OSのサポート期間が長く、iPhone 11 Proに近い重さで、原神を快適にプレイできるスマートフォンを教えてください。
            answer_dict: "機種": "iPhone 12 Pro Max",
                         "サイズ": "6.7インチ",
                         "価格": "150000円",
                         "CPU": "A14 Bionic",
                         "メモリ": "6GB",
                         "ストレージ": "256GB",
                         "バッテリー": "3687mAh",
                         "カメラ": "トリプルカメラ",
                         "画面": "有機EL",
                         "解像度": "2778x1284",
                         "重さ": "226g",
                         "OS": "iOS 14",
                         "その他": "防水防塵"
            response: OSのサポート期間がiOSのため長い
                      iPhone 11 Proに近い重さの226g
                      原神の快適なプレイが可能なCPU
        例の終わり

        request: {request}
        answer_dict: {answer_dict}
        response:
        """,
    )
    model = ChatOpenAI(model="gpt-3.5-turbo-1106", temperature=0)
    output_parser = StrOutputParser()
    chain = prompt | model | output_parser
    recommendations = await chain.ainvoke({"request": request, "answer_dict": answer_dict})
    recommendations = [recommendation.strip() for recommendation in recommendations.split("\n", 2)]
    return recommendations


async def process_answers(request: str, answers: list[Document]) -> list[dict[str, str]]:
    answer_dicts = await asyncio.gather(*[convert_to_dict(answer.page_content) for answer in answers])
    responses = await asyncio.gather(*[generate_recommendations(request, answer_dict) for answer_dict in answer_dicts])
    return responses


if __name__ == "__main__":
    start_time = time()

    query = "撥水性があり、カメラの性能が良く、iPhone 12 Pro Maxに近いスペックのスマートフォンについて教えてください"
    retrival = Retrieval()
    answers = retrival.retrieve(query)
    responses = asyncio.run(process_answers(query, answers))

    end_time = time()
    print(f"処理時間: {end_time - start_time}秒")
    print("---------------------------------------------------")
    print(responses)
