import asyncio
import re
from time import time
#from config import dotenv_setting  # api_keyの読み込み
#from langchain.chat_models import ChatOpenAI
from langchain_openai import ChatOpenAI
#from langchain.prompts import PromptTemplate
from langchain_core.prompts import PromptTemplate
from langchain.schema import StrOutputParser
from langchain.schema.document import Document

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


async def process_answer(request: str, answer_dict: dict[str,str]) -> list[str]:
    # 推薦文の生成を非同期実行
    response = await generate_recommendations(request, answer_dict)
    return response


async def process_answers(request: str, answers_dict: list[dict[str, str]]) -> list[list[str]]:

    # 各回答に対して非同期タスクを作成する
    tasks = [asyncio.create_task(process_answer(request, answer_dict)) for answer_dict in answers_dict]

    # asyncio.gatherを使用して、すべてのタスクを並行実行する
    outcome = await asyncio.gather(*tasks)
    print("finished")
    return outcome

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
