# coding: utf-8
import sys
import os
import boto3
import json
import asyncio
import re


#retriever.pyのインポート
import retriever

#recommend.pyのインポート
from recommend import process_answers
from recommend import convert_to_dict

#langchainのインポート
import langchain
from langchain.prompts import PromptTemplate
#langchain.debug = True
from langchain.callbacks.tracers import ConsoleCallbackHandler
from langchain.llms import OpenAI
from operator import itemgetter
from langchain.chat_models import ChatOpenAI
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder,SystemMessagePromptTemplate, HumanMessagePromptTemplate
from langchain.memory import ConversationBufferMemory,ConversationSummaryBufferMemory
from langchain.schema import messages_from_dict, messages_to_dict
from langchain.schema.runnable import RunnableLambda, RunnablePassthrough
#以下はDocumentStoreのためのインポート
from langchain.docstore.document import Document

phones_info: list[Document] = [Document(page_content='Nothing', metadata={}),Document(page_content='Nothing', metadata={})]#phones_infoの初期化




def get_requirements(history,newinput):  #検索用に要件をまとめる

    model = ChatOpenAI(model_name="gpt-3.5-turbo-1106",max_tokens=1000)
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
    #プロンプトはここまで
    chain = (
            summary_prompt
            | model
        )
    response=chain.invoke({"new_inputs":  newinput,"history":history})
    print("\nsummary:")#一応要件結果をログに出力
    print(response.content)
    return response.content


def send_recommendations(input):#recommend.pyを呼び出しておすすめを返す
    global phones_info
    retrival=retriever.Retrieval()
    requirements=get_requirements(input["history"],input["input"])
    print("要件取得完了")
    phones_info=retrival.retrieve(requirements)
    phones_info_dict=[convert_to_dict(phone_info.page_content) for phone_info in phones_info]
    print(phones_info)
    killer_sentences = asyncio.run(process_answers(requirements, phones_info_dict))
    print(killer_sentences)
    reply="要件\n"+requirements #Line用の返答を作成
    for i in range(len(phones_info)):
        reply=reply+"\n機種名:"+phones_info_dict[i]["機種"]+"\nキラー文"
        for j in range(len(killer_sentences[i])):
            reply=reply+"\n"+str(j+1)+"個目\n"+killer_sentences[i][j]
    return reply



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

    model       = ChatOpenAI(model_name="gpt-3.5-turbo-1106",max_tokens=1000)
    gpt4_model  = ChatOpenAI(model_name="gpt-4-1106-preview",max_tokens=1000)
    prompt_question=ChatPromptTemplate.from_messages(
        [
            ("system", """あなたはスマートフォン選びをサポートする優秀な店員です。現在のあなたの役割は、スマートフォン選びに関する質問を行い、ユーザーのニーズを理解することです。
             人間は質問に対して提供された選択肢の中から一つを選んで回答します。次の情報は会話履歴です。"""),
            MessagesPlaceholder(variable_name="history"),
            ("human", "{input}"),
            ("system","これらの情報を基にして、ユーザーの状況やニーズを探る一つの質問とその質問に対する選択肢を作成して下さい。選択肢は3個から5個で(a,b,c,d,e,f)にして下さい。また、選択肢にできる限りその他や分からないという選択肢を設けて下さい。質問と選択肢の間には改行を入れてください。選択肢はa) 内容\nb) 内容\nc) 内容\nといった形式で言ってください。例としては、a) 軽量だがバッテリーはあまり持たない\nb) 普通の重さで普通のバッテリーの持続時間\nといった感じです。また、あなたはおすすめの提案をすることはできず、質問のみを行います。会話は日本語で行ってください。"),
        ])
    prompt_show_phones=PromptTemplate(
        input_variables=["history", "input"],
        template='''あなたは質問をしておすすめのスマホを複数台教えるチャットbots(一人は質問担当、もう一人はおすすめ提案担当)のおすすめ提案担当チャットbotです。あなたはおすすめのスマホを導くための質問を行うことが出来ません。あなたは会話履歴に基づいておすすめのスマホを教えなさい。日本語で会話すること。
            会話:
                {history}
            新しい人間の回答:
                {input}
        ''')
    prompt_choicesnum=PromptTemplate(
        input_variables=["question"],
        template='''AIの返答から、AIの質問の選択肢の数(整数)を答えてください。返答に選択肢が存在しない場合は0と答えてください。例を参考に選択肢の数を答えてください。例は選択肢の数に含めないでください。
        例:
        AI:
        次の質問です。あなたはどのような用途でスマホを使用しますか？\na) ゲームをする\nb) 写真を撮る\nc) 仕事や学業に使う\nd) 動画を視聴する\ne) 音楽を聴く
        選択肢の数:
        5
        例の終わり
        AI:
        {question}
        選択肢の数:
        '''
    ) 
    chain_choicesnum = (
            prompt_choicesnum
            | model
        )
    #memory = ConversationSummaryBufferMemory(llm=OpenAI(temperature=0),max_token_limit=200,return_messages=True,prompt=summary_prompt2)
    memory = ConversationBufferMemory(return_messages=True)#全ての会話履歴を保存するメモリー(ただし、今後は制限をかける予定)
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('user-history')#ユーザーの会話履歴を保存するテーブル

    if event['input_text']=="clear":#clearと入力された時にメモリーをクリアする
        table.delete_item(
            Key={
                'userId': event['userId']
            }
        )
        return next_lambda("履歴をクリアしました",0,"clear memory of",event,choices=None)
    
        
    table_response = table.get_item(
        Key={
            'userId': event['userId']
        }
    )
    if 'Item' in table_response:    #ユーザーの記憶がある時に記憶を読み込む
        print(table_response['Item'])
        memory.chat_memory.messages=messages_from_dict(json.loads(table_response['Item']['chat_memory_messages']))
        print("以下は読み出したメモリー(memory.chat_memory.messages, memory.moving_summary_buffer,memory.load_memory_variables)")
        print(memory.chat_memory.messages)
        print(memory.load_memory_variables({}))
        
            
        #最初の一回目の会話以外用のchain
        decision_model = OpenAI(model_name="gpt-3.5-turbo-instruct",max_tokens=1000)
        #質問と提案の判断を行うプロンプトとチェーン

        decision_prompt = ChatPromptTemplate.from_messages([
            ("system", """あなたはスマートフォンに関する推薦を行うチャットボットです。会話履歴の分析を通じて、ユーザーに対して更なる質問を行うか、もしくはスマートフォンの推薦に進むかを判断するのがあなたの役割です。以下のガイドラインに従って次のステップを決定してください：
AIがこれまでの会話でユーザーに最低4つの質問を行っているかを確認します。
これらの質問がユーザーのニーズや好みを明らかにするのに十分かどうかを検討します。
もしAIが4つ以上の質問を行っていて、かつそれらの質問がユーザーのニーズを明確にしていると判断できる場合は、「T」と返答します。
もしAIが4つ未満の質問しかしていないか、または4つ以上の質問をしていてもユーザーのニーズがまだ十分に明確ではないと判断される場合は、「F」と返答します。
以下は直近の会話履歴です。                         
            """),
            MessagesPlaceholder(variable_name="history"),
            ("human", "{input}"),
            ("system","これらの情報を基にして、ユーザーに最適な応答をTかFで選択してください。ユーザーの要望を正確に理解し、適切な推薦を行うことが重要です。"),
        ])
        decision_chain=(
            RunnablePassthrough.assign(
                history=RunnableLambda(memory.load_memory_variables) | itemgetter("history")
            )
            |decision_prompt
            | model
        )
        

        inputs = {"input":  event['input_text']}
        decision_response=decision_chain.invoke(inputs).content
        # str.replace()を使用して空白、改行、タブを取り除く
        decision_response = decision_response.replace(" ", "").replace("\n", "").replace("\t", "")
        print("\n次の行動:\n")
        print(decision_response)
        if decision_response=="T":#提案を行う
            inputs = {"input":  event['input_text'], "history":memory.chat_memory.messages}
            return next_lambda(send_recommendations(inputs),0,"reply to",event,choices=None)
            second_chain=(
                RunnablePassthrough.assign(
                    history=RunnableLambda(memory.load_memory_variables) | itemgetter("history")
                )
                |prompt_show_phones
                | model
            )
            print("正常におすすめ提案。次の行動:"+decision_response)
            response=second_chain.invoke(inputs)
        elif decision_response=="F":#質問を行う
            second_chain=(
                RunnablePassthrough.assign(
                    history=RunnableLambda(memory.load_memory_variables) | itemgetter("history")
                )
                |prompt_question
                | model
            )
            print("正常に質問。次の行動:"+decision_response)
            response=second_chain.invoke(inputs)
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
        
        #下は選択肢の数を取得する部分
        """choices_num=chain_choicesnum.invoke({"question":response.content}).content
        try:
            choices_num=int(choices_num)
        except ValueError:
            choices_num=0"""
        
        #下はログを出力する部分
        input_text=response.content
        print("System: " + input_text)
        #print("choices_num: " + str(choices_num))
        # Extracting the question from the text
        question = re.search(r'^.*\n', response.content).group()
        question = question.strip()#\nを取り除く
        input_text=question
        choices = re.findall(r'\b[abcdef]\) .+?(?=\n|$)', response.content)
        print("question: \n" + question)
        print("choices: ")
        print(choices)
        choices_num=len(choices)#選択肢の数を取得
        if choices_num!=0:#選択肢がある時はa)を取り除く
            choices_list=["a)","b)","c)","d)","e)","f)"]
            for i in range(choices_num):
                if choices_list[i] in choices[i]:
                    choices[i]=choices[i].replace(choices_list[i],"")
                else:
                    choices_num=0
                    input_text="内部エラーが発生していますが問題がないので、質問を続行します。"+response.content
                    break
        else:#選択肢がない時はそのまま返す
            input_text=response.content
        print(choices)

        #memoryに会話を記憶。下はtableに記憶を保存する部分
        memory.save_context(inputs, {"output": response.content})   
        table.put_item(Item={
                        'userId': event['userId'],
                        'chat_memory_messages': json.dumps(messages_to_dict(memory.chat_memory.messages),ensure_ascii=False)
                    })
    
        return next_lambda(response.content, choices_num, "reply to", event, choices=choices)


    else:
        #最初の一回目の会話用のchain
        firstmodel = ChatOpenAI(model_name="gpt-3.5-turbo-1106",max_tokens=500)
        firstprompt = PromptTemplate(
            input_variables=["input"],
            template='''あなたはスマートフォン選びをサポートする優秀な店員です。現在のあなたの役割は、スマートフォン選びに関する質問を行い、ユーザーのニーズを理解することです。
             人間は質問に対して提供された選択肢の中から一つを選んで回答します。ユーザーの状況やニーズを探る一つの質問とその質問に対する選択肢を作成して下さい。
             選択肢は3個から5個で(a,b,c,d,e,f)にして下さい。また、選択肢にできる限りその他や分からないという選択肢を設けて下さい。質問と選択肢の間には改行を入れてください。会話は日本語で行ってください。
             ''',
            )
        firstchain = (
            firstprompt
            |firstmodel
        )
        inputs = {"input":  "質問を始めてください"}
        response=firstchain.invoke(inputs)

        print("System: " + response.content)

        #memoryに会話を記憶。下はtableに記憶を保存する部分
        memory.save_context(inputs, {"output": response.content})
        table.put_item(Item={
                        'userId': event['userId'],
                        'chat_memory_messages': json.dumps(messages_to_dict(memory.chat_memory.messages),ensure_ascii=False)
                    })
        
        #下は選択肢の数を取得する部分
        choices_num=chain_choicesnum.invoke({"question":response.content}).content
        try:
             choices_num=int(choices_num)
        except ValueError:
            choices_num=0
    
        return next_lambda(response.content, choices_num, "reply to", event, choices=None)
