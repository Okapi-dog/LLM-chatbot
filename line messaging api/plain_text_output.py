#test_function2からのeventを引数として受け取り、replyTokenが指すアカウントに対して、input_textを送信する。
# Compare this snippet from mitou_lambda/line_test_function_2.py:
import os
import json
import boto3
from linebot import LineBotApi
from linebot.models import TextSendMessage

def lambda_handler(event, context):
    input_text = event['input_text']
    replyToken = event['replyToken']
    # LINEに通知する
    LINE_CHANNEL_ACCESS_TOKEN = os.environ['LINE_CHANNEL_ACCESS_TOKEN']
    LINE_BOT_API = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
    LINE_BOT_API.reply_message(replyToken, TextSendMessage(text=input_text))
    
    return {
        'statusCode': 200,
        'body': json.dumps('Function 2 executed successfully!')
    }
#この関数をテストするjsonイベントは以下のようになります。
# {
#     "input_text": "Hello, world!",
#     "replyToken": "replyToken"
# }
#a