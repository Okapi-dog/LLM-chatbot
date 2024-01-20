import boto3
import json
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, parse_qs, unquote
import time

# DynamoDBからスマホの名前を取得する関数
def get_phone_names_from_dynamodb():
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('IntegratedPhoneStatus')
    
    # DynamoDBから全てのアイテムを取得
    response = table.scan()
    phone_names = [item['機種'] for item in response['Items']]
    return phone_names


# DuckDuckGoで検索して最上位のURLを取得する関数
def search_duckduckgo(query, sites):
    results = []
    for site in sites:
        # サイトごとのクエリを作成
        site_query = f"{query} site:{site}"
        
        # DuckDuckGoで検索
        url = search_single_site(site_query)
        if url:
            results.append(url)
    return results
    
# DuckDuckGoで単一のサイトを検索する関数
def search_single_site(query):
    url = f"https://duckduckgo.com/html/?q={query}"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        link = soup.find('a', class_='result__a')
        return link['href'] if link else None
    except Exception as e:
        print(f"検索中にエラーが発生しました: {e}")
        return None

# BoilerNet Lambda関数にURLを送信する関数
def send_url_to_boilernet(url):
    client = boto3.client('lambda')
    payload = {'url': url}

    # リトライ回数の設定
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = client.invoke(
                FunctionName='boilernet_with_sumy',
                InvocationType='RequestResponse',
                Payload=json.dumps(payload)
            )
            return json.loads(response['Payload'].read())
        except Exception as e:
            print(f"リトライ {attempt + 1} / {max_retries}: {e}")
            time.sleep(2 ** attempt)  # 指数的バックオフ

    raise Exception("boilernet_with_sumy の呼び出しに失敗しました")
    
#search_duckduckgoで取得したリダイレクトurlから実際のurlを作る関数
def extract_actual_url(redirect_url):
    # URL解析
    parsed_url = urlparse(redirect_url)
    query_params = parse_qs(parsed_url.query)

    # 'uddg'パラメータの値を取得し、デコード
    actual_url = query_params.get('uddg', [None])[0]
    if actual_url:
        actual_url = unquote(actual_url)
    return actual_url

def process_search_results(urls):
    results = []
    actual_urls = []

    for i, redirect_url in enumerate(urls):
        if i < 3:  # 最初の3つのURLのみ処理
            actual_url = extract_actual_url(redirect_url)
            actual_urls.append(actual_url)
            if actual_url:
                result = send_url_to_boilernet(actual_url)  # 実際のURLをLambda関数に送信
                results.append(result)  # resultをリストに追加
            else:
                results.append('')
    
    return results, actual_urls

def add_reviews_to_dynamodb(phone_name, reviews, urls):
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('sumdatabase')
    
    try:
        response = table.update_item(
            Key={'機種': phone_name},
            UpdateExpression='SET #rv1 = :r1, #rv2 = :r2, #rv3 = :r3, #url1 = :u1, #url2 = :u2, #url3 = :u3',
            ExpressionAttributeValues={
                ':r1': reviews[0],
                ':r2': reviews[1],
                ':r3': reviews[2],
                ':u1': urls[0],
                ':u2': urls[1],
                ':u3': urls[2]
            },
            ExpressionAttributeNames={
                '#rv1': 'レビュー1',
                '#rv2': 'レビュー2',
                '#rv3': 'レビュー3',
                '#url1': 'レビュー1のurl',
                '#url2': 'レビュー2のurl',
                '#url3': 'レビュー3のurl'
            }
        )
    except Exception as e:
        print(f"スマートフォン '{phone_name}' の保存中にエラーが発生しました: {e}")

# Lambda関数からの引数として最初に処理するスマホの番号を指定
def lambda_handler(event, context):
    start_phone_number = event.get('start_phone_number', 0)  # デフォルトは0番目のスマホから開始
    #phone_names = get_phone_names_from_dynamodb()#IntegratedPhoneStatusにある全てのスマホに付いてのレビューを格納する
    phone_names = ["AQUOS R8 pro SIMフリー", "moto g53j 5G SIMフリー", "OPPO A73 SIMフリー", "Redmi 12 5G SIMフリー", "motorola razr 40 SIMフリー"]#機種名を指定してレビューを格納する
    processed_count =  0 # 処理済みのスマホの数をカウント

    for i, phone_name in enumerate(phone_names):
        if i < start_phone_number:
            continue  # 指定番号までスキップ
        summaries = []
        urls = []

        for site in ["www.notebookcheck.net", "www.phonearena.com", "www.avforums.com"]:
        #"iPhone 12 mini 128GB SIMフリー", "iPhone 15 Plus 256GB SIMフリー", "Phone (1) 128GB SIMフリー  [ブラック]", "moto g52j 5G SIMフリー", "Zenfone 10 128GB SIMフリー", "iPhone SE (第3世代) 64GB SIMフリー", "iPhone 12 mini 64GB SIMフリー"の場合["www.gsmarena.com", "www.trustedreviews.com", "www.notebookcheck.net"]
        #他のスマホは["www.notebookcheck.net", "www.phonearena.com", "www.avforums.com"]を使用
            url_results = search_duckduckgo("iPhone SE (2020) 256GB SIMフリー", [site])#iPhone SE (第2世代) 256GB SIMフリーについてはiPhone SE (2020) 256GB SIMフリーで検索
            if url_results:
                summary_results, actual_urls = process_search_results(url_results)
                summaries.extend(summary_results)
                urls.extend(actual_urls[:3])  # 最初の3つのURLのみを使用
            else:
                summaries.extend(['', '', ''])
                urls.extend(['', '', ''])

        add_reviews_to_dynamodb(phone_name, summaries[:3], urls[:3])
        print(f"追加できたスマホの番号: {processed_count}")
        processed_count += 1
        print(f"スマートフォン '{phone_name}' のレビューを追加しました。")
