import asyncio
import io
import json
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


@register("KasumiCCB", "CavinGou", "提取自kasumi的娶群友功能", "v1.0.0")
class KasumiCCBPlugin(Star):
    def __init__(self, context: Context, config: dict):
        super().__init__(context)
        self.config = config
        self._init_napcat_config()

        # 数据持久化目录 (AstrBot 数据目录下)
        from astrbot.core.utils.astrbot_path import get_astrbot_data_path
        self.data_dir = Path(get_astrbot_data_path()) / "plugin_data" / "KasumiCCB"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._blocklist_path = self.data_dir / "blocklist.json"

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

            logger.info(f"✅ KasumiCCB: 已加载 {len(self.napcat_hosts)} 个Napcat主机")
        except Exception as e:
            raise RuntimeError(f"KasumiCCB: Napcat配置错误: {e}")

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
            logger.info("✅ KasumiCCB: 资源初始化完成")
        except Exception as e:
            logger.error(f"❌ KasumiCCB: 资源初始化失败: {e}")

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
                logger.error(f"KasumiCCB: 连接 {host} 失败: {traceback.format_exc()}")

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
            logger.error(f"KasumiCCB: 下载头像失败: {e}")
        return None

    async def _generate_card(self, user_id: str, target_id: str) -> Optional[Image]:
        """生成 BanGDream 风格卡片"""
        try:
            src_path = PLUGIN_DIR / "bang_avatar" / "resources"
            if not (src_path / "card-2.png").exists():
                logger.warning("KasumiCCB: 资源未就绪")
                return None

            avatar_bytes = await self._fetch_avatar_bytes(target_id)
            if not avatar_bytes:
                return None

            wife_data = WifeData(user_id=user_id, target_id=target_id).generate()
            card_bytes = await render_card(wife_data, src_path, avatar_bytes=avatar_bytes)
            return Image.fromBytes(card_bytes)
        except Exception:
            logger.error(f"KasumiCCB: 生成卡片失败: {traceback.format_exc()}")
            return None

    # --------------- 黑名单管理 ---------------
    def _load_blocklist(self) -> dict:
        """加载黑名单 (JSON: {group_id: [user_id, ...]})"""
        try:
            if self._blocklist_path.exists():
                data = json.loads(self._blocklist_path.read_text("utf-8"))
                if isinstance(data, dict):
                    return data
        except Exception as e:
            logger.error(f"KasumiCCB: 加载黑名单失败: {e}")
        return {}

    def _save_blocklist(self, blocklist: dict):
        """持久化保存黑名单"""
        try:
            self._blocklist_path.write_text(
                json.dumps(blocklist, ensure_ascii=False, indent=2), "utf-8"
            )
        except Exception as e:
            logger.error(f"KasumiCCB: 保存黑名单失败: {e}")

    def _is_blocked(self, group_id: str, user_id: str) -> bool:
        """检查用户是否在该群黑名单中"""
        blocklist = self._load_blocklist()
        return user_id in blocklist.get(group_id, [])

    def _extract_at_target(self, event: AstrMessageEvent) -> Optional[str]:
        """从消息链中提取第一个 @ 的用户 ID"""
        for comp in event.get_messages():
            if isinstance(comp, At):
                qq = getattr(comp, "qq", None)
                if qq:
                    return str(qq)
        return None

    # --------------- 命令 ---------------
    @filter.regex(r"^/block\s+.*")
    async def block_command(self, event: AstrMessageEvent):
        """拉黑用户，使其不再能被娶群友抽到（仅管理员可用）"""
        if not hasattr(event.message_obj, "group_id"):
            yield event.plain_result("此命令仅限群聊中使用。")
            return

        if not event.is_admin():
            yield event.plain_result("⛔ 仅管理员可使用此命令。")
            return

        target_id = self._extract_at_target(event)
        if not target_id:
            yield event.plain_result("⚠️ 请 @ 要拉黑的用户，例如：/block @用户")
            return

        group_id = str(event.message_obj.group_id)
        blocklist = self._load_blocklist()

        if group_id not in blocklist:
            blocklist[group_id] = []

        if target_id in blocklist[group_id]:
            yield event.plain_result(f"ℹ️ 用户 {target_id} 已在黑名单中。")
            return

        blocklist[group_id].append(target_id)
        self._save_blocklist(blocklist)

        logger.info(f"KasumiCCB: 管理员 {event.get_sender_id()} 在群 {group_id} 拉黑了 {target_id}")
        yield event.plain_result(f"✅ 已拉黑用户 {target_id}，该用户将不再被娶群友抽到。")

    @filter.regex(r"^/unblock\s+.*")
    async def unblock_command(self, event: AstrMessageEvent):
        """解除用户拉黑（仅管理员可用）"""
        if not hasattr(event.message_obj, "group_id"):
            yield event.plain_result("此命令仅限群聊中使用。")
            return

        if not event.is_admin():
            yield event.plain_result("⛔ 仅管理员可使用此命令。")
            return

        target_id = self._extract_at_target(event)
        if not target_id:
            yield event.plain_result("⚠️ 请 @ 要解除拉黑的用户，例如：/unblock @用户")
            return

        group_id = str(event.message_obj.group_id)
        blocklist = self._load_blocklist()

        blocked_users = blocklist.get(group_id, [])
        if target_id not in blocked_users:
            yield event.plain_result(f"ℹ️ 用户 {target_id} 不在黑名单中。")
            return

        blocked_users.remove(target_id)
        self._save_blocklist(blocklist)

        logger.info(f"KasumiCCB: 管理员 {event.get_sender_id()} 在群 {group_id} 解除拉黑了 {target_id}")
        yield event.plain_result(f"✅ 已解除用户 {target_id} 的拉黑。")

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

            # 加载黑名单，排除拉黑的用户
            blocked_ids = set(self._load_blocklist().get(group_id, []))
            valid = [m for m in members if str(m.user_id) not in {user_id, bot_id} | blocked_ids]
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
            logger.error(f"KasumiCCB: 异常: {traceback.format_exc()}")
            yield event.plain_result("❌ 发生异常，请联系开发者")
