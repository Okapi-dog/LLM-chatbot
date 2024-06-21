import os
import json
import boto3
from linebot import LineBotApi
from linebot.models import TextSendMessage

# Get LINE channel access token from environment variables
LINE_CHANNEL_ACCESS_TOKEN = os.environ['LINE_CHANNEL_ACCESS_TOKEN']
# Create an instance of LineBotApi using the channel access token
LINE_BOT_API = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)

def lambda_handler(event, context):
    try:
        # Parse the incoming event body as JSON
        body = json.loads(event['body'])
        
        # Check if the event type is 'message'
        if body['events'][0]['type'] == 'message':
            # Check if the message type is 'text'
            if body['events'][0]['message']['type'] == 'text':
                # Extract userId, replyToken, and messageText
                userId = body['events'][0]['source']['userId']
                replyToken = body['events'][0]['replyToken']
                messageText = body['events'][0]['message']['text']
                
                print("userId: " + str(userId))
                print("replyToken: " + str(replyToken))
                print("messageText: " + str(messageText))
                
                # Invoke the next Lambda function
                lambda_client = boto3.client('lambda')
                next_function_name = 'arn:aws:lambda:ap-northeast-1:105837277682:function:hitoshi-docker'
                response = lambda_client.invoke(
                    FunctionName=next_function_name,
                    InvocationType='Event',
                    Payload=json.dumps({
                        'input_text': messageText,
                        'replyToken': replyToken,
                        'userId': userId
                    })
                )
                
                print("Next function invoked successfully")
                
        print("Event received: " + json.dumps(body))
        
    except Exception as e:
        print(f"Error: {e}")
        
    return {
        'statusCode': 200,
        'body': json.dumps('Function 1 executed successfully!')
    }
