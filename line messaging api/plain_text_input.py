import os
import json
import boto3
from linebot import LineBotApi
from linebot.models import TextSendMessage

# 環境変数からLINE Botのチャネルアクセストークンを取得
LINE_CHANNEL_ACCESS_TOKEN = os.environ['LINE_CHANNEL_ACCESS_TOKEN']
# チャネルアクセストークンを使用して、LineBotApiのインスタンスを作成
LINE_BOT_API = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)

def lambda_handler(event, context):
    try:
        # LINEからメッセージを受信
        if event['events'][0]['type'] == 'message':
            # メッセージタイプがテキストの場合
            if event['events'][0]['message']['type'] == 'text':
                #ユーザID
                userId = event['events'][0]['source']['userId']
                # リプライ用トークン
                replyToken = event['events'][0]['replyToken']
                # 受信メッセージ
                messageText = event['events'][0]['message']['text']
                # テスト関数の呼び出し(この関数 ->line test funciton 1)
                lambda_client = boto3.client('lambda')
                next_function_name = 'arn:aws:lambda:ap-northeast-1:105837277682:function:line_test_function_1'  # Replace with ARN of Function 1
                response = lambda_client.invoke(
                FunctionName=next_function_name,
                InvocationType='RequestResponse', 
                Payload=json.dumps({'input_text': messageText, 'replyToken': replyToken, 'userId': userId})
                )

    # エラーが起きた場合
    except Exception as e:
        print(e)
        return {'statusCode': 500, 'body': json.dumps('Exception occurred.')}
    return {'statusCode': 200, 'body': json.dumps('Reply ended normally.')}
