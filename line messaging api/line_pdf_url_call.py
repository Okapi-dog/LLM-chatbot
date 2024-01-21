#lineのユーザIDを入力として受け取って、そのユーザIDがファイル名に含まれたPDFをs3上で探して、そのURLを返すaws lambda関数
import boto3
import os
from linebot import LineBotApi
from linebot.models import FlexSendMessage
from urllib.parse import quote
import json

def send_text_to_line(message,event):#エラー時にテキストをLineで送信するラムダ関数を呼び出す
    lambda_client = boto3.client('lambda')
    #ARN of plain_text_output
    next_function_name = 'arn:aws:lambda:ap-northeast-1:105837277682:function:plain_text_output'
    response = lambda_client.invoke(
        FunctionName=next_function_name,
        InvocationType='Event',
        Payload=json.dumps({'input_text': message, 'replyToken': event['replyToken'], 'userId': event['userId']} )
    )




def lambda_handler(event, context):
  # Extract the LINE user ID from the event object
  userId = event.get('userId')
  replyToken = event['replyToken']
  
  if not userId:
    return {'statusCode': 400, 'body': 'LINE user ID not provided'}
  if not replyToken:
    return {'statusCode': 400, 'body': 'LINE replyToken not provided'}
  
  # Initialize a boto3 client for S3
  s3_client = boto3.client('s3')
  bucket_name = os.environ['BUCKET_NAME']  # Set your bucket name in Lambda's environment variables
  file_name=""
  file_url=""

  try:
    s3_resource = boto3.resource('s3')
    filtered_objects = s3_resource.Bucket(bucket_name).objects.filter(Prefix="スマホ紹介"+userId)
    objects = list(filtered_objects)
    if objects:
      file_name = objects[0].key
    else:
      return send_text_to_line('''おすすめのスマホを提供する際にファイルシステムにおいてエラーが発生しました。申し訳ございません。
      もう一度お試しいただくか、サポートにご連絡ください1''',event)
    
    file_url = f"https://{bucket_name}.s3.amazonaws.com/{file_name}"
    print("file_url:"+file_url)
    print("file_urlエンコード:"+quote(file_url,safe=':/'))
    
  except Exception as e:
    print(f"エラーが発生しました: {e}")
    return send_text_to_line('''おすすめのスマホを提供する際にファイルシステムにエラーが発生しました。申し訳ございません。
      もう一度お試しいただくか、サポートにご連絡ください2''',event)
  
  flex_message_contents = {
    "type": "bubble",
    "header": {
      "type": "box",
      "layout": "vertical",
      "contents": [
        {
          "type": "text",
          "text": "おすすめ結果",
          "size": "xl",
          "color": "#000000",
          "weight": "bold",
          "align": "center",
          "scaling": 'false'
        }
      ]
    },
    "body": {
      "type": "box",
      "layout": "vertical",
      "contents": [
        {
          "type": "text",
          "text": "下のボタンを押すことでおすすめ結果のページを見ることができます。尚この書類は3日で破棄されます。端末に保存するか印刷されることをおすすめします。",
          "weight": "bold",
          "align": "center",
          "wrap": True
        },
        {
          "type": "button",
          "action": {
            "type": "uri",
            "label": "PDFを見る",
            "uri": quote(file_url,safe=':/')
          }
        }
      ],
      "margin": "xxl",
      "spacing": "sm"
    },
    "styles": {
      "header": {
        "backgroundColor": "#da70d6"
      },
      "hero": {
        "backgroundColor": "#da70d6"
      },
      "footer": {
        "backgroundColor": "#ba55d3"
      }
    }
  }
  flex_message = FlexSendMessage(alt_text="おすすめのスマホの提案", contents=flex_message_contents)
  # Flexメッセージを送信
  LINE_CHANNEL_ACCESS_TOKEN = os.environ['LINE_CHANNEL_ACCESS_TOKEN']
  LINE_BOT_API = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
  response_line=LINE_BOT_API.reply_message(replyToken, flex_message)
  print(response_line)
  return "success!"



