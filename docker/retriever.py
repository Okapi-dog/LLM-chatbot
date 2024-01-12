import os
import tempfile
from typing import Final
import sys

import boto3
#from config import dotenv_setting  # api_keyの読み込み
from langchain.chains import RetrievalQA
#from langchain.chat_models import ChatOpenAI
from langchain_community.chat_models import ChatOpenAI
#from langchain.embeddings import OpenAIEmbeddings
from langchain_community.embeddings import OpenAIEmbeddings
#from langchain.vectorstores import FAISS
from langchain_community.vectorstores.faiss import FAISS

# S3からダウンロードするファイルの設定
BUCKET_NAME: Final = "vector-store-s3"
TABLE_NAME: Final = "ScrapingPhoneStatus"
FAISS_FILE_PATH: Final = "index.faiss"
PKL_FILE_PATH: Final = "index.pkl"

class Retrieval():
    def __init__(self):
        # boto3 S3クライアントの作成
        s3 = boto3.client("s3")

        # 一時ディレクトリの作成
        with tempfile.TemporaryDirectory() as tmp_dir:
            # S3からファイルをダウンロード
            s3.download_file(BUCKET_NAME, os.path.join(TABLE_NAME,FAISS_FILE_PATH), os.path.join(tmp_dir, FAISS_FILE_PATH))
            s3.download_file(BUCKET_NAME, os.path.join(TABLE_NAME,PKL_FILE_PATH), os.path.join(tmp_dir, PKL_FILE_PATH))
            # FAISSインデックスのロード
            embedding = OpenAIEmbeddings()
            #self.vector_store = FAISS.load_local(tmp_dir, embedding)
            self.vector_store = FAISS.load_local(tmp_dir, embedding)
        self.retriever = self.vector_store.as_retriever(search_kwargs={"k": 2})

    def retrieve(self,query):#情報を検索して返す
        answer = self.retriever.get_relevant_documents(query)
        return answer
    
    


if __name__ == "__main__":  #テスト用,importされた時には実行されない
    query = "iPhone 11 Pro Maxに近いスペックのスマートフォンについて教えてください"
    a=Retrieval()
    answer=a.retrieve(query)
    print(answer)
