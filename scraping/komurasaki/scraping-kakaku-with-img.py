import json
import requests
from bs4 import BeautifulSoup
import boto3
import time

import io
import base64
BUCKET_NAME="llm-chatbot-s3"

def get_img_from_s3():
    s3 = boto3.client('s3')
    responce = s3.get_object(Bucket=BUCKET_NAME, Key= OBJECT_KEY_NAME)
    body = responce['Body'].read()
    body = base64.b64encode(body)
    return body
def upload_img_to_s3_from_url(url,object_name):
    # 画像をダウンロード
    res = requests.get(url)
    res.raise_for_status()
    # 取得したバイナリデータをファイルオブジェクトに変換
    img = io.BytesIO(res.content)
    print(res.content.__sizeof__())
    if int(res.content.__sizeof__()) < 1.0*1024*1024:#1MB基準
        # S3にアップロード
        s3 = boto3.client('s3')
        s3.upload_fileobj(img, BUCKET_NAME, object_name)
    

# DynamoDBテーブルの名前
dynamodb_table_name = 'komurasaki-test'

# DynamoDBリソースの作成
dynamodb = boto3.resource('dynamodb')
dynamo_table = dynamodb.Table(dynamodb_table_name)

def lambda_handler(event, context):
    #何機種とるか(テスト時の制限)
    max_get_number=5
    # スマホのランキングのURLのリストmother_urlを作成 (1, 13)と(13, 25)で分割すると良い
    mother_url = ['https://kakaku.com/keitai/smartphone/?pdf_Spec030=1&pdf_pg=' + str(i) for i in range(13, 25)]

    # 機種スペック項目を取得
    response = requests.get('https://kakaku.com/keitai/smartphone/model/M0000001005/spec/')
    soup = BeautifulSoup(response.text, 'html.parser')
    elemsItem = soup.find_all(class_="p-hikakuTbl-name")
    #textを抽出
    elemsItemText = [elemsItem[i - 1].text for i in range(1, len(elemsItem) + 1)]
    #「機種」を追加
    new_elemsItemText = ['機種'] + elemsItemText+['href(img-file-name)']
        
    # 1秒待機
    time.sleep(1) 

    
    # 各URLから機種スペックのデータを取得し、DynamoDBに追加
    for url in mother_url:
        #mother_urlの要素を取得
        response = requests.get(url)
        #機種ランキングのページにある個々のスマホのurlを取得
        soup = BeautifulSoup(response.text, 'html.parser')
        elems = soup.find_all(class_="s-biggerlinkBigger")
        href_values = [elem.get('href') for elem in elems]#hrefの値を取得
        full_urls = ['https://kakaku.com/' + href_value + '/spec/' for href_value in href_values]#取得したhrefの値から個々のスマホのスペック表のページのurlを生成

        for full_url in full_urls:
            max_get_number = max_get_number-1
            if max_get_number < 0:
                break
            response = requests.get(full_url)
            soup = BeautifulSoup(response.text, 'html.parser')
            elemsName = soup.find_all(class_="p-hikakuTbl_item-name")#機種名
            elemsSpec = soup.find_all(class_="p-data_cell")#スペックの内容
            imgSrc = soup.find_all(class_="p-main_thumb-main-img")[0]["src"]#imgのSrc
            
            # SIMフリーの数を初期化
            sim_free_count = 0

            # 各要素のテキストを調べてSIMフリーの数を数える
            for element in elemsName:
                text = element.get_text()
                if "SIMフリー" in text:
                    sim_free_count += 1

            if elems and elemsSpec:#ストレージの種類の数は３つ以下と仮定．
                if len(elemsName) == 1:#1機種しかない場合
                    elemsPhone= [elemsName[0].text] +[elemsSpec[i - 1].text for i in range(1, len(elemsSpec) + 1)]
                    # DynamoDBにデータを追加（存在すれば更新）
                    dynamo_item = {new_elemsItemText[i]: elemsPhone[i] for i in range(len(new_elemsItemText)-1)}
                    dynamo_table.put_item(Item=dynamo_item)
                    upload_img_to_s3_from_url(imgSrc,elemsName[0].text)
                    print("追加完了: " + elemsName[0].text)

                elif sim_free_count == 1:#SIMフリーの機種でストレージの種類が１つのみ
                    elemsPhone = [elemsName[0].text] +[elemsSpec[i - 1].text for i in range(1, len(elemsSpec) + 1) if i % len(elemsName) == 1]
                    # DynamoDBにデータを追加（存在すれば更新）
                    dynamo_item = {new_elemsItemText[i]: elemsPhone[i] for i in range(len(new_elemsItemText)-1)}
                    dynamo_table.put_item(Item=dynamo_item)
                    upload_img_to_s3_from_url(imgSrc,elemsName[0].text)
                    print("追加完了: " + elemsName[0].text)

                elif sim_free_count == 2:#SIMフリーの機種でストレージの種類が２つのみ
                    if len(elemsName) == 2:
                        elemsPhone = [elemsName[0].text] +[elemsSpec[i - 1].text for i in range(1, len(elemsSpec) + 1) if i % len(elemsName) == 1]
                        elemsPhone1 = [elemsName[1].text] +[elemsSpec[j - 1].text for j in range(1, len(elemsSpec) + 1) if j % len(elemsName) == 0]
                        # DynamoDBにデータを追加（存在すれば更新）
                        dynamo_item = {new_elemsItemText[i]: elemsPhone[i] for i in range(len(new_elemsItemText)-1)}
                        dynamo_table.put_item(Item=dynamo_item)
                        upload_img_to_s3_from_url(imgSrc,elemsName[0].text)
                        print("追加完了: " + elemsName[0].text)
                        # DynamoDBにデータを追加（存在すれば更新）
                        dynamo_item = {new_elemsItemText[i]: elemsPhone1[i] for i in range(len(new_elemsItemText)-1)}
                        dynamo_table.put_item(Item=dynamo_item)
                        upload_img_to_s3_from_url(imgSrc,elemsName[1].text)
                        print("追加完了: " + elemsName[1].text)
                    else:
                        elemsPhone = [elemsName[0].text] +[elemsSpec[i - 1].text for i in range(1, len(elemsSpec) + 1) if i % len(elemsName) == 1]
                        elemsPhone1 = [elemsName[1].text] +[elemsSpec[j - 1].text for j in range(1, len(elemsSpec) + 1) if j % len(elemsName) == 2]
                        # DynamoDBにデータを追加（存在すれば更新）
                        dynamo_item = {new_elemsItemText[i]: elemsPhone[i] for i in range(len(new_elemsItemText)-1)}
                        dynamo_table.put_item(Item=dynamo_item)
                        upload_img_to_s3_from_url(imgSrc,elemsName[0].text)
                        print("追加完了: " + elemsName[0].text)
                        # DynamoDBにデータを追加（存在すれば更新）
                        dynamo_item = {new_elemsItemText[i]: elemsPhone1[i] for i in range(len(new_elemsItemText)-1)}
                        dynamo_table.put_item(Item=dynamo_item)
                        upload_img_to_s3_from_url(imgSrc,elemsName[1].text)
                        print("追加完了: " + elemsName[1].text)

                elif sim_free_count == 3:#SIMフリーの機種でストレージの種類が３つのみ
                    if len(elemsName) == 3:
                        elemsPhone = [elemsName[0].text] +[elemsSpec[i-1].text for i in range(1, len(elemsSpec) + 1) if i % len(elemsName) == 1]
                        elemsPhone1 = [elemsName[1].text] +[elemsSpec[j-1].text for j in range(1, len(elemsSpec) + 1) if j % len(elemsName) == 2]
                        elemsPhone2 = [elemsName[2].text] +[elemsSpec[k-1].text for k in range(1, len(elemsSpec) + 1) if k % len(elemsName) == 0]
                        # DynamoDBにデータを追加（存在すれば更新）
                        dynamo_item = {new_elemsItemText[i]: elemsPhone[i] for i in range(len(new_elemsItemText)-1)}
                        dynamo_table.put_item(Item=dynamo_item)
                        upload_img_to_s3_from_url(imgSrc,elemsName[0].text)
                        print("追加完了: " + elemsName[0].text)
                        # DynamoDBにデータを追加（存在すれば更新）
                        dynamo_item = {new_elemsItemText[i]: elemsPhone1[i] for i in range(len(new_elemsItemText)-1)}
                        dynamo_table.put_item(Item=dynamo_item)
                        upload_img_to_s3_from_url(imgSrc,elemsName[1].text)
                        print("追加完了: " + elemsName[1].text)
                        # DynamoDBにデータを追加（存在すれば更新）
                        dynamo_item = {new_elemsItemText[i]: elemsPhone2[i] for i in range(len(new_elemsItemText)-1)}
                        dynamo_table.put_item(Item=dynamo_item)
                        upload_img_to_s3_from_url(imgSrc,elemsName[2].text)
                        print("追加完了: " + elemsName[2].text)
                    else:
                        elemsPhone = [elemsName[0].text] +[elemsSpec[i-1].text for i in range(1, len(elemsSpec) + 1) if i % len(elemsName) == 1]
                        elemsPhone1 = [elemsName[1].text] +[elemsSpec[j-1].text for j in range(1, len(elemsSpec) + 1) if j % len(elemsName) == 2]
                        elemsPhone2 = [elemsName[2].text] +[elemsSpec[k-1].text for k in range(1, len(elemsSpec) + 1) if k % len(elemsName) == 3]
                        # DynamoDBにデータを追加（存在すれば更新）
                        dynamo_item = {new_elemsItemText[i]: elemsPhone[i] for i in range(len(new_elemsItemText)-1)}
                        dynamo_table.put_item(Item=dynamo_item)
                        upload_img_to_s3_from_url(imgSrc,elemsName[0].text)
                        print("追加完了: " + elemsName[0].text)
                        # DynamoDBにデータを追加（存在すれば更新）
                        dynamo_item = {new_elemsItemText[i]: elemsPhone1[i] for i in range(len(new_elemsItemText)-1)}
                        dynamo_table.put_item(Item=dynamo_item)
                        upload_img_to_s3_from_url(imgSrc,elemsName[1].text)
                        print("追加完了: " + elemsName[1].text)
                        # DynamoDBにデータを追加（存在すれば更新）
                        dynamo_item = {new_elemsItemText[i]: elemsPhone2[i] for i in range(len(new_elemsItemText)-1)}
                        dynamo_table.put_item(Item=dynamo_item)
                        upload_img_to_s3_from_url(imgSrc,elemsName[2].text)
                        print("追加完了: " + elemsName[2].text)

                else:
                    result = []
            
            else:
                print(f"機種スペックのデータが存在しないため、スキップ: {full_url}")
            
            # 1秒待機
            time.sleep(1)
    

    return {
        'statusCode': 200,
        'body': json.dumps('Successfully completed.')#終了宣言
    }
