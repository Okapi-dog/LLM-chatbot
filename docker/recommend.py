import asyncio
import nest_asyncio
nest_asyncio.apply()
import re
from time import time
#from config import dotenv_setting  # api_keyの読み込み
from langchain_openai import ChatOpenAI
from langchain_openai import OpenAI
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
        """ユーザーの求める要件と推薦するスマートフォンの情報が下に格納されています。これらを基にスマートフォンの推薦文を必ず40字以内で3つ生成してください。内容は推薦するスマートフォンの情報に書いてある内容のみにし、推薦するスマートフォンの情報に書いてない内容は絶対に含めないで下さい。"@#$%^などと言った文字列は絶対に含めないでください。

        ユーザーの求める要件: {request}
        推薦するスマートフォンの情報: {answer_dict}
        推薦文に1.などは必要ありません。ユーザーの求める要件を推薦文に含めないでください。推薦文は絶対に40文字以内で三つ生成し、改行で区切ってください。
        推薦文:
        """,
    )
    model = ChatOpenAI(model="gpt-3.5-turbo-1106", temperature=0)
    model_gpt4 = ChatOpenAI(model="gpt-4-0125-preview", temperature=0)
    output_parser = StrOutputParser()
    chain = prompt | model | output_parser
    # 推薦文の生成を非同期実行
    recommendations = await chain.ainvoke({"request": request, "answer_dict": answer_dict})
    # 生成した推薦文を改行で区切ってリストに格納
    recommendations = [recommendation.strip() for recommendation in recommendations.split("\n", 2)]
    for i in range(len(recommendations)):
        recommendations[i]=escape_tex_special_chars(recommendations[i])
        
    return recommendations

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

def escape_tex_special_chars(text):
    # List of TeX special characters that need to be escaped
    special_chars = ['\\','#', '$', '%', '&', '_', '{', '}', '~', '^']

    # Escaping each special character
    for char in special_chars:
        # Using a backslash '\' before each special character
        # The backslash itself needs to be escaped in Python strings, hence '\\'
        if char != '\\':  # Handling backslash separately
            text = text.replace(char, '\\' + char)
        else:
            text = text.replace(char, '\\textbackslash ')

    return text


async def select_review(review_dict_list:list[dict[str,str]],request: str, phone: str) -> list[str]:
    review_dict =await get_reviews(review_dict_list,phone)
    if review_dict == None:
        return "","","",""
    
    prompt = PromptTemplate.from_template(
        """ユーザーの求める要件に最も適合しているレビューを二つレビュー番号で答えてください。ただ単に製品情報を述べているレビューの評価は低くしてください。違う製品についてのレビューは不適合なレビューとします。レビュー番号は1,2,3,4,5のいずれかです。返答は数字のみ,で区切って二つ答えてください。"

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
    model_gpt4 = ChatOpenAI(model="gpt-4-0125-preview", temperature=0)
    llm = OpenAI(model="gpt-3.5-turbo-instruct")
    output_parser = StrOutputParser()
    chain = prompt | model | output_parser
    # 推薦文の生成を非同期実行
    review_num = await chain.ainvoke({"request": request, "phone": phone, "review1": review_dict["レビュー1"], "review2": review_dict["レビュー2"], "review3": review_dict["レビュー3"], "review4": review_dict["レビュー4"], "review5": review_dict["レビュー5"]})
    # 生成した推薦文を改行で区切ってリストに格納
    print("review_num:"+str(review_num))
    review_num = review_num.split(",")
    review1=""
    review2=""
    review1_url=""
    review2_url=""
    print(review_dict)
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
            print("一個しかレビューない")
    return review1,review2,review1_url,review2_url
    

async def sum_review(review_dict_list:list[dict[str,str]],request: str, answer_dict: dict[str, str]) -> dict[str,str]:
    review1,review2,review1_url,review2_url = await select_review(review_dict_list,request, answer_dict["機種"])
    prompt = PromptTemplate.from_template(
        """ユーザーが求める要件を考慮してレビューのみを日本語で要約してください。要約にはメリットとデメリットどちらも含めることができます。

        ユーザーが求める要件: {request}
        {phone}のレビュー: {review}
        レビューの要約のみを50字以内で回答してください。ユーザーが求める要件を要約に含めないでください。
        """,
    )
    model = ChatOpenAI(model="gpt-3.5-turbo-1106", temperature=0)
    model_gpt4 = ChatOpenAI(model="gpt-4-0125-preview", temperature=0)
    llm = OpenAI(model="gpt-3.5-turbo-instruct")
    output_parser = StrOutputParser()
    chain = prompt | model | output_parser
    # 推薦文の生成を非同期実行
    review_sum1 = await chain.ainvoke({"request": request, "phone": answer_dict["機種"], "review": review1})
    review_sum1=escape_tex_special_chars(review_sum1)
    review_sum2 = await chain.ainvoke({"request": request, "phone": answer_dict["機種"], "review": review2})
    review_sum2=escape_tex_special_chars(review_sum2)
    # 生成した推薦文を改行で区切ってリストに格納
    output={"review1":review_sum1,"review2":review_sum2,"review1_url":review1_url,"review2_url":review2_url}
    if review1_url == "":
        output["review1"] = "エラーによりレビューが取得できませんでした。"
    if review2_url == "":
        output["review2"] = "エラーによりレビューが取得できませんでした。"
    return output


async def get_reviews(review_dict_list:list[dict[str, str]],phone:str) -> dict[str,str]:
    for review_dict in review_dict_list:
        if phone in review_dict["機種"]:
            return review_dict
    
    return None
    




async def process_answer(request: str, answer_dict: dict[str,str]) -> list[str]:
    # 推薦文の生成を非同期実行
    response = await generate_recommendations(request, answer_dict)
    return response




async def process_answers(request: str, answers_dict: list[dict[str, str]]) -> (list[list[str]],list[dict[str,str]]):

    review_dict_list=get_all_sum_dynamodb()

    # 各回答に対して非同期タスクを作成する
    tasks_reccomend = [asyncio.create_task(process_answer(request, answer_dict)) for answer_dict in answers_dict]
    tasks_review = [asyncio.create_task(sum_review(review_dict_list,request, answer_dict)) for answer_dict in answers_dict]

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
