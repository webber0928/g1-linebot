# chatbot/models.py
from django.db import models

class Message(models.Model):
    user_id = models.CharField(max_length=255)
    role = models.CharField(max_length=50)
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.timestamp} - {self.user_id} ({self.role})"
