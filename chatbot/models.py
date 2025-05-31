# chatbot/models.py
from django.db import models
from django.contrib.auth.models import User
import uuid

class SystemPromptRule(models.Model):
    trigger_text = models.CharField(max_length=255, unique=True, help_text='觸發詞，例如：我想學英文')
    system_prompt = models.TextField(help_text='對應的 system prompt 內容')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='建立時間')
    created_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL,
        verbose_name='建立者', related_name='system_prompts'
    )

    def __str__(self):
        return self.trigger_text

class Message(models.Model):
    user_id = models.CharField(max_length=255)
    role = models.CharField(max_length=50)
    content = models.TextField()
    system_prompt_rule = models.ForeignKey(SystemPromptRule, null=True, blank=True, on_delete=models.SET_NULL)
    session_id = models.UUIDField(default=uuid.uuid4, editable=False)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.timestamp} - {self.user_id} ({self.role})"

class SkipKeyword(models.Model):
    text = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return self.text
