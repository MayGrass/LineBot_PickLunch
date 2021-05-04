from .models import *
import logging
from linebot.models import (
    TextMessage,
    TemplateSendMessage,
    ConfirmTemplate,
    ButtonsTemplate,
    MessageAction,
    URIAction,
    TextSendMessage,
    QuickReplyButton,
    QuickReply,
    FlexSendMessage,
)
from django.db import transaction
from django.core.cache import cache as redis
import requests
from django.conf import settings
from django.db.models import Q
import json

logger = logging.getLogger(__name__)


class ChatBot:
    def __init__(self, line_bot_api):
        self.line_bot_api = line_bot_api
        self.event = None
        self.text = None
        self.group_id = None
        self.user_id = None
        self.google_map_api = GoogleMapAPI()  # google map api串接
        self.command_dict = {
            "!help": self.__command_list,
            "!admin": self.__set_group_admin,
            "!add": self.__starting_add_store,
            "!吃": self.__random_eat_store,
            "!ls": self.__list_eat_store,
            "!取消": self.__cancle,
        }  # 一層指令
        self.redis_key = {"add": self.__search_store, "save_store": self.__save_store}  # 二層後指令

    # 接收資訊判斷要做什麼事
    def receive_command(self, event):
        logger.debug(f"receive event: {event}")
        self.event = event
        self.group_id = event.source.group_id
        if not self.group_id:
            self.line_bot_api.reply_message(
                self.event.reply_token, TextMessage(text="把機器人加入群組才能發揮他的功能歐")
            )
        self.user_id = event.source.user_id
        self.text = self.event.message.text
        self.command_dict.get(self.text, self.__second_command)()

    # 二層後的互動
    def __second_command(self):
        for key, function in self.redis_key.items():
            if redis.get(f"{self.group_id}:{key}"):
                function()
                break
        else:
            self.__do_nothing()

    def __do_nothing(self):
        logger.debug("do nothing")
        pass

    # 指令集
    def __command_list(self):
        command_list = [
            QuickReplyButton(action=MessageAction(label=command, text=command))
            for command in self.command_dict.keys()
        ]
        self.line_bot_api.reply_message(
            self.event.reply_token,
            TextSendMessage(
                text="機器人指令集",
                quick_reply=QuickReply(items=command_list),
            ),
        )

    # 儲藏群組資料
    def save_group_data(self, event):
        # 獲得群組資料
        group_id = event.source.group_id
        group_summary = self.line_bot_api.get_group_summary(group_id)
        group_name = group_summary.group_name
        # 將群組資料加入資料庫
        try:
            Group.objects.get_or_create(group_id=group_id, group_name=group_name)
        except:
            logger.exception(f"{group_name} database create fail!")
        else:
            self.line_bot_api.reply_message(event.reply_token, TextMessage(text="群組資料成功存進資料庫囉！"))

    # 設定社團管理員
    def __set_group_admin(self):
        # 取得使用者資料
        user_profile = self.line_bot_api.get_group_member_profile(self.group_id, self.user_id)
        user_name = user_profile.display_name
        # 將管理員資料存進資料庫
        try:
            reply = []
            group_admin, created = GroupAdmin.objects.get_or_create(
                user_id=self.user_id, user_name=user_name
            )
            with transaction.atomic():
                group = Group.objects.get(group_id=self.group_id)
                if not group.admin:
                    group.admin = group_admin
                    group.save()
                    reply.append(TextMessage(text=f"已將「{user_name}」設為此群組的機器人管理員"))
                else:
                    reply.append(TextMessage(text=f"機器人管理員已是「{group.admin.user_name}」"))
                    reply.append(TextMessage(text="目前還沒有設置多個管理者的打算"))
        except:
            logger.exception(f"{user_name} set admin fail!")
        else:
            self.line_bot_api.reply_message(self.event.reply_token, reply)

    # 開啟新增店家資訊功能
    def __starting_add_store(self):
        # 限定管理員開啟功能
        if Group.objects.filter(group_id=self.group_id, admin__user_id=self.user_id).exists():
            redis.set(f"{self.group_id}:add", True, 60)  # 60秒存活
            self.line_bot_api.reply_message(
                self.event.reply_token, TextMessage(text="店家加入功能已開啟一分鐘，可以開始搜尋店家")
            )
        else:
            self.__do_nothing()

    # 搜尋店家資訊
    def __search_store(self):
        place_result = self.google_map_api.place_search(store_name=self.text)  # 店家資料搜尋
        if place_result:
            rate = f"{place_result.get('rating')}顆星" if place_result.get("rating") else "尚無評價"
            reply = f"{place_result['name']}\n評價: {rate}\n{place_result['url']}"
            redis.set(f"{self.group_id}:save_store", place_result, 30)  # 店家資訊暫存
            redis.set(f"{self.group_id}:add", False, 60)  # 暫時關閉店家查詢功能
        else:
            reply = "Google地圖搜尋無結果"
        self.line_bot_api.reply_message(
            self.event.reply_token,
            [
                TextMessage(text=reply),
                TemplateSendMessage(
                    alt_text="店家查詢確認",
                    template=ConfirmTemplate(
                        text="確定是這家嗎?",
                        actions=[
                            MessageAction(label="對", text="Yes"),
                            MessageAction(label="我要再查一次", text="Again"),
                        ],
                    ),
                ),
            ],
        )

    # 將店家資訊存進資料庫
    def __save_store(self):
        reply = []
        # 兩個選項之外的回應就繼續查詢店家
        if self.text != "Yes" and self.text != "Again":
            self.__search_store()
        elif self.text == "Yes":
            store_data = redis.get(f"{self.group_id}:save_store")
            try:
                with transaction.atomic():
                    # 新增或者獲得店家資訊
                    store, created = Store.objects.get_or_create(
                        store_name=store_data["name"],
                        store_address=store_data["formatted_address"],
                        store_phone=store_data.get("formatted_phone_number"),
                        google_map_url=store_data["url"],
                    )
                    # 如果有店家照片再存
                    if store_data.get("photos"):
                        store.google_photo_url = self.google_map_api.place_photo(
                            store_data["photos"][0]["photo_reference"]
                        )
                        store.save()
                    # 為店家綁定群組
                    group = Group.objects.get(group_id=self.group_id)
                    store.group.add(group)
                    # 新增商家種類
                    if created:
                        for type in store_data["types"]:
                            store_type, _ = StoreType.objects.get_or_create(type_name=type)
                            store.store_type.add(store_type)
                        logger.debug("商家種類新增")
            except:
                logging.exception(f"{store_data['name']} saving to database failed!")
            else:
                reply.append(TextMessage(text="資料成功加進去囉!"))
        elif self.text == "Again":
            reply.append(TextMessage(text="店家查詢繼續開放一分鐘"))

        # 如果第一個if條件有達到，這邊不會執行
        redis.set(f"{self.group_id}:add", True, 60)  # 重新開放店家搜尋
        redis.delete(f"{self.group_id}:save_store")  # 刪除店家資料暫存
        self.line_bot_api.reply_message(self.event.reply_token, reply)

    # 隨機抽一家去吃
    def __random_eat_store(self):
        # 隨機查商家清單裡 type name in (food or restaurant) and not cafe
        random_result = (
            Store.objects.filter(
                Q(store_type__type_name__in=["food", "restaurant"])
                & ~Q(store_type__type_name="cafe")
                & Q(group=Group.objects.get(group_id=self.group_id))
            )
            .order_by("?")
            .values()
            .distinct()
            .first()
        )
        if random_result:
            reply = (
                TemplateSendMessage(
                    alt_text="店家資訊",
                    template=ButtonsTemplate(
                        thumbnail_image_url=random_result["google_photo_url"],
                        title=random_result["store_name"],
                        text=f"電話: {random_result['store_phone']}\n地址: {random_result['store_address']}",
                        actions=[
                            MessageAction(label="再抽一次", text="!吃"),
                            URIAction(label="GoogleMap", uri=random_result["google_map_url"]),
                        ],
                    ),
                ),
            )
        else:
            reply = (TextMessage(text="目前群組裡沒有任何商家清單，管理員請先輸入 !add 來開啟美食清單加入功能"),)
        self.line_bot_api.reply_message(
            self.event.reply_token,
            reply,
        )

    # 列出該群組目前所有吃的店家
    def __list_eat_store(self):
        eat_store_list = (
            Store.objects.filter(
                Q(store_type__type_name__in=["food", "restaurant"])
                & ~Q(store_type__type_name="cafe")
                & Q(group=Group.objects.get(group_id=self.group_id))
            )
            .values("id", "store_name", "store_address", "store_phone", "google_map_url")
            .distinct()
        )
        if eat_store_list:
            contents = [
                {
                    "type": "text",
                    "text": "美食清單",
                    "weight": "bold",
                    "size": "lg",
                    "adjustMode": "shrink-to-fit",
                    "offsetBottom": "sm",
                },
                {"type": "separator"},
            ]
            for store in eat_store_list:
                contents.append(
                    {
                        "type": "box",
                        "layout": "horizontal",
                        "spacing": "xs",
                        "contents": [
                            {
                                "type": "box",
                                "layout": "vertical",
                                "contents": [
                                    {
                                        "type": "text",
                                        "text": store["store_name"],
                                        "size": "sm",
                                        "color": "#555555",
                                        "adjustMode": "shrink-to-fit",
                                        "wrap": True,
                                    },
                                    {
                                        "type": "text",
                                        "text": store["store_phone"],
                                        "size": "sm",
                                        "color": "#555555",
                                        "adjustMode": "shrink-to-fit",
                                        "wrap": True,
                                    },
                                    {
                                        "type": "text",
                                        "text": store["store_address"],
                                        "size": "sm",
                                        "color": "#555555",
                                        "adjustMode": "shrink-to-fit",
                                        "wrap": True,
                                    },
                                ],
                                "flex": 2,
                                "spacing": "xs",
                            },
                            {
                                "type": "box",
                                "layout": "vertical",
                                "contents": [
                                    {
                                        "type": "button",
                                        "action": {
                                            "type": "uri",
                                            "label": "地圖",
                                            "uri": store["google_map_url"],
                                        },
                                        "style": "primary",
                                        "height": "sm",
                                        "color": "#0080FF",
                                    },
                                    {
                                        "type": "button",
                                        "action": {
                                            "type": "postback",
                                            "label": "刪除",
                                            "data": json.dumps(
                                                {
                                                    "event": "delete_store",
                                                    "group_id": self.group_id,
                                                    "store_id": store["id"],
                                                    "store_name": store["store_name"],
                                                }
                                            ),
                                        },
                                        "style": "primary",
                                        "height": "sm",
                                        "color": "#EA0000",
                                    },
                                ],
                                "flex": 1,
                                "spacing": "xs",
                                "paddingTop": "md",
                                "alignItems": "center",
                            },
                        ],
                        "alignItems": "center",
                        "paddingBottom": "md",
                    }
                )
                contents.append({"type": "separator"})
            reply = FlexSendMessage(
                alt_text="美食清單",
                contents={
                    "type": "bubble",
                    "body": {"type": "box", "layout": "vertical", "contents": contents},
                    "styles": {"footer": {"separator": True}},
                },
            )
        else:
            reply = TextMessage(text="目前群組裡沒有任何商家清單，管理員請先輸入 !add 來開啟美食清單加入功能")
        self.line_bot_api.reply_message(
            self.event.reply_token,
            reply,
        )

    # 取消目前所有互動功能
    def __cancle(self):
        redis.delete_pattern(f"{self.group_id}:*")  # 講此群組的redis暫存都刪除
        self.line_bot_api.reply_message(self.event.reply_token, TextMessage(text="互動功能取消"))


class GoogleMapAPI:
    def __init__(self):
        self.api_key = settings.GOOGLE_API_KEY
        self.url = "https://maps.googleapis.com/maps/api/place/"

    def place_search(self, store_name):
        api_result = requests.get(
            f"{self.url}findplacefromtext/json?input={store_name}&inputtype=textquery&fields=place_id&key={self.api_key}"
        ).json()
        if api_result.get("status", False) == "OK":
            place_id = api_result["candidates"][0]["place_id"]
            return self.__place_detail(place_id)
        else:
            return False

    def __place_detail(self, place_id):
        fields = "name,rating,formatted_address,formatted_phone_number,url,type,photo"
        api_result = requests.get(
            f"{self.url}details/json?place_id={place_id}&fields={fields}&language=zh-TW&key={self.api_key}"
        ).json()
        if api_result.get("status", False) == "OK":
            result = api_result["result"]
        else:
            result = False
        return result

    def place_photo(self, photoreference):
        return f"{self.url}photo?maxwidth=400&photoreference={photoreference}&key={self.api_key}"
