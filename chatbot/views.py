# chatbot/views.py
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse, HttpResponseBadRequest
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from .models import Message, SkipKeyword, SystemPromptRule
import os
import openai
from dotenv import load_dotenv

load_dotenv()

LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not LINE_CHANNEL_SECRET or not LINE_CHANNEL_ACCESS_TOKEN:
    raise Exception("LINE credentials are not set in .env")
if not OPENAI_API_KEY:
    raise Exception("OpenAI API key is not set in .env")

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)
openai.api_key = OPENAI_API_KEY

MAX_HISTORY = 10

def get_user_history(user_id):
    messages = Message.objects.filter(user_id=user_id).order_by("timestamp")
    return [{"role": m.role, "content": m.content} for m in messages][-MAX_HISTORY*2:]

def add_message(user_id, role, content):
    Message.objects.create(user_id=user_id, role=role, content=content)

def clear_history(user_id):
    Message.objects.filter(user_id=user_id).delete()

@csrf_exempt
def callback(request):
    signature = request.headers.get("X-Line-Signature")
    body = request.body.decode("utf-8")

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        return HttpResponseBadRequest("Invalid signature")

    return HttpResponse("OK")

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    user_message = event.message.text.strip()

     # 檢查是否為應跳過的關鍵字
    if SkipKeyword.objects.filter(text__iexact=user_message).exists():
        return

    if user_message.lower() == "/reset":
        clear_history(user_id)
        reply = "對話紀錄已清除，從頭開始吧！"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
        return

    if user_message.lower() == "/history":
        history = get_user_history(user_id)
        reply = "目前沒有紀錄喔～" if not history else (
            "最近的對話紀錄：\n\n" + "\n".join([f"[{h['role']}] {h['content']}" for h in history])
        )
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
        return

    add_message(user_id, "user", user_message)

    system_prompt_obj = SystemPromptRule.objects.filter(trigger_text__iexact=user_message).first()
    if system_prompt_obj:
        system_prompt = system_prompt_obj.system_prompt
    else:
        system_prompt = "要簡短回答，不要超過50字，中文要用zh-TW。"

    messages = [{"role": "system", "content": system_prompt}]

    messages += get_user_history(user_id)

    try:
        response = openai.chat.completions.create(
            model="o4-mini",
            messages=messages
        )
        reply = response.choices[0].message.content.strip()
        add_message(user_id, "assistant", reply)
    except Exception as e:
        reply = f"抱歉，我出錯了：{str(e)}"

    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))

