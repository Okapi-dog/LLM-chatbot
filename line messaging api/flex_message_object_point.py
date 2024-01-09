import json
import os
import boto3
import random
from linebot import LineBotApi
from linebot.models import FlexSendMessage, BubbleContainer, ImageComponent, TextComponent, BoxComponent

# Line Botのチャネルアクセストークンを設定
LINE_CHANNEL_ACCESS_TOKEN = os.environ['LINE_CHANNEL_ACCESS_TOKEN']
line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)

def get_object_key_from_dynamodb(model_name):
    # DynamoDBのテーブルを指定
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('your_table_name')  # ここにDynamoDBのテーブル名を指定
    # 機種名で検索
    response = table.get_item(Key={'model_name': model_name})
    # オブジェクトキーを取得して返す
    if 'Item' in response:
        return response['Item']['object_key']
    else:
        return None

def get_s3_image_url(bucket_name, object_key):
    s3 = boto3.client('s3')
    url = s3.generate_presigned_url('get_object', Params={'Bucket': bucket_name, 'Key': object_key}, ExpiresIn=3600)
    return url

def get_spec_from_dynamodb(model_name):
    # DynamoDBのテーブルを指定
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('your_table_name')  # ここにDynamoDBのテーブル名を指定

    # 機種名で検索
    response = table.get_item(Key={'model_name': model_name})

    # スペックを取得して返す
    if 'Item' in response:
        return response['Item']['spec']
    else:
        return None

bucket_name = 'your-bucket-name'
object_key = get_object_key_from_dynamodb(bucket_name)
image_url = get_s3_image_url(bucket_name, object_key)
content_dict = get_spec_from_dynamodb(bucket_name, object_key)


#スマホの詳細
# spec_legend = ["機種名", "カラー", "バッテリー容量", 
#                 "対応する充電方法", 
#                 "画面サイズ", "画面解像度", "背面カメラ画素数",
#                   "前面カメラ画素数", "長さ*幅*厚み", "重量"]
# specs = ["iPhone 12 Pro Max", "Pacific Blue, Graphite, Gold, Silver", "3687mAh",
#         "急速充電器(20W)、ワイヤレス充電器(15W)", "6.7インチ", "2778*1284", "1200万画素*3", "1200万画素",
#         "160.8*78.1*7.4mm", "226g"]
# content_dict = dict(zip(spec_legend, specs))
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