# main.py
from fastapi import FastAPI, Request, HTTPException
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import os
from dotenv import load_dotenv
import openai
import pymysql
from datetime import datetime

load_dotenv()

app = FastAPI()

LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
MYSQL_DB = os.getenv("MYSQL_DB", "linebot")

if not LINE_CHANNEL_SECRET or not LINE_CHANNEL_ACCESS_TOKEN:
    raise Exception("LINE credentials are not set in .env")
if not OPENAI_API_KEY:
    raise Exception("OpenAI API key is not set in .env")

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)
openai.api_key = OPENAI_API_KEY

# MySQL 初始化
conn = pymysql.connect(host=MYSQL_HOST, user=MYSQL_USER, password=MYSQL_PASSWORD, database=MYSQL_DB, charset='utf8mb4')
cursor = conn.cursor()
cursor.execute('''
    CREATE TABLE IF NOT EXISTS messages (
        user_id VARCHAR(255),
        role VARCHAR(50),
        content TEXT,
        timestamp DATETIME
    ) CHARACTER SET utf8mb4
''')
conn.commit()

MAX_HISTORY = 10

def get_user_history(user_id):
    cursor.execute("SELECT role, content FROM messages WHERE user_id=%s ORDER BY timestamp ASC", (user_id,))
    rows = cursor.fetchall()
    return [{"role": role, "content": content} for role, content in rows][-MAX_HISTORY*2:]

def add_message(user_id, role, content):
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("INSERT INTO messages (user_id, role, content, timestamp) VALUES (%s, %s, %s, %s)",
                   (user_id, role, content, timestamp))
    conn.commit()

def clear_history(user_id):
    cursor.execute("DELETE FROM messages WHERE user_id=%s", (user_id,))
    conn.commit()

@app.post("/callback")
async def callback(request: Request):
    signature = request.headers.get("X-Line-Signature")

    body = await request.body()
    body = body.decode("utf-8")

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    return "OK"

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    user_message = event.message.text.strip()

    if user_message.lower() == "/reset":
        clear_history(user_id)
        reply = "對話紀錄已清除，從頭開始吧！"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
        return

    if user_message.lower() == "/history":
        history = get_user_history(user_id)
        if not history:
            reply = "目前沒有紀錄喔～"
        else:
            reply = "最近的對話紀錄：\n\n" + "\n".join([
                f"[{h['role']}] {h['content']}" for h in history
            ])
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
        return

    add_message(user_id, "user", user_message)

    messages = [{"role": "system", "content": "要簡短回答，不要超過50字，中文要用zh-TW。"}]
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

    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply)
    )

