# coding: utf-8
import sys
import os
import boto3
import json
import asyncio
import nest_asyncio
nest_asyncio.apply()
import re
from operator import itemgetter

#retriever.pyのインポート
import retriever
from retriever import get_documents

#recommend.pyのインポート
from recommend import process_answers
from recommend import convert_to_dict

#langchainのインポート
import langchain
from langchain_core.prompts import PromptTemplate
#langchain.debug = True
from langchain_openai import OpenAI
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder,SystemMessagePromptTemplate, HumanMessagePromptTemplate
from langchain.memory import ConversationBufferMemory,ConversationSummaryBufferMemory
from langchain.schema import messages_from_dict, messages_to_dict
from langchain.schema.runnable import RunnableLambda, RunnablePassthrough
#以下はDocumentStoreのためのインポート
from langchain_core.documents.base import Document

phones_info: list[Document] = [Document(page_content='Nothing', metadata={}),Document(page_content='Nothing', metadata={})]
#phones_infoの初期化(グローバル変数にする)
model= ChatOpenAI(model_name="gpt-3.5-turbo-1106",max_tokens=1000)
gpt4_model= ChatOpenAI(model_name="gpt-4-0125-preview",max_tokens=1000)
llm = OpenAI(model="gpt-3.5-turbo-instruct")




def get_requirements(history,newinput):  #検索用に要件をまとめる

    summary_prompt = PromptTemplate(
        input_variables=["history", "new_inputs"],
        template='''AIと人間の会話から、人間が求めているスマホの要件をまとめてください。例を参考にして要件を作成してください。例は要件に含めないでください。
例:
会話:
AI: こんにちは！スマホをお探しですね。まず最初の質問です。\n\na. 予算は3万円以下です\nb. 予算は3万円から5万円です\nc. 予算は5万円から8万円です\nd. 予算は8万円以上です\ne. 予算についてよく分からないです\nf. その他の要件がある\n\nどの予算帯に当てはまりますか？
人間: c
AI: 了解です！次の質問です。\n\na. カメラ性能が重要ですか？\nb. バッテリー持続時間が重要ですか？\nc. パフォーマンス（処理能力）が重要ですか？\nd. デザインやサイズが重要ですか？\ne. 画面の大きさが重要ですか？\nf. その他の要件がある\n\n何が重要ですか？

新しい人間の返答:
B

要件:
予算:5万円から8万円
重視するポイント:バッテリー持続時間

例の終わり

会話:
{history}

新しい人間の返答:
{new_inputs}

要件:
    ''',
    )
    summary_prompt2 = PromptTemplate(
        input_variables=["history", "new_inputs"],
        template='''AIとユーザーの会話から、ユーザーが求めているスマホの要件を要約してください。
            会話:{history}
            新しい人間の返答:{new_inputs}
            ユーザーが求める要件:''',)
    #プロンプトはここまで
    chain = (
            summary_prompt2
            | gpt4_model
        )
    response=chain.invoke({"new_inputs":  newinput,"history":history})
    print("\n要件:")#一応要件結果をログに出力
    print(response.content)
    return response.content


def send_recommendations(input,event,memory):#recommend.pyを呼び出しておすすめを返す
    pdf_tex="arn:aws:lambda:ap-northeast-1:105837277682:function:pdf_tex"

    global phones_info
    requirements=get_requirements(input["history"],input["input"])
    print("要件取得完了")
    phones_info=get_documents("IntegratedPhoneStatus-v3l",requirements)
    phones_info_dict=[convert_to_dict(phone_info.page_content) for phone_info in phones_info]
    try:
        compelling,review = asyncio.run(process_answers(requirements, phones_info_dict))

    except Exception as e:
        print(e)
        send_line("PDFの内容をGPTで生成する際にエラーが発生しました。時間をおいて再度お試しください。",0,event,None)
        

    phone_info_with_compelling=phones_info_dict
    for i in range(len(phones_info)):
        phone_info_with_compelling[i]["compelling1"]=compelling[i][0]
        phone_info_with_compelling[i]["compelling2"]=compelling[i][1]
        phone_info_with_compelling[i]["compelling3"]=compelling[i][2]
        phone_info_with_compelling[i]["review1"]=review[i]["review1"]
        phone_info_with_compelling[i]["review2"]=review[i]["review2"]
        phone_info_with_compelling[i]["review1_url"]=review[i]["review1_url"]
        phone_info_with_compelling[i]["review2_url"]=review[i]["review2_url"]
    
    print(phone_info_with_compelling)#最終的にPDFに出力する情報をログに出力
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('user-history')#ユーザーの履歴を保存するテーブル
    memory.save_context(input, {"output": "おすすめのスマホ提案書をPDFで送信します。"})
    table.put_item(Item={
                    'userId': event['userId'],
                    'chat_memory_messages': json.dumps(messages_to_dict(memory.chat_memory.messages),ensure_ascii=False),
                    'phone_info_with_compelling': json.dumps(phone_info_with_compelling,ensure_ascii=False)
                })
    
    to_pdf_lambda(pdf_tex,"",phone_info_with_compelling,event)




def send_line(message,choices_num,event,choices:None):#lineにメッセージを送信する
    lambda_client = boto3.client('lambda')
    #ARN of plain_text_output
    next_function_name = 'arn:aws:lambda:ap-northeast-1:105837277682:function:line_question_option_output'
    lambda_client.invoke(
        FunctionName=next_function_name,
        InvocationType='Event',
        Payload=json.dumps({'input_text': message, 'choices_num':choices_num, 'replyToken': event['replyToken'], 'userId': event['userId'],'choices':choices} )
    )

def to_pdf_lambda(next_function_name,message,phone_info_with_compelling,event):#PDFを作成するラムダ関数を呼び出す
    lambda_client = boto3.client('lambda')
    #next_function_nameはlambdaのARNを入れる

    response = lambda_client.invoke(
        FunctionName=next_function_name,
        InvocationType='Event',
        Payload=json.dumps({'input_text': message, 'phone_info_with_compelling':phone_info_with_compelling, 'replyToken': event['replyToken'], 'userId': event['userId']} )
    )




def not_reccomendation(inputs,response,memory,table,event):
    #下は選択肢の数を取得する部分
    output_text=response.content
    print("System: " + output_text)
    try:
        question = re.search(r'^.*\n', response.content).group()
        question = question.strip()#\nを取り除く
        output_text=question
        choices = re.findall(r'\b[abcdef]\) .+?(?=\n|$)', response.content)
        choices_num=len(choices)#選択肢の数を取得
        if choices_num!=0:#選択肢がある時はa)を取り除く
            choices_list=["a)","b)","c)","d)","e)","f)"]
            for i in range(choices_num):
                if choices_list[i] in choices[i]:
                    choices[i]=choices[i].replace(choices_list[i],"")
                else:
                    choices_num=0
                    output_text=response.content
        else:#選択肢がない時はそのまま返す
            output_text=response.content
            choices=None
    except:
        choices_num=0
        output_text=response.content
        choices=None

    #memoryにPDFを生成したということを記憶させる。下はtableに記憶を保存する部分
    memory.save_context(inputs, {"output": response.content})   
    table.put_item(Item={
                    'userId': event['userId'],
                    'chat_memory_messages': json.dumps(messages_to_dict(memory.chat_memory.messages),ensure_ascii=False)
                })

    send_line(output_text, choices_num, event, choices=choices)


def handler(event, context):

    
    prompt_question=ChatPromptTemplate.from_messages(
        [
            ("system", """あなたはスマートフォン選びをサポートする優秀な店員です。現在のあなたの役割は、スマートフォン選びに関する質問を行い、ユーザーのニーズを理解することです。
             人間は質問に対して提供された選択肢の中から一つを選んで回答します。次の情報は会話履歴です。"""),
            MessagesPlaceholder(variable_name="history"),
            ("human", "{input}"),
            ("system","これらの情報を基にして、ユーザーの状況やニーズを探る一つの質問とその質問に対する選択肢を作成して下さい。選択肢は3個から5個で(a,b,c,d,e,f)にして下さい。また、選択肢にできる限りその他や分からないという選択肢を設けて下さい。質問と選択肢の間には改行を入れてください。選択肢はa) 内容\nb) 内容\nc) 内容\nといった形式で言ってください。例としては、a) 軽量だがバッテリーはあまり持たない\nb) 普通の重さで普通のバッテリーの持続時間\nといった感じです。また、あなたはおすすめの提案をすることはできず、質問のみを行います。会話は日本語で行ってください。"),
        ])
    prompt_answer=ChatPromptTemplate.from_messages(
        [
            ("system", """あなたはスマートフォン選びをサポートする優秀な店員です。現在のあなたの役割は、ユーザーからの質問などに答えることです。次の情報は会話履歴です。"""),
            MessagesPlaceholder(variable_name="history"),
            ("human", "{input}"),
            ("system","また、あなたはおすすめの提案をすることはできず、質問に答えることのみを行います。会話は日本語で行ってください。"),
        ])
    prompt_answer_pdf=ChatPromptTemplate.from_messages(
        [   ("system", "次の情報は前回あなたが提案したスマホ提案PDFの情報です。{pdf_phone_info}"),
            ("system", """あなたはスマートフォン選びをサポートする優秀な店員です。現在のあなたの役割は、ユーザーからの質問などに答えることです。次の情報は会話履歴です。"""),
            MessagesPlaceholder(variable_name="history"),
            ("human", "{input}"),
            ("system","あなたはおすすめの提案をすることはできず、質問に答えることのみを行います。会話は日本語で行ってください。"),
        ])
    prompt_dialogue_pdf=ChatPromptTemplate.from_messages(
        [   ("system", "次の情報は前回あなたが提案したスマホ提案PDFの情報です。{pdf_phone_info}"),
            ("system", """あなたはスマートフォン選びをサポートする優秀な店員です。現在のあなたの役割は、ユーザーの要望に応えることです。次の情報は会話履歴です。"""),
            MessagesPlaceholder(variable_name="history"),
            ("human", "{input}"),
            ("system","あなたはおすすめの提案をすることはできません。会話は日本語で行ってください。"),
        ])
    prompt_dialogue=ChatPromptTemplate.from_messages(
        [   ("system", """あなたはスマートフォン選びをサポートする優秀な店員です。現在のあなたの役割は、ユーザーの要望に応えることです。次の情報は会話履歴です。"""),
            MessagesPlaceholder(variable_name="history"),
            ("human", "{input}"),
            ("system","あなたはおすすめの提案をすることはできません。会話は日本語で行ってください。"),
        ])
    #memory = ConversationSummaryBufferMemory(llm=OpenAI(temperature=0),max_token_limit=200,return_messages=True,prompt=summary_prompt2)
    memory = ConversationBufferMemory(return_messages=True)#全ての会話履歴を保存するメモリー(ただし、今後は制限をかける予定)
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('user-history')#ユーザーの会話履歴を保存するテーブル

    if event['input_text']=="clear" or event['input_text']=="質問を始める":#clearと入力された時にメモリーをクリアする
        table.delete_item(
            Key={
                'userId': event['userId']
            }
        )
        
    
        
    table_response = table.get_item(
        Key={
            'userId': event['userId']
        }
    )
    if 'Item' in table_response:    #ユーザーの記憶がある時に記憶を読み込む
        print(table_response['Item'])
        memory.chat_memory.messages=messages_from_dict(json.loads(table_response['Item']['chat_memory_messages']))
        if 'phone_info_with_compelling' in table_response['Item']:
            #pdf_phone_info = json.loads(table_response['Item']['phone_info_with_compelling'])
            pdf_phone_info = table_response['Item']['phone_info_with_compelling']
            print(pdf_phone_info)
        else:
            pdf_phone_info = None
            print("PDF情報なし")
        print("以下は読み出したメモリー(memory.chat_memory.messages, memory.moving_summary_buffer,memory.load_memory_variables)")
        print(memory.chat_memory.messages)
        print(memory.load_memory_variables({}))
        #質問と提案の判断を行うプロンプトとチェーン

        decision_prompt = ChatPromptTemplate.from_messages([
            ("system", """あなたはスマートフォンに関する推薦を行うチャットボットです。会話履歴の分析を通じて、ユーザーに対して更なる質問を行うか、もしくはスマートフォンの推薦に進むか、ユーザーの質問などに答えるか、ユーザーと対話するかを判断するのがあなたの役割です。以下のガイドラインに従って次のステップを決定してください：
AIがこれまでの会話でユーザーに最低4つの質問を行っているかを確認します。
これらの質問がユーザーのニーズや好みを明らかにするのに十分かどうかを検討します。
もしAIが4つ以上の質問を行っていて、かつそれらの質問がユーザーのニーズを明確にしていると判断できる場合は、「A」と返答します。
もしAIが4つ未満の質問しかしていないか、または4つ以上の質問をしていてもユーザーのニーズがまだ十分に明確ではないと判断される場合は、「B」と返答します。
もしユーザーがAIに対して質問をしている場合は、「C」と返答します。
もし上記の条件にあてはまらない場合やユーザーが対話をしようとしている時は、「D」と返答します。
以下は直近の会話履歴です。                         
            """),
            MessagesPlaceholder(variable_name="history"),
            ("human", "{input}"),
            ("system","これらの情報を基にして、ユーザーに最適な応答をA,B,Cで選択してください。ユーザーの要望を正確に理解し、適切な推薦を行うことが重要です。"),
        ])
        decision_chain=(
            RunnablePassthrough.assign(
                history=RunnableLambda(memory.load_memory_variables) | itemgetter("history")
            )
            |decision_prompt
            | gpt4_model
        )

        inputs = {"input":  event['input_text']}
        decision_response=decision_chain.invoke(inputs).content
        # str.replace()を使用して空白、改行、タブを取り除く
        decision_response = decision_response.replace(" ", "").replace("\n", "").replace("\t", "")
        print("\n次の行動:\n")
        print(decision_response)
        if decision_response=="A":#提案を行う
            inputs = {"input":  event['input_text'], "history":memory.chat_memory.messages}
            send_recommendations(inputs,event,memory)
            return '提案を行います'
        elif decision_response=="B":#質問を行う
            second_chain=(
                RunnablePassthrough.assign(
                    history=RunnableLambda(memory.load_memory_variables) | itemgetter("history")
                )
                |prompt_question
                | model
            )
            print("正常に質問します")
            response=second_chain.invoke(inputs)
        elif decision_response=="C":#質問に答える
            if pdf_phone_info:
                print("pdf情報使用")
                second_chain=(
                    RunnablePassthrough.assign(
                        history=RunnableLambda(memory.load_memory_variables) | itemgetter("history")
                    )
                    |prompt_answer_pdf
                    | model
                )
                #inputs["pdf_phone_info"]=json.dumps(pdf_phone_info)
                inputs["pdf_phone_info"]=pdf_phone_info
                response=second_chain.invoke(inputs)
                del inputs["pdf_phone_info"]
            else:
                second_chain=(
                    RunnablePassthrough.assign(
                        history=RunnableLambda(memory.load_memory_variables) | itemgetter("history")
                    )
                    |prompt_answer
                    | model
                )
                response=second_chain.invoke(inputs)
            print("正常質問に答えます")

        elif decision_response=="D":#対話する
            if pdf_phone_info:
                print("pdf情報使用")
                second_chain=(
                    RunnablePassthrough.assign(
                        history=RunnableLambda(memory.load_memory_variables) | itemgetter("history")
                    )
                    |prompt_dialogue_pdf
                    | model
                )
                #inputs["pdf_phone_info"]=json.dumps(pdf_phone_info)
                inputs["pdf_phone_info"]=pdf_phone_info
                response=second_chain.invoke(inputs)
                del inputs["pdf_phone_info"]
            else:
                second_chain=(
                    RunnablePassthrough.assign(
                        history=RunnableLambda(memory.load_memory_variables) | itemgetter("history")
                    )
                    |prompt_dialogue
                    | model
                )
                response=second_chain.invoke(inputs)
            print("正常質問に答えます")
        else:#分岐が不正な値の時でも質問を行う
            second_chain=(
                RunnablePassthrough.assign(
                    history=RunnableLambda(memory.load_memory_variables) | itemgetter("history")
                )
                |prompt_question
                | model
            )
            print("不正に質問。次の行動:"+decision_response)
            response=second_chain.invoke(inputs)
        not_reccomendation(inputs,response,memory,table,event)


    else:
        #最初の一回目の会話用のchain
        firstprompt = PromptTemplate(
            input_variables=["input"],
            template='''あなたはスマートフォン選びをサポートする優秀な店員です。現在のあなたの役割は、スマートフォン選びに関する質問を行い、ユーザーのニーズを理解することです。
             人間は質問に対して提供された選択肢の中から一つを選んで回答します。ユーザーの状況やニーズを探る一つの質問とその質問に対する選択肢を作成して下さい。
             選択肢は3個から5個で(a,b,c,d,e,f)にして下さい。また、選択肢にできる限りその他や分からないという選択肢を設けて下さい。質問と選択肢の間には改行を入れてください。会話は日本語で行ってください。
             ''',
            )
        firstchain = (
            firstprompt
            |model
        )
        inputs = {"input":  "質問を始めてください"}
        response=firstchain.invoke(inputs)
        not_reccomendation(inputs,response,memory,table,event)
        print('最初の質問を行いました')
