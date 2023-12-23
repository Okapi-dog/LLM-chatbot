import os
import re
import tempfile
from typing import Final

import boto3
from config import dotenv_setting  # api_keyの読み込み
from langchain.chains import RetrievalQA
from langchain.chat_models import ChatOpenAI
from langchain.embeddings import OpenAIEmbeddings
from langchain.vectorstores import FAISS

# S3からダウンロードするファイルの設定
BUCKET_NAME: Final = "vector-store-s3"
FAISS_FILE_PATH: Final = "index.faiss"
PKL_FILE_PATH: Final = "index.pkl"


class Retrieval:
    def __init__(self) -> None:
        # boto3 S3クライアントの作成
        s3 = boto3.client("s3")

        # 一時ディレクトリの作成
        with tempfile.TemporaryDirectory() as tmp_dir:
            # S3からファイルをダウンロード
            s3.download_file(BUCKET_NAME, FAISS_FILE_PATH, os.path.join(tmp_dir, FAISS_FILE_PATH))
            s3.download_file(BUCKET_NAME, PKL_FILE_PATH, os.path.join(tmp_dir, PKL_FILE_PATH))
            # FAISSインデックスのロード
            embedding = OpenAIEmbeddings()
            self.vector_store = FAISS.load_local(tmp_dir, embedding)
        self.retriever = self.vector_store.as_retriever(search_kwargs={"k": 3})

    def retrieve(self, query: str) -> dict[str, str]:  # 情報を検索して返す
        docs = self.retriever.get_relevant_documents(query)
        return docs
        # pprint(docs)
        # print("---------------------------------------------------")

        # llm = ChatOpenAI(temperature=0, model_name="gpt-3.5-turbo")
        # qa = RetrievalQA.from_chain_type(llm=llm, retriever=self.retriever)
        # answer = qa(query)
        # return answer


def convert_to_dict(input_str: str) -> dict[str, str]:
    result_dict = {}
    pairs = re.findall(r"([^:|]+):([^|]*)", input_str)
    for pair in pairs:
        if pair[1].strip():
            key, value = pair
            result_dict[key.strip()] = value.strip()
    return result_dict


if __name__ == "__main__":
    query = "iPhone 12 Pro Maxに近いスペックのスマートフォンについて教えてください"

    retrieval = Retrieval()
    answers = retrieval.retrieve(query)

    answer_list = [
        convert_to_dict(answer.page_content) for answer in answers
    ]  # Document型のリストをdict型のリストに変換
    phone_list = [answer["機種"] for answer in answer_list]

    print("---------------------------------------------------")
    print(phone_list)
