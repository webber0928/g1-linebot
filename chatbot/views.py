# chatbot/views.py
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse, HttpResponseBadRequest
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from .models import Message, SkipKeyword, SystemPromptRule, LineUser
import os
import openai
import uuid
from dotenv import load_dotenv

load_dotenv()

LINE_CHANNEL_SECRET = os.getenv('LINE_CHANNEL_SECRET')
LINE_CHANNEL_ACCESS_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

if not LINE_CHANNEL_SECRET or not LINE_CHANNEL_ACCESS_TOKEN:
    raise Exception('LINE credentials are not set in .env')
if not OPENAI_API_KEY:
    raise Exception('OpenAI API key is not set in .env')

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)
openai.api_key = OPENAI_API_KEY

MAX_HISTORY = 10

def get_user_history(user_id, session_id):
    messages = Message.objects.filter(user_id=user_id, session_id=session_id).order_by('timestamp')
    return [{'role': m.role, 'content': m.content} for m in messages][-MAX_HISTORY*2:]

def add_message(user_id, role, content, session_id, system_prompt_rule_id=None):
    system_prompt_rule = None
    if system_prompt_rule_id:
        try:
            system_prompt_rule = SystemPromptRule.objects.get(id=system_prompt_rule_id)
        except SystemPromptRule.DoesNotExist:
            pass  # 安全防呆，不讓 get 出錯導致整個掛掉

    Message.objects.create(
        user_id=user_id,
        role=role,
        content=content,
        session_id=session_id,
        system_prompt_rule=system_prompt_rule
    )

def clear_history(user_id):
    Message.objects.filter(user_id=user_id).delete()

@csrf_exempt
def callback(request):
    signature = request.headers.get('X-Line-Signature')
    body = request.body.decode('utf-8')

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        return HttpResponseBadRequest('Invalid signature')

    return HttpResponse('OK')

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    user_message = event.message.text.strip()

    # 確保 LineUser 存在
    line_user, created = LineUser.objects.get_or_create(user_id=user_id)
    if created:
        print(f"新使用者：{line_user.user_id}，預設語言：{line_user.language}")

     # 檢查是否為應跳過的關鍵字
    if SkipKeyword.objects.filter(text__iexact=user_message).exists():
        return

    # 語言切換指令
    if user_message.lower().startswith('/lang '):
        new_lang = user_message[6:].strip().lower()

        if new_lang in ['zh', 'en']:
            if new_lang != line_user.language:
                line_user.language = new_lang
                line_user.save()
                reply = (
                    "語言已更新為：繁體中文" if new_lang == 'zh'
                    else "Language updated to: English"
                )
            else:
                reply = (
                    "你目前已經是繁體中文語系了喔！" if new_lang == 'zh'
                    else "You're already using English."
                )
        else:
            reply = (
                "請輸入有效語言代碼：`zh`（繁體中文）或 `en`（English）"
            )

        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
        return

    if user_message.lower() == '/reset':
        clear_history(user_id)
        reply = '對話紀錄已清除，從頭開始吧！'
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
        return

    if user_message.lower() == '/history':
        latest_msg = Message.objects.filter(user_id=user_id).order_by('-timestamp').first()
        if latest_msg:
            session_id = latest_msg.session_id
            history = get_user_history(user_id, session_id)
        else:
            history = []
        reply = '目前沒有紀錄喔～' if not history else (
            '最近的對話紀錄：\n\n' + '\n'.join([f"[{h['role']}] {h['content']}" for h in history])
        )
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
        return

    system_prompt_obj = SystemPromptRule.objects.filter(trigger_text__iexact=user_message).first()
    if system_prompt_obj:
        system_prompt = system_prompt_obj.system_prompt
        session_id = uuid.uuid4()
        system_prompt_rule_id = system_prompt_obj.id
    else:
        latest_msg = Message.objects.filter(user_id=user_id).order_by('-timestamp').first()
        if latest_msg and latest_msg.system_prompt_rule:
            # 取到 SystemPromptRule instance 的 system_prompt
            system_prompt = latest_msg.system_prompt_rule.system_prompt + '[對話語系] 語系請用' + line_user.language
            system_prompt_rule_id = latest_msg.system_prompt_rule.id
        else:
            # 如果沒紀錄，fallback 給一個預設的 prompt
            system_prompt = '要簡短回答，不要超過50字，對話的語系要用' + line_user.language
            system_prompt_rule_id = None
        session_id = latest_msg.session_id if latest_msg else uuid.uuid4()

    add_message(user_id, 'user', user_message, session_id, system_prompt_rule_id)

    messages = [{'role': 'system', 'content': system_prompt}]
    messages += get_user_history(user_id, session_id)

    try:
        response = openai.chat.completions.create(
            model='o4-mini',
            messages=messages
        )
        reply = response.choices[0].message.content.strip()
        add_message(user_id, 'assistant', reply, session_id, system_prompt_rule_id)
    except Exception as e:
        reply = f"抱歉，我出錯了：{str(e)}"

    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))

