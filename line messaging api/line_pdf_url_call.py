#lineのユーザIDを入力として受け取って、そのユーザIDがファイル名に含まれたPDFをs3上で探して、そのURLを返すaws lambda関数
import boto3
import os
from linebot import LineBotApi
from linebot.models import FlexSendMessage
from urllib.parse import quote

def lambda_handler(event, context):
  # Extract the LINE user ID from the event object
  userId = event.get('userId')
  replyToken = event['replyToken']
  
  if not userId:
    return {'statusCode': 400, 'body': 'LINE user ID not provided'}
  
  # Initialize a boto3 client for S3
  s3_client = boto3.client('s3')
  bucket_name = os.environ['BUCKET_NAME']  # Set your bucket name in Lambda's environment variables
  file_name=""

  try:
    # List objects in the specified S3 bucket
    response = s3_client.list_objects_v2(Bucket=bucket_name)
    
    if 'Contents' in response:
      for item in response['Contents']:
        file_name = item['Key']
            
        # Check if the file name contains the LINE user ID and is a PDF
        if userId in file_name and file_name.endswith('.pdf'):
          file_url = f"https://{bucket_name}.s3.amazonaws.com/{file_name}"
          print("file_url:"+file_url)
          print("file_urlエンコード:"+quote(file_url,safe=':/'))
    else:
      file_url=""
      
  except Exception as e:
    print("エラー発生")
    return {'statusCode': 500, 'body': f'Error occurred: {str(e)}'}

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
          "weight": "bold",
          "align": "center",
          "color": "#000000"
        }
      ]
    },
    "body": {
      "type": "box",
      "layout": "vertical",
      "contents": [
        {
          "type": "box",
          "layout": "vertical",
          "margin": "xxl",
          "spacing": "sm",
          "contents": [
            {
              "type": "text",
              "text": "ボタンを押してPDFをみる",
              "weight": "bold",
              "align": "center"
            }
          ]
        },
        {
          "type": "box",
          "layout": "vertical",
          "contents": [
            {
              "type": "button",
              "action": {
                "type": "uri",
                "label": "ダウンロード",
                "uri": quote(file_url,safe=':/') #ここにpdfのurlを入れる
              }
            }
          ]
        }
        
      ]
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
  flex_message_contents2 = {
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
          "text": "ボタンを押してPDFを見る",
          "weight": "bold",
          "align": "center"
        },
        {
          "type": "button",
          "action": {
            "type": "uri",
            "label": "ダウンロード",
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
  flex_message = FlexSendMessage(alt_text="質問", contents=flex_message_contents2)
  # Flexメッセージを送信
  LINE_CHANNEL_ACCESS_TOKEN = os.environ['LINE_CHANNEL_ACCESS_TOKEN']
  LINE_BOT_API = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
  response_line=LINE_BOT_API.reply_message(replyToken, flex_message)
  print(response_line)
    
  # No matching file found
  return {'statusCode': 404, 'body': 'No matching PDF file found'}



