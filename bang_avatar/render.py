import io
import logging
from pathlib import Path

from PIL import Image

from .models import WifeData
from .utils import paste_img, resize_img, circle_corner, fetch_avatar

logger = logging.getLogger(__name__)


async def render_card(
    wife_data: WifeData,
    src_path: Path,
    avatar_bytes: bytes = None,
) -> bytes:
    """渲染一张 BanGDream 风格的头像卡片

    Args:
        wife_data: 卡片数据（包含随机生成的 band/star/attribute）
        src_path: 素材资源路径
        avatar_bytes: 头像图片的 bytes（如果为 None 则自动下载）

    Returns:
        PNG 图片的 bytes
    """
    # 获取头像
    if avatar_bytes:
        avatar = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")
    else:
        avatar = await fetch_avatar(wife_data.target_id)

    # 渲染卡片
    return _render(avatar, wife_data.star, wife_data.band, wife_data.attribute, src_path)


def _render(
    base: Image.Image,
    stars: int,
    band: int,
    attr: str,
    src_path: Path,
) -> bytes:
    """实际渲染卡片

    Args:
        base: 头像图片
        stars: 星级 (1-5)
        band: 乐队编号
        attr: 属性 (cool/pure/powerful/happy)
        src_path: 素材路径

    Returns:
        PNG 图片 bytes
    """
    # 圆角化头像
    base = circle_corner(base, 48)

    # 缩放到640x640
    if base.size != (640, 640):
        base = resize_img(base, 640)

    # 选择卡面背景
    card_pic_path = f"card-1-{attr}.png" if stars == 1 else f"card-{stars}.png"
    card_pic = Image.open(src_path / card_pic_path)
    base = paste_img(base, card_pic, (0, 0))

    # 乐队图标 (左上角)
    band_pic = Image.open(src_path / f"band_{band}.png")
    base = paste_img(base, band_pic, (7, 7))

    # 属性图标 (右上角)
    attr_pic = Image.open(src_path / f"{attr}.png")
    base = paste_img(base, attr_pic, (473, 11))

    # 星级图标 (左侧)
    star_pic = (
        Image.open(src_path / "star.png")
        if stars <= 2
        else Image.open(src_path / "star_trained.png")
    )
    for i in range(stars):
        y = 513 - i * 80
        base = paste_img(base, star_pic, (10, y))

    # 输出 bytes
    buffer = io.BytesIO()
    base.save(buffer, format="PNG")
    return buffer.getvalue()
