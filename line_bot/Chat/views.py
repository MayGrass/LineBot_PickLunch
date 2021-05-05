from line_bot.Chat.models import *
from django.conf import settings
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError, LineBotApiError
from linebot.models import (
    MessageEvent,
    TextMessage,
    JoinEvent,
    LeaveEvent,
    FollowEvent,
    PostbackEvent,
)
from .chat_bot import ChatBot
import logging
import json
from django.db import transaction

logger = logging.getLogger(__name__)

line_bot_api = LineBotApi(settings.LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(settings.LINE_CHANNEL_SECRET)

chat_bot = ChatBot(line_bot_api)

# /callback 負責接收line傳過來的訊息
@csrf_exempt
def callback(request):
    if request.method == "POST":
        signature = request.headers["X-Line-Signature"]
        body = request.body.decode("utf-8")

        try:
            handler.handle(body, signature)
        except InvalidSignatureError:
            print(
                print("Invalid signature. Please check your channel access token/channel secret.")
            )
            return HttpResponseForbidden()
        except LineBotApiError:
            return HttpResponseBadRequest()
        else:
            return HttpResponse()
    else:
        return HttpResponseBadRequest()


# 處理傳送過來的訊息
@handler.add(MessageEvent, message=TextMessage)
def handler_message(event):
    chat_bot.receive_command(event)


# 處理剛加入群組的事件
@handler.add(JoinEvent)
def save_group_data(event):
    chat_bot.save_group_data(event)


# 處理離開群組的事件
@handler.add(LeaveEvent)
def delete_group_data(event):
    ...


# 處理加機器人當好友的事件
@handler.add(FollowEvent)
def follow_bot(event):
    line_bot_api.reply_message(
        event.reply_token, TextMessage(text="歡迎加此機器人好友，此機器人僅提供群組服務，把他邀進群組吧！")
    )


# 處理加機器人當好友的事件
@handler.add(PostbackEvent)
def postback(event):
    data = json.loads(event.postback.data)
    # 群組管理員可將店家與指定群組解除綁定
    if (
        data.get("event") == "delete_store"
        and Group.objects.filter(
            group_id=data.get("group_id"), admin__user_id=event.source.user_id
        ).exists()
    ):
        try:
            with transaction.atomic():
                group = Group.objects.get(group_id=data["group_id"])
                store = Store.objects.get(id=data["store_id"])
                store.group.remove(group)
        except:
            reply_text = f"系統發生錯誤，無法刪除『{data['store_name']}』"
        else:
            reply_text = f"已將『{data['store_name']}』從美食清單中移除"
        finally:
            line_bot_api.reply_message(event.reply_token, TextMessage(text=reply_text))
    else:
        line_bot_api.reply_message(event.reply_token, TextMessage(text="只有群組管理員才可執行刪除！"))
