import asyncio
import re
from time import time
#from config import dotenv_setting  # api_keyの読み込み
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from langchain.schema import StrOutputParser
from langchain.schema.document import Document
import boto3
from boto3.dynamodb.conditions import Attr
from boto3.session import Session

#retriever.pyのインポート
import retriever

def convert_to_dict(input_str: str) -> dict[str, str]:
    result_dict = {}
    # 正規表現でkeyとvalueを取得
    pairs = re.findall(r"([^:|]+):([^|]*)", input_str)
    for pair in pairs:
        # 値が空文字列でない場合のみ辞書に追加
        if pair[1].strip():
            key, value = pair
            result_dict[key.strip()] = value.strip()
    return result_dict

async def generate_recommendations(request: str, answer_dict: dict[str, str]) -> list[str]:
    prompt = PromptTemplate.from_template(
        """以下のrequestに基づいたおすすめのスマートフォンの情報がanswer_dictに格納されています。answer_dictの情報を基に、requestでユーザーが求める点を中心に推薦文を20字以内で3つ生成してください。内容はanswer_dictに書いてある内容のみにし、answer_dictに書いてない内容は絶対に含めないで下さい。推薦文に1.などは必要ありません。"@#$%^などと言った文字列は絶対に含めないでください。"
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
    model_gpt4 = ChatOpenAI(model="gpt-4-1106-preview", temperature=0)
    output_parser = StrOutputParser()
    chain = prompt | model | output_parser
    # 推薦文の生成を非同期実行
    recommendations = await chain.ainvoke({"request": request, "answer_dict": answer_dict})
    # 生成した推薦文を改行で区切ってリストに格納
    recommendations = [recommendation.strip() for recommendation in recommendations.split("\n", 2)]
    return recommendations


async def select_review(request: str, phone: str) -> list[str]:
    review_dict =await get_reviews_dynamo(phone)
    prompt = PromptTemplate.from_template(
        """ユーザーの求める要件に最も適合しているレビューを二つレビュー番号で答えてください。製品情報を実機を触らずに述べているレビューの評価は低くなります。errorコードが入っているレビューや違う製品についてのレビューは不適合なレビューとします。レビュー番号は1,2,3,4,5のいずれかです。返答は数字のみ,で区切って答えてください。"

        例:
            ユーザーが求める要件: 予算: 5万円から8万円,重視するポイント: 長時間バッテリーを持つこと,主な目的: ゲームをプレイすること,好みのサイズ: 手にしっくりと収まる中くらいのサイズが好き
            推薦機種: iPhone 12 Pro Max
            レビュー1: レビューは例の為省略。
            レビュー2: レビューは例の為省略。
            レビュー3: レビューは例の為省略。
            レビュー4: レビューは例の為省略。
            レビュー5: レビューは例の為省略。
            response: 1,3
        例の終わり

        ユーザーが求める要件: {request}
        推薦機種: {phone}
        レビュー1: {review1}
        レビュー2: {review2}
        レビュー3: {review3}
        レビュー4: {review4}
        レビュー5: {review5}
        response: 
        """,
    )
    model = ChatOpenAI(model="gpt-3.5-turbo-1106", temperature=0)
    model_gpt4 = ChatOpenAI(model="gpt-4-1106-preview", temperature=0)
    output_parser = StrOutputParser()
    chain = prompt | model | output_parser
    # 推薦文の生成を非同期実行
    review_num = await chain.ainvoke({"request": request, "phone": phone, "review1": review_dict["レビュー1"], "review2": review_dict["レビュー2"], "review3": review_dict["レビュー3"], "review4": review_dict["レビュー4"], "review5": review_dict["レビュー5"]})
    # 生成した推薦文を改行で区切ってリストに格納
    review_num = review_num.split(",")
    review1=""
    review2=""
    review1_url=""
    review2_url=""
    for i in range(5):
        if len(review_num) == 2:
            if review_num[0] == str(i+1):
                review1 = review_dict[f"レビュー{i+1}"]
                review1_url = review_dict[f"レビュー{i+1}のurl"]
            if review_num[1] == str(i+1):
                review2 = review_dict[f"レビュー{i+1}"]
                review2_url = review_dict[f"レビュー{i+1}のurl"]
        elif len(review_num) == 1:
            if review_num[0] == str(i+1):
                review1 = review_dict[f"レビュー{i+1}"]
                review1_url = review_dict[f"レビュー{i+1}のurl"]
    return review1,review2,review1_url,review2_url
    

async def sum_review(request: str, answer_dict: dict[str, str]) -> dict[str,str]:
    review1,review2,review1_url,review2_url = await select_review(request, answer_dict["機種"])
    prompt = PromptTemplate.from_template(
        """下のレビューを日本語で要約してください。要約する際にはユーザーが求める要件を読みユーザーが必要としていることを意識して要約してください。要約にはメリットとデメリットどちらも含めることができます。要約は50字以内でお願いします。"

        ユーザーが求める要件: {request}
        推薦機種: {phone}
        レビュー: {review}
        response: 
        """,
    )
    model = ChatOpenAI(model="gpt-3.5-turbo-1106", temperature=0)
    model_gpt4 = ChatOpenAI(model="gpt-4-1106-preview", temperature=0)
    output_parser = StrOutputParser()
    chain = prompt | model | output_parser
    # 推薦文の生成を非同期実行
    review_sum1 = await chain.ainvoke({"request": request, "phone": answer_dict["機種"], "review": review1})
    review_sum2 = await chain.ainvoke({"request": request, "phone": answer_dict["機種"], "review": review2})
    # 生成した推薦文を改行で区切ってリストに格納
    output={"review1":review_sum1,"review2":review_sum2,"review1_url":review1_url,"review2_url":review2_url}
    return output
        

async def get_reviews_dynamo(phone: str) -> dict[str, str]:
    # DynamoDB サービスリソースを初期化
    dynamodb = boto3.resource('dynamodb')

    # 操作するテーブルを指定
    table = dynamodb.Table('sumdatabase')

    # スキャン操作で使用するフィルタ条件
    filter_condition = Attr('機種').contains(phone)

    # 初期化
    found_items = []
    last_evaluated_key = None

    while True:
        # スキャン操作のパラメータ
        scan_kwargs = {
            'FilterExpression': filter_condition
        }

        # 前回のスキャンで LastEvaluatedKey がある場合、次のページからスキャンを続ける
        if last_evaluated_key:
            scan_kwargs['ExclusiveStartKey'] = last_evaluated_key

        # スキャン操作を実行
        response = table.scan(**scan_kwargs)

        # 検索結果があるか確認
        if response['Items']:
            found_items.extend(response['Items'])
            break  # 最初の項目が見つかったらループを終了

        # 次のページがないか確認
        last_evaluated_key = response.get('LastEvaluatedKey')
        if not last_evaluated_key:
            break  # 全てのページをスキャンし終わったらループを終了
    if len(found_items) == 0:
        return {}
    else:
        return found_items[0]
    

def get_all_sum_dynamodb() -> list[dict[str, str]]:
    # DynamoDB サービスリソースを初期化
    dynamodb = boto3.resource('dynamodb')

    # 操作するテーブルを指定
    table = dynamodb.Table('sumdatabase')

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
    return found_items


async def process_answer(request: str, answer_dict: dict[str,str]) -> list[str]:
    # 推薦文の生成を非同期実行
    response = await generate_recommendations(request, answer_dict)
    return response




async def process_answers(request: str, answers_dict: list[dict[str, str]]) -> (list[list[str]],list[dict[str,str]]):

    sum_dynamodb=get_all_sum_dynamodb()

    # 各回答に対して非同期タスクを作成する
    tasks_reccomend = [asyncio.create_task(process_answer(request, answer_dict)) for answer_dict in answers_dict]
    tasks_review = [asyncio.create_task(sum_review(request, answer_dict)) for answer_dict in answers_dict]

    # asyncio.gatherを使用して、すべてのタスクを並行実行する
    outcome = await asyncio.gather(*tasks_reccomend, *tasks_review)
    compelling = outcome[0:len(answers_dict)]
    review = outcome[len(answers_dict):]
    print("finished")
    return compelling,review

if __name__ == "__main__":#テスト用,importされた時には実行されない
    start_time = time()

    query = "撥水性があり、カメラの性能が良く、iPhone 12 Pro Maxに近いスペックのスマートフォンについて教えてください"
    retrival = retriever.Retrieval()
    answers: list[Document] = retrival.retrieve(query)
    answers_dict = [convert_to_dict(answer.page_content)for answer in answers]
    responses = asyncio.run(process_answers(query, answers_dict))

    end_time = time()
    print(f"処理時間: {end_time - start_time}秒")
    print("---------------------------------------------------")
    print(responses)
