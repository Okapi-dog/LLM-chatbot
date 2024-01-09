import json
import os
import boto3
import random
from linebot import LineBotApi
from linebot.models import FlexSendMessage, BubbleContainer, ImageComponent, TextComponent, BoxComponent

# Line Botのチャネルアクセストークンを設定
LINE_CHANNEL_ACCESS_TOKEN = os.environ['LINE_CHANNEL_ACCESS_TOKEN']
line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)

def get_random_s3_object_key(bucket_name):
    # boto3ライブラリを使ってS3のクライアントを作成
    s3 = boto3.client('s3')
    # 指定したバケット内のオブジェクトの一覧を取得
    response = s3.list_objects_v2(Bucket=bucket_name)
    # 取得した一覧からオブジェクトの部分だけを取り出す
    all_objects = response['Contents']
    # オブジェクトの一覧からランダムに1つ選ぶ
    random_object = random.choice(all_objects)
    # ランダムに選んだオブジェクトのキー（名前）を返す
    return random_object['Key']
    
def get_s3_image_url(bucket_name, object_key):
    # boto3ライブラリを使ってS3のクライアントを作成
    s3 = boto3.client('s3')
    # 指定したバケットとオブジェクトに対するpresigned URL（一時的に公開されるURL）を生成
    # このURLは1時間（3600秒）後に有効期限が切れる
    url = s3.generate_presigned_url('get_object',
                                     Params={'Bucket': bucket_name, 'Key': object_key}, 
                                     ExpiresIn=3600)
    # 生成したURLを返す
    return url

#スマホの詳細
spec_legend = ["機種名", "カラー", "バッテリー容量", 
                "対応する充電方法", 
                "画面サイズ", "画面解像度", "背面カメラ画素数",
                  "前面カメラ画素数", "長さ*幅*厚み", "重量"]
specs = ["iPhone 12 Pro Max", "Pacific Blue, Graphite, Gold, Silver", "3687mAh",
        "急速充電器(20W)、ワイヤレス充電器(15W)", "6.7インチ", "2778*1284", "1200万画素*3", "1200万画素",
        "160.8*78.1*7.4mm", "226g"]
content_dict = dict(zip(spec_legend, specs))
body_contents = [TextComponent(
                    text=i + ": "+ content_dict[i],
                    size='md',
                ) for i in spec_legend]
# 画像ファイルを作成する関数
def create_flex_message(image_url, text):
    bubble = BubbleContainer(
        header=BoxComponent(
            layout='vertical',
            contents=[
                TextComponent(
                    text='おすすめスマホ',
                    size='xl',
                    weight='bold'
                )
            ],
            color='#c4ebf5'
        ),
        hero=BoxComponent(
            layout='vertical',
            contents=[
                ImageComponent(
                    url=image_url,
                    size='full',
                    aspect_mode='cover',
                    aspect_ratio='1:1',
                    gravity='top'
                )
            ]
        ),
        body=BoxComponent(
            layout='vertical',
            contents=body_contents,
            color='#c4ebf5'
        )
    )
    return FlexSendMessage(alt_text=text, contents=bubble)

# AWS Lambdaのハンドラ関数
def lambda_handler(event, context):
    replyToken = event['events'][0]['replyToken']
    text = event['events'][0]['message']['text']
    
    bucket_name = 'llm-chatbot-s3'  # あなたのS3バケット名
    object_key = get_random_s3_object_key(bucket_name)
    image_url = get_s3_image_url(bucket_name, object_key)
    
    flex_message = create_flex_message(image_url, text)

    # Flex Messageを返信
    line_bot_api.reply_message(replyToken, flex_message)

    return {
        'statusCode': 200,
        'body': json.dumps('Hello from Lambda!')
    }