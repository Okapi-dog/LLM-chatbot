# coding: utf-8
import sys
import os
import boto3
import json

#retriever.pyのインポート
import retriever

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
#以下はOutputParserのためのインポート
from langchain.output_parsers import PydanticOutputParser, OutputFixingParser
from langchain.pydantic_v1 import BaseModel,Field #pydanticはv1とv2があるが、v2は新しく破壊的変更が多く、内部的にも使用されていないのでv1を使用する
from typing import List



def sum_to_requirements(history,newinput):  #検索用に要件をまとめる
    model = ChatOpenAI(model_name="gpt-3.5-turbo-1106",max_tokens=1000)
    summary_prompt = PromptTemplate(
        input_variables=["history", "new_inputs"],
        template='''AIと人間の会話から、人間が求めているスマホの要件をまとめてください。例を参考にして要件を作成してください。例は要件に含めないでください。
例：
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

新しい要約:
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


def get_context(input):#ドキュメントから要件の要約をもとに検索する
            phone=retriever.retrieve()
            return phone.get_retrieve(sum_to_requirements(input["history"],input["input"]))

class output(BaseModel):#返事のクラス
     choices_num: int =Field(desription="選択肢の数。選択肢がない場合は0とする")
     AI_reply: str =Field(desription="質問と選択肢を含めたAIの返答(項目間は改行を入れる)")


def next_lambda(message,choices_num,log_message,event):#次のラムダ関数を呼び出す
    # 次のラムダ関数を呼び出す (-> plain_text_output)
    lambda_client = boto3.client('lambda')
    #ARN of plain_text_output
    #next_function_name = 'arn:aws:lambda:ap-northeast-1:105837277682:function:plain_text_output'
    next_function_name = 'arn:aws:lambda:ap-northeast-1:105837277682:function:line_question_option_output'
    response = lambda_client.invoke(
        FunctionName=next_function_name,
        InvocationType='Event',
        Payload=json.dumps({'input_text': message, 'choices_num':choices_num, 'replyToken': event['replyToken'], 'userId': event['userId']} )
    )
    return log_message+event['userId']
    



def handler(event, context):

    summary_prompt = PromptTemplate(#要約用のプロンプト-今は使ってないが保存用
        input_variables=["summary", "new_lines"],
        template='''会話の行を徐々に要約し、前の要約に追加して新しい要約を返してください。例を参考にして要約を作成してください。例は要約に含めないでください。
例：
現在の要約:
人間はAIに人工知能についてどう思うか尋ねます。AIは人工知能が善の力だと考えています。
新しい会話の行:
人間:なぜあなたは人工知能が善の力だと思いますか？
AI:人工知能は人間が最大限の潜在能力を発揮するのを助けるからです。
新しい要約:
人間はAIに人工知能についてどう思うか尋ねます。AIは人工知能が善の力だと考えており、それは人間が最大限の潜在能力を発揮するのを助けるからです。
例の終わり

現在の要約:
{summary}
新しい会話の行:
{new_lines}
新しい要約:
    ''',
    )
    summary_prompt2 = PromptTemplate(#要約用のプロンプト-今は使ってないが保存用
        input_variables=["summary", "new_lines"],
        template="""Progressively summarize the lines of conversation provided, adding onto the previous summary returning a new summary. Do not include the example in the summary. Include question answer in the summary.

EXAMPLE
Current summary:
The human asks what the AI thinks of artificial intelligence. The AI thinks artificial intelligence is a force for good.

New lines of conversation:
Human: Why do you think artificial intelligence is a force for good?
AI: Because artificial intelligence will help humans reach their full potential.

New summary:
The human asks what the AI thinks of artificial intelligence. The AI thinks artificial intelligence is a force for good because it will help humans reach their full potential.
END OF EXAMPLE

Current summary:
{summary}

New lines of conversation:
{new_lines}

New summary:""")

    model = ChatOpenAI(model_name="gpt-3.5-turbo-1106",max_tokens=1000)
    parser=PydanticOutputParser(pydantic_object=output)
    fixing_parser=OutputFixingParser(parser=parser,llm=model)
    system_template = PromptTemplate(
            input_variables=[],
            template="質問と選択肢、選択肢と選択肢の間には改行を入れること。日本語で会話すること。\n{format_instructions}",
            partial_variables={"format_instructions": parser.get_format_instructions()}
            )
    system_message_prompt = SystemMessagePromptTemplate(prompt=system_template)
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", "あなたは質問をしておすすめのスマホを複数台教えるチャットbotです。あなたはおすすめのスマホを導くための質問を行うことが出来ます。質問は3個から5個の選択肢(a,b,c,d,e,f(分からない))で回答可能な形式でなければならない。人間は選択肢の内から一つを選んで回答をする。質問は一つずつすること。回答を待ってから回答を参考にして次の質問をすること。あなたは既に何回か質問をしており、あなたは次のような会話の要約や直近の会話の履歴を思い出すことが出来ます。質問と選択肢、選択肢と選択肢の間には改行を入れること。日本語で会話すること。"),
            MessagesPlaceholder(variable_name="history"),
            ("human", "{input}"),
            #("system","次の情報は最新の情報です。{context}"),
        ]
    )
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
        return next_lambda("履歴をクリアしました",0,"clear memory of",event)
    
        
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
        chain = (
            RunnablePassthrough.assign(
                history=RunnableLambda(memory.load_memory_variables) | itemgetter("history")
            )
            | prompt
            | model
        )
        chain_choicesnum = (
            prompt_choicesnum
            | model
        )

        inputs = {"input":  event['input_text']}
        response=chain.invoke(inputs).content
        choices_num=chain_choicesnum.invoke({"question":response}).content
        try:
             choices_num=int(choices_num)
        except ValueError:
            choices_num=0
        
        print("System: " + response)
        print("choices_num: " + str(choices_num))
        memory.save_context(inputs, {"output": response})   #memoryに会話を記憶。下はtableに記憶を保存する部分
        table.put_item(Item={
                        'userId': event['userId'],
                        'chat_memory_messages': json.dumps(messages_to_dict(memory.chat_memory.messages),ensure_ascii=False)
                    })
    
    
        return next_lambda(response, choices_num, "reply to", event)


    else:
        #最初の一回目の会話用のchainなど
        firstmodel = ChatOpenAI(model_name="gpt-3.5-turbo-1106",max_tokens=500)
        first_system_template = PromptTemplate(
            input_variables=["input"],
            template="あなたは質問をしておすすめのスマホを複数台教えるチャットbotです。あなたはおすすめのスマホを導くための質問を行うことが出来ます。質問は3個から5個の選択肢(a,b,c,d,e,f(分からない))で回答可能な形式でなければならない。人間は選択肢の内から一つを選んで回答をする。質問は一つずつすること。回答を待ってから回答を参考にして次の質問をすること。日本語で会話すること。質問と選択肢、選択肢と選択肢の間には改行を入れること。\n{format_instructions}",
            partial_variables={"format_instructions": parser.get_format_instructions()}
            )
        first_system_message_prompt = SystemMessagePromptTemplate(prompt=first_system_template)
        firstprompt = ChatPromptTemplate.from_messages([first_system_message_prompt])
        firstchain = (
            firstprompt
            | firstmodel
            | parser
        )
        inputs = {"input":  "質問を始めてください"}
        response=firstchain.invoke(inputs)

        print("System: " + response.AI_reply)
        memory.save_context(inputs, {"output": response.AI_reply})   #memoryに会話を記憶。下はtableに記憶を保存する部分
        table.put_item(Item={
                        'userId': event['userId'],
                        'chat_memory_messages': json.dumps(messages_to_dict(memory.chat_memory.messages),ensure_ascii=False)
                    })
    
    
        return next_lambda(response.AI_reply, response.choices_num, "reply to", event)
