from django.contrib.auth.models import User
from django.db import models


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    birthdate = models.DateField(blank=True, null=True)
    api_key = models.CharField(max_length=64, null=True)
    api_secret = models.CharField(max_length=64, null=True)

    def __str__(self):
        return "Профиль пользователя %s" % self.user.username


# Create your models here.
