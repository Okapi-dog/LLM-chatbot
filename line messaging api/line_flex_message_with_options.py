import os
import json
from linebot import LineBotApi
from linebot.models import FlexSendMessage, TextSendMessage

def lambda_handler(event, context):
    replyToken = event['replyToken']
    input_text = event['input_text']
    choices_num = event['choices_num']
    choices = event['choices']

    alphabets = ["a", "b", "c", "d", "e", "f", "g", "h"]
    option_labels = [alphabets[i] for i in range(choices_num)]

    if choices_num != 0:  # 選択肢のボタンを作成
        buttons = []
        for label in option_labels:
            buttons.append({
                "type": "button",
                "action": {
                    "type": "message",
                    "label": label,
                    "text": label
                },
                "style": "primary",
                "color": "#9400d3",
                "margin": "xs"
            })

        # 質問と選択肢の詳細を組み込む
        flex_message_options = []
        for i in range(len(choices)):
            flex_message_options.append({
                "type": "box",
                "layout": "horizontal",
                "contents": [
                    {
                "type": "text",
                "text": option_labels[i],
                "size": "lg",
                "color": "#555555",
                "decoration": "none",
                "gravity": "top",
                "scaling": False,
                "weight": "bold",
                "style": "normal",
                "margin": "none",
                "flex": 0
              },
                    {
                        "type": "text",
                        "text": choices[i],
                        "size": "lg",
                        "color": "#111111",
                        "align": "start",
                        "wrap": True,
                        "margin": "md"
                    }
                ],
                "spacing": "none",
                "position": "relative",
                "margin": "md"
            })

        # Flexメッセージを構築
        flex_message_contents = {
        "type": "bubble",
        "header": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": "質問",
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
                    "type": "text",
                    "text": input_text,
                    "wrap": True,
                    "weight": "bold",
                    "size": "lg",
                    "margin": "md",
                    "adjustMode": "shrink-to-fit"
                },
                {
                    "type": "separator",
                    "margin": "xxl"
                },
                {
                    "type": "box",
                    "layout": "vertical",
                    "margin": "xxl",
                    "spacing": "sm",
                    "contents": flex_message_options + [
                        {
                            "type": "box",
                            "layout": "horizontal",
                            "contents": buttons
                        }
                    ]
                }
            ]
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": "↑当てはまる記号をタップ！",
                    "color": "#ffffff",
                    "weight": "bold",
                    "align": "center",
                    "size": "xl",
                    "wrap": True
                }
            ]
        },
        "styles": {
            "header": {
                "backgroundColor": "#da70d6",
                "separator": True,
                "separatorColor": "#da70d6"
            },
            "hero": {
                "backgroundColor": "#da70d6"
            },
            "footer": {
                "separator": True,
                "backgroundColor": "#ba55d3"
            }
        }
        }
        flex_message = FlexSendMessage(alt_text="質問", contents=flex_message_contents)

        # Flexメッセージを送信
        LINE_CHANNEL_ACCESS_TOKEN = os.environ['LINE_CHANNEL_ACCESS_TOKEN']
        LINE_BOT_API = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
        LINE_BOT_API.reply_message(replyToken, flex_message)

    else:
        # テキストメッセージを送信
        LINE_CHANNEL_ACCESS_TOKEN = os.environ['LINE_CHANNEL_ACCESS_TOKEN']
        LINE_BOT_API = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
        LINE_BOT_API.reply_message(replyToken, TextSendMessage(text=input_text))

    return {
        'statusCode': 200,
        'body': json.dumps('Function executed successfully!')
    }
