from line_bot.Chat.models import Group
from django.conf import settings
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt

from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError, LineBotApiError
from linebot.models import MessageEvent, TextMessage, TextSendMessage, JoinEvent
from .chat_bot import ChatBot
import logging

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
