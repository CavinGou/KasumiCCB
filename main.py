import asyncio
import io
import logging
import random
import traceback
from pathlib import Path
from typing import List, Optional
from urllib.parse import urlparse

import aiohttp
import astrbot.api.event.filter as filter
from astrbot.api.all import *
from astrbot.api.message_components import *

from .bang_avatar import render_card, ensure_resources, WifeData

logger = logging.getLogger(__name__)

# 尝试导入Pillow
try:
    from PIL import Image as PILImage
    PILLOW_INSTALLED = True
except ImportError:
    PILLOW_INSTALLED = False

PLUGIN_DIR = Path(__file__).parent


class GroupMember:
    """群成员数据类"""
    def __init__(self, data: dict):
        self.user_id: str = str(data["user_id"])
        self.nickname: str = data.get("nickname", "")
        self.card: str = data.get("card", "")

    @property
    def display_info(self) -> str:
        return f"{self.card or self.nickname}({self.user_id})"


@register("BangAvatar", "jmt059", "BanGDream风格卡片渲染插件", "v1.0.0")
class BangAvatarPlugin(Star):
    def __init__(self, context: Context, config: dict):
        super().__init__(context)
        self.config = config
        self._init_napcat_config()

        # 初始化卡片资源
        if PILLOW_INSTALLED:
            asyncio.create_task(self._init_resources())

    def _init_napcat_config(self):
        try:
            hosts_str = self.config.get("napcat_host") or "127.0.0.1:3000"
            self.napcat_hosts = [host.strip() for host in hosts_str.split(",")]
            self.current_host_index = 0
            self.timeout = self.config.get("request_timeout") or 10

            for host in self.napcat_hosts:
                parsed = urlparse(f"http://{host}")
                if not parsed.hostname or not parsed.port:
                    raise ValueError(f"无效的Napcat地址格式: {host}")

            logger.info(f"✅ BangAvatar: 已加载 {len(self.napcat_hosts)} 个Napcat主机")
        except Exception as e:
            raise RuntimeError(f"BangAvatar: Napcat配置错误: {e}")

    def _get_current_napcat_host(self):
        if not hasattr(self, 'napcat_hosts') or not self.napcat_hosts:
            return "127.0.0.1:3000"
        host = self.napcat_hosts[self.current_host_index]
        self.current_host_index = (self.current_host_index + 1) % len(self.napcat_hosts)
        return host

    async def _init_resources(self):
        """初始化卡片素材资源"""
        try:
            src_path = PLUGIN_DIR / "bang_avatar" / "resources"
            await ensure_resources(src_path)
            logger.info("✅ BangAvatar: 资源初始化完成")
        except Exception as e:
            logger.error(f"❌ BangAvatar: 资源初始化失败: {e}")

    async def _get_members(self, group_id: str) -> Optional[List[GroupMember]]:
        """通过 NapCat API 获取群成员列表"""
        for _ in range(len(self.napcat_hosts)):
            host = self._get_current_napcat_host()
            try:
                headers = {"Authorization": f"Bearer {self.config.get('napcat_token', '')}"}
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        f"http://{host}/get_group_member_list",
                        headers=headers,
                        json={"group_id": group_id},
                        timeout=self.timeout,
                    ) as resp:
                        data = await resp.json()
                        if "data" in data and isinstance(data["data"], list):
                            members = [GroupMember(m) for m in data["data"] if "user_id" in m]
                            if members:
                                return members
            except Exception:
                logger.error(f"BangAvatar: 连接 {host} 失败: {traceback.format_exc()}")

        return None

    async def _fetch_avatar_bytes(self, user_id: str) -> Optional[bytes]:
        """下载头像原始 bytes"""
        url = f"http://q.qlogo.cn/headimg_dl?dst_uin={user_id}&spec=640"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=self.timeout) as resp:
                    if resp.status == 200 and 'image' in resp.headers.get('Content-Type', ''):
                        return await resp.read()
        except Exception as e:
            logger.error(f"BangAvatar: 下载头像失败: {e}")
        return None

    async def _generate_card(self, user_id: str, target_id: str) -> Optional[Image]:
        """生成 BanGDream 风格卡片"""
        try:
            src_path = PLUGIN_DIR / "bang_avatar" / "resources"
            if not (src_path / "card-2.png").exists():
                logger.warning("BangAvatar: 资源未就绪")
                return None

            avatar_bytes = await self._fetch_avatar_bytes(target_id)
            if not avatar_bytes:
                return None

            wife_data = WifeData(user_id=user_id, target_id=target_id).generate()
            card_bytes = await render_card(wife_data, src_path, avatar_bytes=avatar_bytes)
            return Image.fromBytes(card_bytes)
        except Exception:
            logger.error(f"BangAvatar: 生成卡片失败: {traceback.format_exc()}")
            return None

    # --------------- 命令 ---------------
    @filter.regex(r"^(娶群友|qqy|ccb)$")
    async def bang_avatar_command(self, event: AstrMessageEvent):
        if not hasattr(event.message_obj, "group_id"):
            yield event.plain_result("此命令仅限群聊中使用。")
            return

        if not PILLOW_INSTALLED:
            yield event.plain_result("❌ 未安装 Pillow 库，无法使用卡片功能。")
            return

        try:
            group_id = str(event.message_obj.group_id)
            user_id = str(event.get_sender_id())
            bot_id = str(event.message_obj.self_id)

            members = await self._get_members(group_id)
            if not members:
                yield event.plain_result("⚠️ 当前群组状态异常，请联系管理员")
                return

            valid = [m for m in members if str(m.user_id) not in {user_id, bot_id}]
            if not valid:
                yield event.plain_result("😢 群里暂时没有其他人")
                return

            target = random.choice(valid)
            target_display = f"{target.card or target.nickname}({target.user_id})"
            sender_name = event.get_sender_name()
            sender_display = f"{sender_name}({user_id})"

            message_elements = []

            card_img = await self._generate_card(user_id, str(target.user_id))
            if card_img:
                message_elements.append(card_img)
            else:
                yield event.plain_result("❌ 卡片生成失败，请稍后重试")
                return

            message_elements.append(Plain(f"🎰 {sender_display} 娶到 {target_display}了哦~"))
            yield event.chain_result(message_elements)

        except Exception:
            logger.error(f"BangAvatar: 异常: {traceback.format_exc()}")
            yield event.plain_result("❌ 发生异常，请联系开发者")
