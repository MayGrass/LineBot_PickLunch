from django.db import models

# Create your models here.
class Store(models.Model):
    store_name = models.CharField(max_length=50, help_text="商家名稱", unique=True)
    store_address = models.CharField(max_length=100, help_text="商家地址")
    store_type = models.ManyToManyField("StoreType")
    store_phone = models.CharField(max_length=20, null=True, help_text="商家號碼")
    google_map_url = models.URLField(unique=True, help_text="Google map商家網址")
    google_photo_url = models.URLField(default="https://i.imgur.com/v8oKeSg.png", max_length=500)
    group = models.ManyToManyField("Group", blank=True)
    create_time = models.DateTimeField(auto_now_add=True)


class StoreType(models.Model):
    type_name = models.CharField(max_length=50, unique=True, help_text="商家類型")


class Group(models.Model):
    group_id = models.CharField(max_length=40, unique=True, help_text="Line群組ID")
    group_name = models.CharField(max_length=100, help_text="Line群組名稱")
    admin = models.ForeignKey(
        "GroupAdmin", on_delete=models.SET_NULL, null=True, help_text="Line群組機器人管理者"
    )


class GroupAdmin(models.Model):
    user_id = models.CharField(max_length=40, unique=True, help_text="Line使用者ID（唯一值不是使用者設定的）")
    user_name = models.CharField(max_length=40, help_text="Line使用者名稱（資料參考用，Line使用者可以隨時改名）")
