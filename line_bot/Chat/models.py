from django.db import models

# Create your models here.
class Store(models.Model):
    store_name = models.CharField(max_length=50, help_text="商家名稱", unique=True)
    store_address = models.CharField(max_length=100, help_text="商家地址")
    store_type = models.ForeignKey(
        "StoreType",
        on_delete=models.PROTECT,
    )
    group = models.ManyToManyField("Group", blank=True)
    create_time = models.DateTimeField(auto_now_add=True)


class StoreType(models.Model):
    type_name = models.CharField(max_length=5)


class Group(models.Model):
    group_id = models.CharField(max_length=40, unique=True)
    group_name = models.CharField(max_length=100)
    admin = models.ForeignKey("GroupAdmin", on_delete=models.PROTECT, null=True)


class GroupAdmin(models.Model):
    user_id = models.CharField(max_length=40, unique=True)
    user_name = models.CharField(max_length=40)
