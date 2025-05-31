from django.contrib import admin
from .models import Message, SkipKeyword, SystemPromptRule

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('user_id', 'role', 'content', 'timestamp', 'session_id')
    search_fields = ("user_id", "content", "session_id")
    list_filter = ("session_id",)

@admin.register(SkipKeyword)
class SkipKeywordAdmin(admin.ModelAdmin):
    list_display = ('text', 'created_at', 'created_by')
    search_fields = ('text',)

    def save_model(self, request, obj, form, change):
        if not obj.pk:  # 如果是新增
            obj.created_by = request.user  # 自動設為目前登入的使用者
        super().save_model(request, obj, form, change)

@admin.register(SystemPromptRule)
class SystemPromptRuleAdmin(admin.ModelAdmin):
    list_display = ("trigger_text", "created_by", "created_at")
    search_fields = ("trigger_text", "system_prompt")
    readonly_fields = ("created_at",)

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)