import boto3
import os
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS

os.environ['AWS_DEFAULT_REGION'] = 'ap-northeast-1'

def get_all_sum_dynamodb() -> list[dict[str, str]]:
    # DynamoDB サービスリソースを初期化
    dynamodb = boto3.resource('dynamodb')

    # 操作するテーブルを指定
    table = dynamodb.Table('IntegratedPhoneStatus')

    # 初期化
    found_items = []
    last_evaluated_key = None
    # スキャン操作のパラメータ
    scan_kwargs = {}
    response = table.scan(**scan_kwargs)
    found_items.extend(response['Items'])
    last_evaluated_key = response.get('LastEvaluatedKey')

    while last_evaluated_key:

        # 前回のスキャンで LastEvaluatedKey がある場合に、次のページからスキャンを続ける
        scan_kwargs['ExclusiveStartKey'] = last_evaluated_key
        # スキャン操作を実行
        response = table.scan(**scan_kwargs)
        found_items.extend(response['Items'])
        # 次のページがないか確認
        last_evaluated_key = response.get('LastEvaluatedKey')
    
    print("all:"+str(len(found_items)))
    found_items_not_empty=[]#valueが存在しない項目は削除する
    for found_item in found_items:
        found_item_not_empty = {k: v for k, v in found_item.items() if v}
        found_items_not_empty.append(found_item_not_empty)
    return found_items_not_empty

#dynamodbのIntegratedPhoneStatusより携帯データダウンロード
found_items_not_empty=get_all_sum_dynamodb()

embedding = OpenAIEmbeddings(model="text-embedding-3-large")
#embeddingする元データの生成
answers = ["".join(f"{key}:{value} | " for key, value in item_dict.items()) for item_dict in found_items_not_empty]
#embeddingしてローカルに保存
vector_store = FAISS.from_texts(answers, embedding)
vector_store.save_local("IntegratedPhoneStatus-v3l")
#embeddingデータをs3にアップロード
client = boto3.client('s3')
client.upload_file("./IntegratedPhoneStatus-v3l/index.faiss", "vector-store-s3", "IntegratedPhoneStatus-v3l/index.faiss")
client.upload_file("./IntegratedPhoneStatus-v3l/index.pkl", "vector-store-s3", "IntegratedPhoneStatus-v3l/index.pkl")
#以下はembeddingデータ確認用
#vector_store = FAISS.load_local("IntegratedPhoneStatus-v3l", embedding)
#retriever = vector_store.as_retriever(search_kwargs={"k": 4})
#answer = retriever.get_relevant_documents("iPhone15が欲しいな")
#print(answer)

