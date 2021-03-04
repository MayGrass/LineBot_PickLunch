from .models import *
import logging
from linebot.models import TextMessage

logger = logging.getLogger(__name__)


class ChatBot:
    def __init__(self, line_bot_api, handler):
        self.line_bot_api = line_bot_api
        self.handler = handler

    def save_group_data(self, event):
        # 獲得群組資料
        group_id = event.source.group_id
        group_summary = self.line_bot_api.get_group_summary(group_id)
        group_name = group_summary.group_name
        # 將群組資料加入資料庫
        try:
            Group.objects.create(group_id=group_id, group_name=group_name)
        except:
            logger.exception(f"{group_name} database create fail!")
        else:
            self.line_bot_api.reply_message(event.reply_token, TextMessage(text="群組資料成功存進資料庫囉！"))

    # 設定社團管理員
    def __set_group_admin(self, event):
        # 取得使用者資料
        group_id = event.source.group_id
        user_id = event.source.user_id
        user_profile = self.line_bot_api.get_group_member_profile(group_id, user_id)
        user_name = user_profile.display_name
        # 將管理員資料存進資料庫
        try:
            GroupAdmin.objects.create(user_id=user_id, user_name=user_name)
        except:
            logger.exception(f"{user_name} database create fail! Maybe already exist")
        else:
            self.line_bot_api.reply_message(
                event.reply_token, TextMessage(text=f"已將 {user_name} 設為此群組的機器人管理員")
            )
