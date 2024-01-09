# test_function2からのeventを引数として受け取り、replyTokenが指すアカウントに対して、input_textを送信する。
# Compare this snippet from mitou_lambda/line_test_function_2.py:
import os
import json
import boto3
from linebot import LineBotApi
from linebot.models import TextSendMessage, QuickReply, QuickReplyButton, MessageAction

def lambda_handler(event, context):
    input_text = event['input_text']
    replyToken = event['replyToken']
    question_number = event['question_number']
    
    # question = "以下の中から当てはまる選択肢を選んでください" #LLMが出力した質問文を入れる
    
    # options = ["a", "b", "c", "d", "e"] #LLMが出力した選択肢を入れる
    alphabets = ["a", "b", "c", "d", "e", "f", "g", "h"] #選択肢の数に応じてアルファベットを用意
    options = [alphabets[i] for i in range(question_number)]
    if question_number!=0:
        items = [QuickReplyButton(action=MessageAction(label=i, text=i)) for i in options]#optionsをボタン化してitemsに追加
            
        quick_reply = QuickReply(#選択肢を入れるquick replyの作成
            items=items
            )
            
        #最終的には入力関数→この関数を含む他の関数→出力関数　という形にする予定
        LINE_CHANNEL_ACCESS_TOKEN = os.environ['LINE_CHANNEL_ACCESS_TOKEN'] 
        LINE_BOT_API = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
        LINE_BOT_API.reply_message(replyToken, TextSendMessage(text=input_text, quick_reply=quick_reply))
    
    return {
        'statusCode': 200,
        'body': json.dumps('Function 2 executed successfully!')
    }