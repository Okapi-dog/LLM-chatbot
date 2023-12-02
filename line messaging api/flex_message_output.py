import os
import json
import boto3
import random
from linebot import LineBotApi
from linebot.models import FlexSendMessage, BubbleContainer, BoxComponent, TextComponent, ButtonComponent, MessageAction, QuickReply, QuickReplyButton

def lambda_handler(event, context):
    text = event['events'][0]['message']['text']
    replyToken = event['events'][0]['replyToken']
    
    if text == 'じゃんけん':
        flex_message = BubbleContainer(
            header=BoxComponent(
                layout='vertical',
                contents=[
                    TextComponent(text='じゃんけん'),
                ]
            )
        )
        
        quick_reply = QuickReply(
        items=[
            QuickReplyButton(action=MessageAction(label='グー', text='グー')),
            QuickReplyButton(action=MessageAction(label='チョキ', text='チョキ')),
            QuickReplyButton(action=MessageAction(label='パー', text='パー')),
            ]
        )
    else:
        choices = ['グー', 'チョキ', 'パー']
        ai_choice = random.choice(choices)
        if text == ai_choice:
            result = 'あいこ'
        elif (text == 'グー' and ai_choice == 'チョキ') or (text == 'チョキ' and ai_choice == 'パー') or (text == 'パー' and ai_choice == 'グー'):
            result = 'あなたの勝ち'
        else:
            result = 'あなたの負け'
        flex_message = BubbleContainer(
            body=BoxComponent(
                layout='vertical',
                contents=[
                    TextComponent(text=f'あなた: {text}, AI: {ai_choice}'),
                    TextComponent(text=result),
                ]
            )
        )
        
        quick_reply = QuickReply(
        items=[
            QuickReplyButton(action=MessageAction(label='グー', text='グー')),
            QuickReplyButton(action=MessageAction(label='チョキ', text='チョキ')),
            QuickReplyButton(action=MessageAction(label='パー', text='パー')),
            ]
        )

    LINE_CHANNEL_ACCESS_TOKEN = os.environ['LINE_CHANNEL_ACCESS_TOKEN'] 
    LINE_BOT_API = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
    LINE_BOT_API.reply_message(replyToken, FlexSendMessage(alt_text='じゃんけん結果', contents=flex_message, quick_reply=quick_reply))
    
    return {
        'statusCode': 200,
        'body': json.dumps('Function executed successfully!')
    }