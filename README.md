# g1-linebot
期末作業 - linebot

## 建立環境
```
conda create -n linebot-mini python=3.10 --no-default-packages
python3 -m venv venv
# window 進入方式
source venv/Scripts/activate

pip install django
django-admin startproject linebot .
```

## 啟動環境
```
python manage.py makemigrations chatbot
python manage.py migrate

python manage.py runserver
```

## 後臺帳號密碼
```
python manage.py createsuperuser

# 建立完成後，可以用這個帳號登入 http://localhost:8000/admin/
```