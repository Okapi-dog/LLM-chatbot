# coding: utf-8
import sys
import os
import boto3
import json
import subprocess
from jinja2 import Environment, FileSystemLoader
from datetime import datetime


def send_pdf_to_line(input_text,event):#PDFをLineで送信するラムダ関数を呼び出す
    lambda_client = boto3.client('lambda')
    #ARN of plain_text_output
    next_function_name = 'arn:aws:lambda:ap-northeast-1:105837277682:function:line_pdf_url_call'
    response = lambda_client.invoke(
        FunctionName=next_function_name,
        InvocationType='Event',
        Payload=json.dumps({'input_text': input_text, 'replyToken': event['replyToken'], 'userId': event['userId']} )
    )

def send_text_to_line(message,event):#エラー時にテキストをLineで送信するラムダ関数を呼び出す
    lambda_client = boto3.client('lambda')
    #ARN of plain_text_output
    next_function_name = 'arn:aws:lambda:ap-northeast-1:105837277682:function:plain_text_output'
    response = lambda_client.invoke(
        FunctionName=next_function_name,
        InvocationType='Event',
        Payload=json.dumps({'input_text': message, 'replyToken': event['replyToken'], 'userId': event['userId']} )
    )


def render_tex_from_phones(phones_info, tex_file_path, image_paths):#TeXファイルをテンプレートを基に生成する
    """
    phones_infoリストからデータを取得し、Jinja2テンプレートに埋め込んでTeXファイルを生成する
    :param phones_info: 各phoneの情報を含む辞書のリスト
    :param template_file_path: 出力されるTeXファイルのパス
    :param output_path: 出力されるTeXファイルのパス
    """
    # Jinja2テンプレート環境の設定
    template_dir= './'
    template_file = 'catalog_template.tex'
    jinja_env = Environment(
        loader=FileSystemLoader(template_dir, encoding='utf8'),
        variable_start_string='[[',
        variable_end_string=']]',
        )

    # テンプレートファイルのロード
    template = jinja_env.get_template(template_file)

    formatted_phones_info = {}#TeXファイルに埋め込むデータを格納する辞書

    #日時の設定
    current_date = datetime.now()
    formatted_date = current_date.strftime("生成日: %Y-%m-%d")
    formatted_phones_info.update({"date":formatted_date})
    
    # テンプレートに埋め込むデータをphones_infoから取得する
    phone_num=1
    for phone in phones_info:
        # 特徴タイトルを分割し、リストに変換する
        features = phone['特徴タイトル'].split('@#$%^')

        formatted_phones_info.update({
            f'image{phone_num}': image_paths[phone_num-1],
            f'url{phone_num}': phone['URL'],
            f'name{phone_num}': phone['機種'],
            f'description{phone_num}1': features[0],
            f'description{phone_num}2': features[1],
            f'description{phone_num}3': features[2],
            f'size{phone_num}': phone['画面サイズ'],
            f'backcamera{phone_num}': phone['背面カメラ画素数'],
            f'frontcamera{phone_num}': phone['前面カメラ画素数'],
            f'CPU{phone_num}': phone['CPU'],
            f'compelling{phone_num}1': phone['compelling1'],
            f'compelling{phone_num}2': phone['compelling2'],
            f'compelling{phone_num}3': phone['compelling3'],
            f'review{phone_num}1': '',  # レビュー情報が提供されていないため空白
            f'review{phone_num}2': '',  # 同上
            f'lprice{phone_num}': phone['最低価格(円)'],
            f'hprice{phone_num}': phone['最高価格(円)'],
        })
        phone_num+=1

    # テンプレートにデータを埋め込む
    rendered_content = template.render(formatted_phones_info)

    # 完成したTeXファイルを保存する
    with open(tex_file_path, 'w') as f:
        f.write(rendered_content)

def get_images(phones_info):#S3から製品画像を取得する
    image_paths = []
    bucket_name = 'llm-chatbot-s3'
    for phone in phones_info:
        s3_image_name = phone['機種']
        local_image_name = '/tmp/'+phone['機種']+'.jpg'
        try:
            s3_resource = boto3.resource('s3')
            filtered_objects = s3_resource.Bucket(bucket_name).objects.filter(Prefix=s3_image_name)
            objects = list(filtered_objects)
            if objects:
                s3_image_name = objects[0].key
            else:
                s3_image_name = 'noimage.jpg'
            print("s3_image_name:"+s3_image_name)
            s3_client = boto3.client('s3')
            s3_client.download_file(bucket_name, s3_image_name, local_image_name)
        except Exception as e:#画像がない場合はnoimageを代わりに表示する
            print(f"エラーが発生しました: {e}")
            local_image_name = '/var/task/noimage.jpg'
        image_paths.append(local_image_name)
    return image_paths
    




def handler(event, context):
    file_id ="スマホ紹介"+event['userId']#ファイル名にユーザーIDを含めることで検索しやすくする
    bucket_name = 'pdf-tex'

    out_dir = '/tmp/'#PDFとTEXは/tmp/(lambdaでWriteが唯一できる場所)に保存する
    tex_file_path = os.path.join(out_dir, f'{file_id}.tex')
    pdf_file_path = os.path.join(out_dir, f'{file_id}.pdf')
    file_name_in_s3 = f'{file_id}.pdf'
    file_name_in_s3_2 = f'{file_id}.tex'

    image_paths=get_images(event['phone_info_with_compelling'])
    render_tex_from_phones(event['phone_info_with_compelling'], tex_file_path, image_paths)
    
    pdf_generate_command = [#TeXファイルをコンパイルしてPDFを生成するコマンド
        "bash",
        "pdf_generate.sh",
        tex_file_path
    ]
    print("PDF生成開始")
    try:
        result = subprocess.run(pdf_generate_command, stdout=subprocess.PIPE , stderr=subprocess.PIPE ,encoding="utf-8")
        if result.returncode == 0:
            print("PDF生成成功")
            s3_client = boto3.client('s3')
            s3_client.upload_file(pdf_file_path, bucket_name, file_name_in_s3,ExtraArgs={'ContentType': 'application/pdf' })#PDFをS3にアップロード
            s3_client = boto3.client('s3')
            s3_client.upload_file(tex_file_path, bucket_name, file_name_in_s3_2)#TeXをS3にアップロード
            send_pdf_to_line(event['input_text'],event)#PDFをLineで送信するラムダ関数を呼び出す
        else:
            print("PDF生成失敗")
            print(result.stdout)
            s3_client = boto3.client('s3')
            s3_client.upload_file(tex_file_path, bucket_name, file_name_in_s3_2)#TeXをS3にアップロード
            send_text_to_line("申し訳ありません。PDF生成中にエラーが発生しており、ただいま結果を表示することができません。",event)
    except Exception as e:
        print(f"エラーが発生しました: {e}")
        send_text_to_line("申し訳ありません。PDF生成中にエラーが発生しており、ただいま結果を表示することができません。",event)#エラー時にテキストをLineで送信するラムダ関数を呼び出す

    return 'This is pdf-tex-generater!'
#handler("","")
