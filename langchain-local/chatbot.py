import os
import tempfile

import boto3
from config import dotenv_setting  # api_keyの読み込み
from langchain.embeddings import OpenAIEmbeddings
from langchain.vectorstores import FAISS

# S3からダウンロードするファイルの設定
bucket_name = "vector-store-s3"
faiss_index_file = "index.faiss"
pkl_file = "index.pkl"

# boto3 S3クライアントの作成
s3 = boto3.client("s3")

# 一時ディレクトリの作成
with tempfile.TemporaryDirectory() as tmp_dir:
    # S3からファイルをダウンロード
    s3.download_file(bucket_name, faiss_index_file, os.path.join(tmp_dir, faiss_index_file))
    s3.download_file(bucket_name, pkl_file, os.path.join(tmp_dir, pkl_file))

    # FAISSインデックスのロード
    embedding = OpenAIEmbeddings()
    vector_store = FAISS.load_local(tmp_dir, embedding)

retriever = vector_store.as_retriever()
docs = retriever.get_relevant_documents("ベクトルデータの中からiPhone 12 Pro Maxかそれに近いものを検索してください。")
print(docs)
