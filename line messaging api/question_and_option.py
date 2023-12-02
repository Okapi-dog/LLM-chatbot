import os
import json
from linebot import LineBotApi
from linebot.models import FlexSendMessage, BubbleContainer, BoxComponent, TextComponent, ButtonComponent, MessageAction, QuickReply, QuickReplyButton

def lambda_handler(event, context):
    text = event['events'][0]['message']['text'] #送信内容の取得
    replyToken = event['events'][0]['replyToken']
    question = "以下の中から当てはまる選択肢を選んでください" #LLMが出力した質問文を入れる
    options = ["a", "b", "c", "d", "e"] #LLMが出力した選択肢を入れる
    items = []#選択肢を入れる配列

    for i in options:
        items.append(QuickReplyButton(action=MessageAction(label=i, text=i)))#optionsをボタン化してitemsに追加

    flex_message = BubbleContainer(#質問文を入れるflex messageの作成
            header=BoxComponent(
                layout='vertical',
                contents=[
                    TextComponent(text=question, size='sm', align='center', weight='bold'),
                ]
            )
        )
        
    quick_reply = QuickReply(#選択肢を入れるquick replyの作成
        items=items
        )

    LINE_CHANNEL_ACCESS_TOKEN = os.environ['LINE_CHANNEL_ACCESS_TOKEN'] 
    LINE_BOT_API = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
    LINE_BOT_API.reply_message(replyToken, FlexSendMessage(alt_text='おすすめ結果', contents=flex_message, quick_reply=quick_reply))
    
    return {
        'statusCode': 200,
        'body': json.dumps('Function executed successfully!')
    }