import json
import boto3

def lambda_handler(event, context):
    input_text = event['input_text']
    replyToken = event['replyToken']
    # 次のラムダ関数を呼び出す (line_test_function_1 -> line_test_function_2)
    lambda_client = boto3.client('lambda')
    #ARN of Function 2
    next_function_name = 'arn:aws:lambda:ap-northeast-1:105837277682:function:line_test_function_2'
    response = lambda_client.invoke(
        FunctionName=next_function_name,
        InvocationType='RequestResponse',
        Payload=json.dumps({'input_text': input_text, 'replyToken': replyToken})
    )
    
    return {
        'statusCode': 200,
        'body': json.dumps('Function 1 executed successfully!')
    }
#dumpsは２つの引数を取ることができない。
#                Payload=json.dumps({'input_text': messageText}, {'replyToken': replyToken})
#                Payload=json.dumps({'input_text': messageText, 'replyToken': replyToken})

# この関数をテストするjsonイベントは以下のようになります。
# {
#     "input_text": "Hello, world!",
#     "replyToken": "replyToken"
# }

# Traceback (most recent call last):
#  File "/var/task/lambda_function.py", line 5, in lambda_handler
#    input_text = event['input_text']END となりました。
# このエラーは、line_test_function_1.pyの実行権限がないことが原因です。
# 実行権限を付与するには、IAMのロールを編集します。
# 1. IAMのロールを開きます。
# 2. Lambda-Full-Accessをクリックします。

