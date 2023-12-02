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
    s3 = boto3.client('s3')
    response = s3.list_objects_v2(Bucket=bucket_name)
    all_objects = response['Contents']
    random_object = random.choice(all_objects)
    return random_object['Key']
    
def get_s3_image_url(bucket_name, object_key):
    s3 = boto3.client('s3')
    url = s3.generate_presigned_url('get_object', Params={'Bucket': bucket_name, 'Key': object_key}, ExpiresIn=3600)
    return url

# 画像ファイルを作成する関数
def create_flex_message(image_url, text):
    bubble = BubbleContainer(
        body=BoxComponent(
            layout='vertical',
            contents=[
                ImageComponent(
                    url=image_url,
                    size='full',
                    aspect_mode='cover',
                    aspect_ratio='1:1',
                    gravity='top'
                ),
                TextComponent(
                    text=text,
                    wrap=True,
                    weight='bold',
                    size='xl'
                )
            ]
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