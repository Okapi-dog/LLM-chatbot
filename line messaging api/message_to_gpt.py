import os
import json
from linebot import LineBotApi
from linebot.models import TextSendMessage, FlexSendMessage, BubbleContainer, BoxComponent, TextComponent, ButtonComponent, MessageAction, QuickReply, QuickReplyButton

def lambda_handler(event, context):
    #最終的にはGPTからの出力を受け取るようにする。（質問と選択肢を受け取る）
    text = event['events'][0]['message']['text'] #送信内容の取得
    replyToken = event['events'][0]['replyToken']
    question = "以下の中から当てはまる選択肢を選んでください" #LLMが出力した質問文を入れる
    choices_num = 5 #GPTが指定する選択肢の数を記録
    input_text = event['input_text']
    replyToken = event['replyToken']
    
    # options = ["a", "b", "c", "d", "e"] #LLMが出力した選択肢を入れる
    alphabets = ["a", "b", "c", "d", "e", "f", "g", "h"] #選択肢の数に応じてアルファベットを用意
    options = [alphabets[i] for i in range(choices_num)]
    if choices_num!=0:
        items = [QuickReplyButton(action=MessageAction(label=i, text=i)) for i in options]#optionsをボタン化してitemsに追加
            
        quick_reply = QuickReply(#選択肢を入れるquick replyの作成
            items=items
            )
            
        #最終的には入力関数→この関数を含む他の関数→出力関数　という形にする予定
        LINE_CHANNEL_ACCESS_TOKEN = os.environ['LINE_CHANNEL_ACCESS_TOKEN'] 
        LINE_BOT_API = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
        LINE_BOT_API.reply_message(replyToken, TextSendMessage(text=question, quick_reply=quick_reply))
    
    return {
        'statusCode': 200,
        'body': json.dumps('Function executed successfully!')
    }