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

def upload_img_to_s3_from_url(url, object_name):
    try:
        # 画像をダウンロード
        res = requests.get(url)
        res.raise_for_status()
        
        # 取得したバイナリデータをファイルオブジェクトに変換
        img = io.BytesIO(res.content)
        print(res.content.__sizeof__())
        
        if int(res.content.__sizeof__()) < 1.0 * 1024 * 1024:  # 1MB基準
            # S3にアップロード
            s3 = boto3.client('s3')
            s3.upload_fileobj(img, BUCKET_NAME, object_name)
        
    except requests.exceptions.RequestException as e:
        # URLが存在しない場合やダウンロードできない場合の例外を捕捉
        print(f"Error: {e}")

# DynamoDBテーブルの名前
dynamodb_table_name = 'ScrapingPhoneStatus'

# DynamoDBリソースの作成
dynamodb = boto3.resource('dynamodb')
dynamo_table = dynamodb.Table(dynamodb_table_name)

def extract_text_from_elements(elements):
    return [element.text for element in elements]#テキストデータを取得

def lambda_handler(event, context):
    
    try:
        # スマホのランキングのURLのリストmother_urlを作成 (1, 13)と(13, 25)で分割すると良い
        mother_url = ['https://kakaku.com/keitai/smartphone/?pdf_Spec030=1&pdf_pg=' + str(i) for i in range(1, 13)]
        
        # # 機種スペック項目を取得
        # response = requests.get('https://kakaku.com/keitai/smartphone/model/M0000001005/spec/')
        # soup = BeautifulSoup(response.text, 'html.parser')
        # elemsItem = soup.find_all(class_="p-hikakuTbl-name")
        # #textを抽出
        # elemsItemText = [elemsItem[i - 1].text for i in range(1, len(elemsItem) + 1)]
        #「機種」を追加
        new_elemsItemText = ["機種", "発売日", "OS種類?", "CPU", "CPUコア数", "内蔵メモリ(ROM)?", "内蔵メモリ(RAM)", "充電器・充電ケーブル", "外部メモリタイプ", "外部メモリ最大容量", "バッテリー容量", "画面サイズ", "画面解像度", "パネル種類", "背面カメラ画素数", "前面カメラ画素数", "手ブレ補正", "4K撮影対応?", "スローモーション撮影", "撮影用フラッシュ", "複数レンズ", "幅", "高さ", "厚み", "重量", "カラー", "おサイフケータイ/FeliCa", "ワイヤレス充電(Qi)?", "急速充電", "認証機能", "耐水・防水", "防塵", "MIL規格?", "イヤホンジャック", "HDMI端子", "MHL?", "フルセグ", "ワンセグ", "ハイレゾ", "GPS", "センサー", "5G?", "4G・LTE", "無線LAN規格", "テザリング対応?", "Bluetooth", "NFC?", "赤外線通信機能", "デュアルSIM?", "デュアルSIMデュアルスタンバイ(DSDS)?", "デュアルSIMデュアルVoLTE(DSDV)?", "SIM情報", "URL", "特徴タイトル", "特徴本文", "最低価格(円)", "最高価格(円)", "その他の特徴タイトル", "その他の特徴本文"]
        
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
            full_urls1 = ['https://kakaku.com/' + href_value for href_value in href_values]

            url_count = 0
            for full_url in full_urls:
                try:
                    response = requests.get(full_url)#full_urlsのi番目の情報
                    soup = BeautifulSoup(response.text, 'html.parser')
                    response1 = requests.get(full_urls1[url_count])#full_urls1のi番目の情報
                    soup1 = BeautifulSoup(response1.text, 'html.parser')
                    
                    elemsName = soup.find_all(class_="p-hikakuTbl_item-name")#機種名
                    
                    print(elemsName[0].text)#確認用
                    
                    elemsSpec = soup.find_all(class_="p-data_cell")#スペックの内容
                    elemsFeatureTitle = soup.find_all(class_="p-feature_ttl")#特徴のタイトル
                    elemsFeatureSent = soup.find_all(class_="p-feature_readTxt")#特徴の文
                    elemsExtraFeatureTitle = soup.select('.p-spec_table.p-feature_aside_table th')#その他の特徴のタイトル
                    elemsExtraFeatureSent = soup.select('.p-spec_table.p-feature_aside_table td')#その他の特徴の文
                    min_price_element = soup1.find(class_='p-device_main_price')
                    # main_price_element内のclassがp-numの要素を取得
                    elemsMinPrice = min_price_element.find(class_='p-num')
                    max_price_element = soup1.find(class_='p-device_main_price_min')
                    elemsMaxPrice = max_price_element.find(class_='p-num')
                    imgSrc = soup.find_all(class_="p-main_thumb-main-img")[0]["src"]#imgのSrc
                    elemsFeatureTitle.pop()#リスト最後の要素が「その他の要素」であるためこれを削除
                    elemsFeatureTitle=['@#$%^'.join(extract_text_from_elements(elemsFeatureTitle))]
                    elemsFeatureSent=['@#$%^'.join(extract_text_from_elements(elemsFeatureSent))]
                    elemsExtraFeatureTitle=['@#$%^'.join(extract_text_from_elements(elemsExtraFeatureTitle))]
                    elemsExtraFeatureSent=['@#$%^'.join(extract_text_from_elements(elemsExtraFeatureSent))]
                    
                    # SIMフリーの数を初期化
                    sim_free_count = 0
                    # 各要素のテキストを調べてSIMフリーの数を数える
                    for element in elemsName:
                            text = element.get_text()
                            if "SIMフリー" in text:
                                sim_free_count += 1
                                
                    if elems and elemsSpec:#ストレージの種類の数は３つ以下と仮定．容量が違う同じ機種のスマホは別のスマホとしてDBに保存
                        if len(elemsName) == 1:#1機種しかない場合
                            elemsPhone= [elemsName[0].text] +[elemsSpec[i - 1].text for i in range(1, len(elemsSpec) + 1)]
                            # リスト内包表記を使用して'\n ○ \n'を'対応'に変換
                            elemsPhone = ['対応' if elem == '\n○\n'  else elem for elem in elemsPhone]
                            elemsPhone.append(full_url)
                            elemsPhone=elemsPhone+ elemsFeatureTitle + elemsFeatureSent+[elemsMinPrice.text]+[elemsMaxPrice.text]+elemsExtraFeatureTitle + elemsExtraFeatureSent
                            # DynamoDBにデータを追加（存在すれば更新）
                            dynamo_item = {new_elemsItemText[i]: elemsPhone[i] for i in range(len(new_elemsItemText))}
                            dynamo_table.put_item(Item=dynamo_item)
                            upload_img_to_s3_from_url(imgSrc,elemsName[0].text)
                            print("追加完了: " + elemsName[0].text)
                            url_count += 1
                        elif sim_free_count == 1:#SIMフリーの機種でストレージの種類が１つのみ
                            elemsPhone = [elemsName[0].text] +[elemsSpec[i - 1].text for i in range(1, len(elemsSpec)+1) if i % len(elemsName) == 1]
                            # リスト内包表記を使用して'\n ○ \n'を'対応'に変換
                            elemsPhone = ['対応' if elem == '\n○\n'  else elem for elem in elemsPhone]
                            elemsPhone.append(full_url)
                            elemsPhone=elemsPhone+ elemsFeatureTitle + elemsFeatureSent+[elemsMinPrice.text]+[elemsMaxPrice.text]+elemsExtraFeatureTitle + elemsExtraFeatureSent
                            # DynamoDBにデータを追加（存在すれば更新）
                            dynamo_item = {new_elemsItemText[i]: elemsPhone[i] for i in range(len(new_elemsItemText))}
                            dynamo_table.put_item(Item=dynamo_item)
                            upload_img_to_s3_from_url(imgSrc,elemsName[0].text)
                            print("追加完了: " + elemsName[0].text)
                            url_count += 1
                            
                        elif sim_free_count == 2:#SIMフリーの機種でストレージの種類が２つのみ
                            if len(elemsName) == 2:
                                elemsPhone = [elemsName[0].text] +[elemsSpec[i - 1].text for i in range(1, len(elemsSpec) + 1) if i % len(elemsName) == 1]
                                elemsPhone1 = [elemsName[1].text] +[elemsSpec[j - 1].text for j in range(1, len(elemsSpec) + 1) if j % len(elemsName) == 0]
                                elemsPhone = ['対応' if elem == '\n○\n'  else elem for elem in elemsPhone]
                                elemsPhone1 = ['対応' if elem == '\n○\n'  else elem for elem in elemsPhone1]
                                elemsPhone.append(full_url)
                                elemsPhone1.append(full_url)
                                elemsPhone=elemsPhone+ elemsFeatureTitle + elemsFeatureSent+[elemsMinPrice.text]+[elemsMaxPrice.text]+elemsExtraFeatureTitle + elemsExtraFeatureSent
                                elemsPhone1=elemsPhone1+ elemsFeatureTitle + elemsFeatureSent+[elemsMinPrice.text]+[elemsMaxPrice.text]+elemsExtraFeatureTitle + elemsExtraFeatureSent
                                # DynamoDBにデータを追加（存在すれば更新）
                                dynamo_item = {new_elemsItemText[i]: elemsPhone[i] for i in range(len(new_elemsItemText))}
                                dynamo_table.put_item(Item=dynamo_item)
                                upload_img_to_s3_from_url(imgSrc,elemsName[0].text)
                                print("追加完了: " + elemsName[0].text)
                                # DynamoDBにデータを追加（存在すれば更新）
                                dynamo_item = {new_elemsItemText[i]: elemsPhone1[i] for i in range(len(new_elemsItemText))}
                                dynamo_table.put_item(Item=dynamo_item)
                                upload_img_to_s3_from_url(imgSrc,elemsName[1].text)
                                print("追加完了: " + elemsName[1].text)
                                url_count += 1
                            else:
                                elemsPhone = [elemsName[0].text] +[elemsSpec[i - 1].text for i in range(1, len(elemsSpec) + 1) if i % len(elemsName) == 1]
                                elemsPhone1 = [elemsName[1].text] +[elemsSpec[j - 1].text for j in range(1, len(elemsSpec) + 1) if j % len(elemsName) == 2]                                
                                # リスト内包表記を使用して'\n ○ \n'を'対応'に変換
                                elemsPhone = ['対応' if elem == '\n○\n'  else elem for elem in elemsPhone]
                                elemsPhone1 = ['対応' if elem == '\n○\n'  else elem for elem in elemsPhone1]
                                elemsPhone.append(full_url)
                                elemsPhone1.append(full_url)
                                elemsPhone=elemsPhone+ elemsFeatureTitle + elemsFeatureSent+[elemsMinPrice.text]+[elemsMaxPrice.text]+elemsExtraFeatureTitle + elemsExtraFeatureSent
                                elemsPhone1=elemsPhone1+ elemsFeatureTitle + elemsFeatureSent+[elemsMinPrice.text]+[elemsMaxPrice.text]+elemsExtraFeatureTitle + elemsExtraFeatureSent
                                # DynamoDBにデータを追加（存在すれば更新）
                                dynamo_item = {new_elemsItemText[i]: elemsPhone[i] for i in range(len(new_elemsItemText))}
                                dynamo_table.put_item(Item=dynamo_item)
                                upload_img_to_s3_from_url(imgSrc,elemsName[0].text)
                                print("追加完了: " + elemsName[0].text)
                                # DynamoDBにデータを追加（存在すれば更新）
                                dynamo_item = {new_elemsItemText[i]: elemsPhone1[i] for i in range(len(new_elemsItemText))}
                                dynamo_table.put_item(Item=dynamo_item)
                                upload_img_to_s3_from_url(imgSrc,elemsName[1].text)
                                print("追加完了: " + elemsName[1].text)
                                url_count += 1
                                
                        elif sim_free_count == 3:#SIMフリーの機種でストレージの種類が３つのみ
                            if len(elemsName) == 3:
                                elemsPhone = [elemsName[0].text] +[elemsSpec[i-1].text for i in range(1, len(elemsSpec) + 1) if i % len(elemsName) == 1]
                                elemsPhone1 = [elemsName[1].text] +[elemsSpec[j-1].text for j in range(1, len(elemsSpec) + 1) if j % len(elemsName) == 2]
                                elemsPhone2 = [elemsName[2].text] +[elemsSpec[k-1].text for k in range(1, len(elemsSpec) + 1) if k % len(elemsName) == 0]
                                # リスト内包表記を使用して'\n ○ \n'を'対応'に変換
                                elemsPhone = ['対応' if elem == '\n○\n'  else elem for elem in elemsPhone]
                                elemsPhone1 = ['対応' if elem == '\n○\n'  else elem for elem in elemsPhone1]
                                elemsPhone2 = ['対応' if elem == '\n○\n'  else elem for elem in elemsPhone2]
                                elemsPhone.append(full_url)
                                elemsPhone1.append(full_url)
                                elemsPhone2.append(full_url)
                                elemsPhone=elemsPhone+ elemsFeatureTitle + elemsFeatureSent+[elemsMinPrice.text]+[elemsMaxPrice.text]+elemsExtraFeatureTitle + elemsExtraFeatureSent
                                elemsPhone1=elemsPhone1+ elemsFeatureTitle + elemsFeatureSent+[elemsMinPrice.text]+[elemsMaxPrice.text]+elemsExtraFeatureTitle + elemsExtraFeatureSent
                                elemsPhone2=elemsPhone2+ elemsFeatureTitle + elemsFeatureSent+[elemsMinPrice.text]+[elemsMaxPrice.text]+elemsExtraFeatureTitle + elemsExtraFeatureSent
                                # DynamoDBにデータを追加（存在すれば更新）
                                dynamo_item = {new_elemsItemText[i]: elemsPhone[i] for i in range(len(new_elemsItemText))}
                                dynamo_table.put_item(Item=dynamo_item)
                                upload_img_to_s3_from_url(imgSrc,elemsName[0].text)
                                print("追加完了: " + elemsName[0].text)
                                # DynamoDBにデータを追加（存在すれば更新）
                                dynamo_item = {new_elemsItemText[i]: elemsPhone1[i] for i in range(len(new_elemsItemText))}
                                dynamo_table.put_item(Item=dynamo_item)
                                upload_img_to_s3_from_url(imgSrc,elemsName[1].text)
                                print("追加完了: " + elemsName[1].text)
                                # DynamoDBにデータを追加（存在すれば更新）
                                dynamo_item = {new_elemsItemText[i]: elemsPhone2[i] for i in range(len(new_elemsItemText))}
                                dynamo_table.put_item(Item=dynamo_item)
                                upload_img_to_s3_from_url(imgSrc,elemsName[2].text)
                                print("追加完了: " + elemsName[2].text)
                                url_count += 1
                            else:
                                elemsPhone = [elemsName[0].text] +[elemsSpec[i-1].text for i in range(1, len(elemsSpec) + 1) if i % len(elemsName) == 1]
                                elemsPhone1 = [elemsName[1].text] +[elemsSpec[j-1].text for j in range(1, len(elemsSpec) + 1) if j % len(elemsName) == 2]
                                elemsPhone2 = [elemsName[2].text] +[elemsSpec[k-1].text for k in range(1, len(elemsSpec) + 1) if k % len(elemsName) == 3]
                                elemsPhone = ['対応' if elem == '\n○\n'  else elem for elem in elemsPhone]
                                elemsPhone1 = ['対応' if elem == '\n○\n'  else elem for elem in elemsPhone1]
                                elemsPhone2 = ['対応' if elem == '\n○\n'  else elem for elem in elemsPhone2]
                                elemsPhone.append(full_url)
                                elemsPhone1.append(full_url)
                                elemsPhone2.append(full_url)
                                elemsPhone=elemsPhone+ elemsFeatureTitle + elemsFeatureSent+[elemsMinPrice.text]+[elemsMaxPrice.text]+elemsExtraFeatureTitle + elemsExtraFeatureSent
                                elemsPhone1=elemsPhone1+ elemsFeatureTitle + elemsFeatureSent+[elemsMinPrice.text]+[elemsMaxPrice.text]+elemsExtraFeatureTitle + elemsExtraFeatureSent
                                elemsPhone2=elemsPhone2+ elemsFeatureTitle + elemsFeatureSent+[elemsMinPrice.text]+[elemsMaxPrice.text]+elemsExtraFeatureTitle + elemsExtraFeatureSent
                                # DynamoDBにデータを追加（存在すれば更新）
                                dynamo_item = {new_elemsItemText[i]: elemsPhone[i] for i in range(len(new_elemsItemText))}
                                dynamo_table.put_item(Item=dynamo_item)
                                upload_img_to_s3_from_url(imgSrc,elemsName[0].text)
                                print("追加完了: " + elemsName[0].text)
                                # DynamoDBにデータを追加（存在すれば更新）
                                dynamo_item = {new_elemsItemText[i]: elemsPhone1[i] for i in range(len(new_elemsItemText))}
                                dynamo_table.put_item(Item=dynamo_item)
                                upload_img_to_s3_from_url(imgSrc,elemsName[1].text)
                                print("追加完了: " + elemsName[1].text)
                                # DynamoDBにデータを追加（存在すれば更新）
                                dynamo_item = {new_elemsItemText[i]: elemsPhone2[i] for i in range(len(new_elemsItemText))}
                                dynamo_table.put_item(Item=dynamo_item)
                                upload_img_to_s3_from_url(imgSrc,elemsName[2].text)
                                print("追加完了: " + elemsName[2].text)
                                url_count += 1
                            
                        elif sim_free_count == 4:#SIMフリーの機種でストレージの種類が３つのみ
                            if len(elemsName) == 4:
                                elemsPhone = [elemsName[0].text] +[elemsSpec[i-1].text for i in range(1, len(elemsSpec) + 1) if i % len(elemsName) == 1]
                                elemsPhone1 = [elemsName[1].text] +[elemsSpec[j-1].text for j in range(1, len(elemsSpec) + 1) if j % len(elemsName) == 2]
                                elemsPhone2 = [elemsName[2].text] +[elemsSpec[k-1].text for k in range(1, len(elemsSpec) + 1) if k % len(elemsName) == 3]
                                elemsPhone3 = [elemsName[3].text] +[elemsSpec[i-1].text for i in range(1, len(elemsSpec) + 1) if i % len(elemsName) == 0]
                                # リスト内包表記を使用して'\n ○ \n'を'対応'に変換
                                elemsPhone = ['対応' if elem == '\n○\n'  else elem for elem in elemsPhone]
                                elemsPhone1 = ['対応' if elem == '\n○\n'  else elem for elem in elemsPhone1]
                                elemsPhone2 = ['対応' if elem == '\n○\n'  else elem for elem in elemsPhone2]
                                elemsPhone3 = ['対応' if elem == '\n○\n'  else elem for elem in elemsPhone3]
                                elemsPhone.append(full_url)
                                elemsPhone1.append(full_url)
                                elemsPhone2.append(full_url)
                                elemsPhone3.append(full_url)
                                elemsPhone=elemsPhone+ elemsFeatureTitle + elemsFeatureSent+[elemsMinPrice.text]+[elemsMaxPrice.text]+elemsExtraFeatureTitle + elemsExtraFeatureSent
                                elemsPhone1=elemsPhone1+ elemsFeatureTitle + elemsFeatureSent+[elemsMinPrice.text]+[elemsMaxPrice.text]+elemsExtraFeatureTitle + elemsExtraFeatureSent
                                elemsPhone2=elemsPhone2+ elemsFeatureTitle + elemsFeatureSent+[elemsMinPrice.text]+[elemsMaxPrice.text]+elemsExtraFeatureTitle + elemsExtraFeatureSent
                                elemsPhone3=elemsPhone3+ elemsFeatureTitle + elemsFeatureSent+[elemsMinPrice.text]+[elemsMaxPrice.text]+elemsExtraFeatureTitle + elemsExtraFeatureSent
                                # DynamoDBにデータを追加（存在すれば更新）
                                dynamo_item = {new_elemsItemText[i]: elemsPhone[i] for i in range(len(new_elemsItemText))}
                                dynamo_table.put_item(Item=dynamo_item)
                                upload_img_to_s3_from_url(imgSrc,elemsName[0].text)
                                print("追加完了: " + elemsName[0].text)
                                # DynamoDBにデータを追加（存在すれば更新）
                                dynamo_item = {new_elemsItemText[i]: elemsPhone1[i] for i in range(len(new_elemsItemText))}
                                dynamo_table.put_item(Item=dynamo_item)
                                upload_img_to_s3_from_url(imgSrc,elemsName[1].text)
                                print("追加完了: " + elemsName[1].text)
                                # DynamoDBにデータを追加（存在すれば更新）
                                dynamo_item = {new_elemsItemText[i]: elemsPhone2[i] for i in range(len(new_elemsItemText))}
                                dynamo_table.put_item(Item=dynamo_item)
                                upload_img_to_s3_from_url(imgSrc,elemsName[2].text)
                                print("追加完了: " + elemsName[2].text)
                                dynamo_item = {new_elemsItemText[i]: elemsPhone3[i] for i in range(len(new_elemsItemText))}
                                dynamo_table.put_item(Item=dynamo_item)
                                upload_img_to_s3_from_url(imgSrc,elemsName[3].text)
                                print("追加完了: " + elemsName[3].text)
                                url_count += 1
                            else:
                                elemsPhone = [elemsName[0].text] +[elemsSpec[i-1].text for i in range(1, len(elemsSpec) + 1) if i % len(elemsName) == 1]
                                elemsPhone1 = [elemsName[1].text] +[elemsSpec[j-1].text for j in range(1, len(elemsSpec) + 1) if j % len(elemsName) == 2]
                                elemsPhone2 = [elemsName[2].text] +[elemsSpec[k-1].text for k in range(1, len(elemsSpec) + 1) if k % len(elemsName) == 3]
                                elemsPhone3 = [elemsName[3].text] +[elemsSpec[i-1].text for i in range(1, len(elemsSpec) + 1) if i % len(elemsName) == 4]
                                elemsPhone = ['対応' if elem == '\n○\n'  else elem for elem in elemsPhone]
                                elemsPhone1 = ['対応' if elem == '\n○\n'  else elem for elem in elemsPhone1]
                                elemsPhone2 = ['対応' if elem == '\n○\n'  else elem for elem in elemsPhone2]
                                elemsPhone3 = ['対応' if elem == '\n○\n'  else elem for elem in elemsPhone3]
                                elemsPhone.append(full_url)
                                elemsPhone1.append(full_url)
                                elemsPhone2.append(full_url)
                                elemsPhone3.append(full_url)
                                elemsPhone=elemsPhone+ elemsFeatureTitle + elemsFeatureSent+[elemsMinPrice.text]+[elemsMaxPrice.text]+elemsExtraFeatureTitle + elemsExtraFeatureSent
                                elemsPhone1=elemsPhone1+ elemsFeatureTitle + elemsFeatureSent+[elemsMinPrice.text]+[elemsMaxPrice.text]+elemsExtraFeatureTitle + elemsExtraFeatureSent
                                elemsPhone2=elemsPhone2+ elemsFeatureTitle + elemsFeatureSent+[elemsMinPrice.text]+[elemsMaxPrice.text]+elemsExtraFeatureTitle + elemsExtraFeatureSent
                                elemsPhone3=elemsPhone3+ elemsFeatureTitle + elemsFeatureSent+[elemsMinPrice.text]+[elemsMaxPrice.text]+elemsExtraFeatureTitle + elemsExtraFeatureSent
                                # DynamoDBにデータを追加（存在すれば更新）
                                dynamo_item = {new_elemsItemText[i]: elemsPhone[i] for i in range(len(new_elemsItemText))}
                                dynamo_table.put_item(Item=dynamo_item)
                                upload_img_to_s3_from_url(imgSrc,elemsName[0].text)
                                print("追加完了: " + elemsName[0].text)
                                # DynamoDBにデータを追加（存在すれば更新）
                                dynamo_item = {new_elemsItemText[i]: elemsPhone1[i] for i in range(len(new_elemsItemText))}
                                dynamo_table.put_item(Item=dynamo_item)
                                upload_img_to_s3_from_url(imgSrc,elemsName[1].text)
                                print("追加完了: " + elemsName[1].text)
                                # DynamoDBにデータを追加（存在すれば更新）
                                dynamo_item = {new_elemsItemText[i]: elemsPhone2[i] for i in range(len(new_elemsItemText))}
                                dynamo_table.put_item(Item=dynamo_item)
                                upload_img_to_s3_from_url(imgSrc,elemsName[2].text)
                                print("追加完了: " + elemsName[2].text)
                                # DynamoDBにデータを追加（存在すれば更新）
                                dynamo_item = {new_elemsItemText[i]: elemsPhone3[i] for i in range(len(new_elemsItemText))}
                                dynamo_table.put_item(Item=dynamo_item)
                                upload_img_to_s3_from_url(imgSrc,elemsName[3].text)
                                print("追加完了: " + elemsName[3].text)
                                url_count += 1
                        else:
                            result = []
                    else:
                        print(f"機種スペックのデータが存在しないため、スキップ: {full_url}")
                    # 1秒待機
                    time.sleep(1)
                except Exception as e:
                    print('Error during processing individual phone data!')
                    print(e)
                    url_count += 1
                    # 例外が発生した場合、処理を続行
                    continue
                
    except Exception as e:
        print('Error!')
        print(e)
        raise e
        
    # 次のラムダ関数を呼び出す (-> delete_backn)
    lambda_client = boto3.client('lambda')
    #ARN of plain_text_output
    next_function_name = 'arn:aws:lambda:ap-northeast-1:105837277682:function:delete_backn'
    response = lambda_client.invoke(
        FunctionName=next_function_name,
        InvocationType='Event',
        Payload=json.dumps({})
    )
    return {
        'statusCode': 200,
        'body': json.dumps('Successfully completed.')#終了宣言
    }
