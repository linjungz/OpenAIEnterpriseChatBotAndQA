'''
Enterprise KB Chatbot and KB QA UI, using Azure OpenAI and Azure Cognitive Services
For demo purpose, the chatbot summarizes based on the vector generated by Enterprise_KB_Ingest.py by scanning the docs in subfolder ..\Doc_Store.

Created by Ric Zhou on 2023.03.27
'''

from langchain.llms import AzureOpenAI
from langchain.chains import (VectorDBQAWithSourcesChain, ConversationalRetrievalChain, ChatVectorDBChain, RetrievalQAWithSourcesChain)
from langchain.vectorstores import FAISS
from langchain.embeddings import OpenAIEmbeddings
import gradio as gr
import os
from dotenv import load_dotenv
from CommonHelper import *
from GlobalClasses import *
from ChatPromptTemplate import *
from CustomConversationalRetrievalChain import *


def execute_chat(user_input):
    if GlobalContext.ENABLE_TRANSLATION:
        GlobalContext.txt_translate_to_languages = language_detection(user_input)
    # user_input = user_input.replace("\n", "\\n")
    print("\n[History]: {}".format(GlobalContext.chat_history))
    result = lc_chatbot({"question": user_input, "chat_history": GlobalContext.chat_history})
    answer_str = result["answer"].lstrip("\n")
    GlobalContext.chat_latest_return = answer_str
    print("\n[Answer] {}".format(answer_str))

    GlobalContext.chat_history.extend([(user_input, answer_str)])

    GlobalContext.source_doc_reference_str = ""
    for source_doc in result["source_documents"]:
        GlobalContext.source_doc_reference_str += f"{source_doc.metadata}\n"
        print(source_doc.metadata)

    # keep the history within specific length
    if GlobalContext.KEEP_CHAT_HISTORY_TURN > 0:
        while (len(GlobalContext.chat_history) > GlobalContext.KEEP_CHAT_HISTORY_TURN):
            GlobalContext.chat_history.pop(0)

    return answer_str, GlobalContext.source_doc_reference_str


def chat_set_msg(user_message, history):
    GlobalContext.user_message = user_message
    history = history_remove_br(history)
    return history + [[user_message, None]]


def chat_set_bot(history):
    bot_message, reference_str = execute_chat(GlobalContext.user_message)
    # bot_message = bot_message.replace("\\n", "\n")

    GlobalContext.message_for_read_out = bot_message

    if GlobalContext.ENABLE_TRANSLATION:
        output_language = language_detection(bot_message)
        if GlobalContext.txt_translate_to_languages != output_language:
            translated = language_translate(bot_message, GlobalContext.txt_translate_to_languages)
            GlobalContext.message_for_read_out = translated
            print("\n[Answer Translated]: {}".format(translated))
            bot_message += f"\n{translated}"
    bot_message += f"\n{reference_str}"

    history[-1][1] = bot_message
    history = history_remove_br(history)
    return "", history


def execute_QA(user_message):
    if GlobalContext.ENABLE_TRANSLATION:
        GlobalContext.txt_translate_to_languages = language_detection(user_message)
    result = lc_qa_chain({"question": user_message})
    answer = result['answer']
    print(f"\n[Answer]: {answer}")
    # print(f"\n[Sources]: {result['sources']}")
    return answer


def QA_set_msg(user_message):
    GlobalContext.user_message = user_message
    # history = history_remove_br(history)
    return [[user_message, None]]


def QA_set_panel(history):
    qa_message = execute_QA(GlobalContext.user_message)
    # qa_message = qa_message.replace("\\n", "\n")

    GlobalContext.message_for_read_out = qa_message
    if GlobalContext.ENABLE_TRANSLATION:
        output_language = language_detection(qa_message)
        if GlobalContext.txt_translate_to_languages != output_language:
            translated = language_translate(qa_message, GlobalContext.txt_translate_to_languages)
            GlobalContext.message_for_read_out = translated
            print("\n[Answer Translated]: {}".format(translated))
            qa_message += f"\n{translated}"

    history[-1][1] = qa_message
    history = history_remove_br(history)
    return "", history


def history_remove_br(history):
    for x in range(0, len(history)):
        history[x][0] = history[x][0].replace("<br>", "")
        history[x][1] = history[x][1].replace("<br>", "")
    return history


def readOuput():
    if (GlobalContext.ENABLE_VOICE):
        if (GlobalContext.need_read_output):
            print("[reading...] {}".format(GlobalContext.chat_latest_return))
            # text_to_voice("oh " + GlobalContext.chat_latest_return)
            text_to_voice(GlobalContext.chat_latest_return)
            GlobalContext.chat_latest_return = ""
    return gr.Button.update(interactive=True)


def clearHistory():
    GlobalContext.message_for_read_out = ""
    GlobalContext.chat_latest_return = ""
    GlobalContext.chat_history = []
    return ""


def clearHistory_and_backup(history):
    GlobalContext.message_for_read_out = ""
    GlobalContext.chat_latest_return = ""
    GlobalContext.chat_history = []
    return "", history


def change_system_message(system_message):
    GlobalContext.set_openai_system_msg(system_message)
    return clearHistory()


def startRecording(history):
    if (GlobalContext.ENABLE_VOICE):
        if (GlobalContext.need_translate):
            GlobalContext.original_sound_text, voice_text = translate_from_microphone()
            print("[Captured text] {}".format(GlobalContext.original_sound_text))
            print("[Translated text] {}".format(voice_text))
        else:
            voice_text = voice_to_text()
            print("[Captured text] {}".format(voice_text))
    else:
        voice_text = "Voice is not enabled at global setting!"
    GlobalContext.user_message = voice_text
    return history + [[voice_text, None]]


def radioChage(choice):
    if choice == "Say Chinese":
        GlobalContext.speech_recognition_language = "zh-cn"
        GlobalContext.need_translate = False
        # GlobalContext.text_to_speech_language = "zh-CN-XiaoxiaoNeural"
    elif choice == "Say English":
        GlobalContext.speech_recognition_language = "en-US"
        GlobalContext.need_translate = False
        # GlobalContext.text_to_speech_language = 'en-US-JennyMultilingualNeural'  # 'en-US-JennyNeural'
    elif choice == "Say Chinese output English":
        GlobalContext.translation_source_language = "zh-cn"
        GlobalContext.translation_targe_language = "en"
        GlobalContext.need_translate = True
        # GlobalContext.text_to_speech_language = 'en-US-JennyMultilingualNeural'  # 'en-US-JennyNeural'
    elif choice == "Say English output Chinese":
        GlobalContext.translation_source_language = "en-US"
        GlobalContext.translation_targe_language = "zh-Hans"
        GlobalContext.need_translate = True
        # GlobalContext.text_to_speech_language = "zh-CN-XiaoxiaoNeural"
    return None


def readOutSettingChange(checkbox):
    if checkbox:
        GlobalContext.need_read_output = True
    else:
        GlobalContext.need_read_output = False


def change_Openai_param(param_name, value):
    match param_name:
        case "max_tokens":
            GlobalContext.openai_param_max_tokens = value
            print("GlobalContext.openai_param_max_tokens = {}".format(value))
            # print("type is {}".format(type(GlobalContext.openai_param_max_tokens)))
        case "temperature":
            GlobalContext.openai_param_temperature = value
            print("GlobalContext.openai_param_temperature = {}".format(value))
        case "top_p":
            GlobalContext.openai_param_top_p = value
            print("GlobalContext.openai_param_top_p = {}".format(value))
        case _:
            print("unknown param name when call [change_Openai_param]")


load_dotenv()
GlobalContext()  # initialize global context

GlobalContext.ENABLE_TRANSLATION = False  # you need to provide Azure Translator API key at GlobalContext before enable this feature
GlobalContext.ENABLE_VOICE = False  # you need to provide Azure Speech API key at GlobalContext before enable this feature
GlobalContext.SHOW_SINGLE_TURN_QA = False  # show single turn QA interactive UI

os.environ["OPENAI_API_TYPE"] = "azure"
os.environ["OPENAI_API_VERSION"] = "2022-12-01"
os.environ["OPENAI_API_BASE"] = GlobalContext.OPENAI_BASE
os.environ["OPENAI_API_KEY"] = GlobalContext.OPENAI_API_KEY

# vectorstore = FAISS.load_local(GlobalContext.VECTOR_DB_PATH, OpenAIEmbeddings(document_model_name="text-search-curie-doc-001", query_model_name="text-search-curie-query-001")) # text-search-curie-*-001 performance is worse than text-embedding-ada-002
vectorstore = FAISS.load_local(GlobalContext.VECTOR_DB_PATH, OpenAIEmbeddings(chunk_size=1))

# input("Press Enter to continue...")

# "text-davinci-003"
# intialize ChatVectorDBChain
lc_chatbot_llm = AzureOpenAI(temperature=0, deployment_name="text-davinci-003", model_name="text-davinci-003", max_tokens=800)

lc_chatbot = CustomConversationalRetrievalChain.from_llm(lc_chatbot_llm, vectorstore.as_retriever(
), condense_question_prompt=MyPromptCollection.CONDENSE_QUESTION_PROMPT, chain_type="stuff")  # stuff , map_reduce, refine, map_rerank
# lc_chatbot.top_k_docs_for_context = 3
lc_chatbot.max_tokens_limit = GlobalContext.TOTAL_TOKENS_LIMIT_OF_ALL_DOCS_FOR_CHAIN  # only take effect on 'stuff' and 'refine' chain type
lc_chatbot.return_source_documents = True

if GlobalContext.SHOW_SINGLE_TURN_QA:  # disabled by default
    # initialize VectorDBQAWithSourcesChain RetrievalQAWithSourcesChain
    lc_qa_chain_llm = AzureOpenAI(temperature=0, deployment_name="text-davinci-003", model_name="text-davinci-003", max_tokens=800)
    # lc_qa_chain = RetrievalQAWithSourcesChain.from_chain_type(lc_qa_chain_llm, chain_type="refine", retriever=vectorstore.as_retriever())  # stuff , map_reduce, refine, map_rerank
    lc_qa_chain = VectorDBQAWithSourcesChain.from_chain_type(lc_qa_chain_llm, chain_type="refine", vectorstore=vectorstore, k=3)  # stuff , map_reduce, refine, map_rerank
    lc_qa_chain.reduce_k_below_max_tokens = True
    lc_qa_chain.max_tokens_limit = GlobalContext.TOTAL_TOKENS_LIMIT_OF_ALL_DOCS_FOR_CHAIN  # only take effect on 'stuff' chain type
    lc_qa_chain.return_source_documents = True

# Spin up web GUI

# with gr.Blocks(theme=gr.themes.Glass()) as demo:
with gr.Blocks() as demo:
    # chat bot section
    title = gr.Label("Azure OpenAI Enterprise KB Chatbot with Voice", label="", color="CornflowerBlue")
    chatbot = gr.Chatbot().style(height=500)
    checkbox_for_read = gr.Checkbox(label="Read result atomatically", visible=GlobalContext.ENABLE_VOICE)
    msg = gr.Textbox(label="Type your question below or click the voice botton to say")
    with gr.Row():
        clear = gr.Button("Clear")
        clear_and_move_to_history = gr.Button("Clear with Backup", visible=GlobalContext.SHOW_CHAT_BACKUP_AND_SETTINGS)
    with gr.Row(visible=GlobalContext.ENABLE_VOICE):
        radio = gr.Radio(["Say Chinese", "Say English", "Say Chinese output English", "Say English output Chinese"], value="Say Chinese", label="Voice setting")
        record_button = gr.Button("Click Here to Say")

    # single turn QA section
    gr.HTML('<hr size="18" width="100%" color="red">')
    title_QA = gr.Label("Enterprise KB QA Only", label="", color="lightblue", visible=GlobalContext.SHOW_SINGLE_TURN_QA)
    QA_Panel = gr.Chatbot(visible=GlobalContext.SHOW_SINGLE_TURN_QA).style(height=250)
    QA_question = gr.Textbox(label="Type your question below", visible=GlobalContext.SHOW_SINGLE_TURN_QA)

    # Azure OpenAI parapemter setting section (not integrated yet)
    gr.Markdown(
        """
    ---
    # 
    ---
    ```
    ** History and Settings **
    ```
    """, visible=GlobalContext.SHOW_CHAT_BACKUP_AND_SETTINGS)
    with gr.Box(visible=GlobalContext.SHOW_CHAT_BACKUP_AND_SETTINGS):
        with gr.Row():
            with gr.Column():
                last_round_chatbot = gr.Chatbot(label="Chatbot History")
            with gr.Column():
                with gr.Row():
                    slider_temperature = gr.Slider(0, 1, 0.5, step=0.1, label="Temperature", interactive=True)
                    slider_top_p = gr.Slider(0, 1, 0.7, step=0.1, label="Top_P", interactive=True)
                    slider_max_token = gr.Slider(50, 1050, 250, step=100, label="Max Token", interactive=True)
                txt_system_message = gr.Textbox(GlobalContext.chat_system_message_plain, label="System message for prompt", interactive=True)
                bt_update_system_message = gr.Button("Update System Message", interactive=False)

    # GUI event handlers
    msg.submit(chat_set_msg, [msg, chatbot], chatbot, queue=False).then(chat_set_bot, chatbot, [msg, chatbot]).then(readOuput, None, record_button)
    clear.click(clearHistory, None, chatbot, queue=False)
    clear_and_move_to_history.click(clearHistory_and_backup, chatbot, [chatbot, last_round_chatbot], queue=False)

    record_button.click(lambda: gr.Button.update("Recording...", interactive=False), None, record_button).then(
        startRecording, chatbot, chatbot).then(lambda: "Click Here to Say", None, record_button).then(
        chat_set_bot, chatbot, [msg, chatbot]).then(readOuput, None, record_button)

    radio.change(fn=radioChage, inputs=radio, outputs=None)
    checkbox_for_read.change(readOutSettingChange, checkbox_for_read)

    QA_question.submit(QA_set_msg, QA_question, QA_Panel, queue=False).then(QA_set_panel, QA_Panel, [QA_question, QA_Panel])

    txt_system_message.change(lambda: gr.Button.update(interactive=True), None, bt_update_system_message)
    bt_update_system_message.click(change_system_message, txt_system_message, chatbot).then(lambda: gr.Button.update(interactive=False), None, bt_update_system_message)

    slider_temperature.change(lambda x: change_Openai_param("temperature", x), slider_temperature, None)
    slider_max_token.change(lambda x: change_Openai_param("max_tokens", x), slider_max_token, None)
    slider_top_p.change(lambda x: change_Openai_param("top_p", x), slider_top_p, None)

# demo.launch(auth=("admin", "pass1234"), share=True)
demo.launch()
