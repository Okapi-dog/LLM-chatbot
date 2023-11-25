import os
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


if __name__ == "__main__":
    # boto3 S3クライアントの作成
    s3 = boto3.client("s3")

    # 一時ディレクトリの作成
    with tempfile.TemporaryDirectory() as tmp_dir:
        # S3からファイルをダウンロード
        s3.download_file(BUCKET_NAME, FAISS_FILE_PATH, os.path.join(tmp_dir, FAISS_FILE_PATH))
        s3.download_file(BUCKET_NAME, PKL_FILE_PATH, os.path.join(tmp_dir, PKL_FILE_PATH))
        # FAISSインデックスのロード
        embedding = OpenAIEmbeddings()
        vector_store = FAISS.load_local(tmp_dir, embedding)

    query = "iPhone 11 Pro Maxに近いスペックのスマートフォンについて教えてください"
    retriever = vector_store.as_retriever()
    docs = retriever.get_relevant_documents(query)
    print(docs)
    print("---------------------------------------------------")

    llm = ChatOpenAI(temperature=0, model_name="gpt-3.5-turbo")
    qa = RetrievalQA.from_chain_type(llm=llm, retriever=retriever)
    answer = qa(query)
    print(answer)
