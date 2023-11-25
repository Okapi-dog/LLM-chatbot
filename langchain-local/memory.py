import langchain
#langchain.debug = True
from langchain.callbacks.tracers import ConsoleCallbackHandler
from langchain.llms import OpenAI
from operator import itemgetter
from langchain.chat_models import ChatOpenAI
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.memory import ConversationBufferMemory,ConversationSummaryBufferMemory

from langchain.schema.runnable import RunnableLambda, RunnablePassthrough

prompt = ChatPromptTemplate.from_messages(
    [
        ("system", "You are a helpful chatbot"),
        MessagesPlaceholder(variable_name="history"),
        ("human", "{input}"),
    ]
)
model = ChatOpenAI(model_name="gpt-3.5-turbo-1106",max_tokens=100)
#memory = ConversationBufferMemory(return_messages=True)
memory = ConversationSummaryBufferMemory(llm=OpenAI(),max_token_limit=40,return_messages=True)

memory.load_memory_variables({})
#chain = prompt | model
#stop return
#chain = prompt | model.bind(stop=["\n"])
chain = (
    RunnablePassthrough.assign(
        history=RunnableLambda(memory.load_memory_variables) | itemgetter("history")
    )
    | prompt
    | model
)
while True:
    #input = input("You: ")
    inputs = {"input":  input("You: ")}
    #response=chain.invoke(inputs,config={'callbacks': [ConsoleCallbackHandler()]})
    response=chain.invoke(inputs)
    print("System: " + response.content)
    memory.save_context(inputs, {"output": response.content})
    print(memory.load_memory_variables({}))
