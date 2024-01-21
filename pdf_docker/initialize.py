# coding: utf-8
import sys
import os
import boto3
import json
import subprocess
from jinja2 import Environment, FileSystemLoader
from datetime import datetime


def next_lambda(message,choices_num,log_message,event,choices:None):#次のラムダ関数を呼び出す
    lambda_client = boto3.client('lambda')
    #ARN of plain_text_output
    #next_function_name = 'arn:aws:lambda:ap-northeast-1:105837277682:function:plain_text_output'
    next_function_name = 'arn:aws:lambda:ap-northeast-1:105837277682:function:line_question_option_output'
    response = lambda_client.invoke(
        FunctionName=next_function_name,
        InvocationType='Event',
        Payload=json.dumps({'input_text': message, 'choices_num':choices_num, 'replyToken': event['replyToken'], 'userId': event['userId'],'choices':choices} )
    )
    return log_message+event['userId']
    




def handler(event, context):
    file_id ="testtest"
    bucket_name = 'pdf-tex'
    file_name_in_s3 = f'{file_id}.pdf'
    current_date = datetime.now()
    formatted_date = current_date.strftime("生成日: %Y-%m-%d")
    template_dir = './'
    OUT_DIR = '/tmp/'
    env = Environment(
        loader=FileSystemLoader(template_dir, encoding='utf8'),
        variable_start_string='[[',
        variable_end_string=']]',
        )
    template = env.get_template('catalog_template.tex')
    tex_file_path = os.path.join(OUT_DIR, f'{file_id}.tex')
    pdf_file_path = os.path.join(OUT_DIR, f'{file_id}.pdf')

    with open(tex_file_path, 'w') as f:
        f.write(template.render(
            date=formatted_date
        ))
    
    command = [
        "bash",
        "pdf_generate.sh",
        tex_file_path
    ]
    try:
        result = subprocess.run(command, stdout=subprocess.PIPE , stderr=subprocess.PIPE ,encoding="utf-8")
        if result.returncode == 0:
            print("PDF生成成功だよーーんbypython")
            #s3_client = boto3.client('s3')
            #s3_client.upload_file(pdf_file_path, bucket_name, file_name_in_s3)
        else:
            print("PDF失敗だよーん")
            print(result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"エラーが発生しました: {e}")

    return 'Hello from AWS Lambda using Python' + sys.version + '!'
handler("","")
