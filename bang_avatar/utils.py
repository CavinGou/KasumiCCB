import io
from pathlib import Path

import aiohttp
from PIL import Image, ImageDraw, ImageFilter


def paste_img(imgbase: Image.Image, imgadd: Image.Image, position: tuple[int, int]) -> Image.Image:
    """将图片粘贴到指定位置（保留透明通道）"""
    alpha = imgadd.split()[3]
    imgbase.paste(imgadd, position, alpha)
    return imgbase


def resize_img(img: Image.Image, target_size: int) -> Image.Image:
    """缩放图片到指定尺寸（BICUBIC + 锐化）"""
    img = img.resize((target_size, target_size), Image.BICUBIC)
    img = img.filter(ImageFilter.SHARPEN)
    return img


def circle_corner(img: Image.Image, radii: int) -> Image.Image:
    """为图片添加圆角"""
    img = img.convert("RGBA")
    width, height = img.size
    radii = min(radii, min(width, height) // 2)

    circle = Image.new("L", (radii * 2, radii * 2), 0)
    draw = ImageDraw.Draw(circle)
    draw.ellipse((0, 0, radii * 2, radii * 2), fill=255)

    alpha = Image.new("L", img.size, 255)
    positions = [
        (0, 0),
        (width - radii, 0),
        (width - radii, height - radii),
        (0, height - radii),
    ]

    for i, (x, y) in enumerate(positions):
        quadrant = circle.crop(
            (
                0 if i in [0, 3] else radii,
                0 if i in [0, 1] else radii,
                radii if i in [0, 3] else radii * 2,
                radii if i in [0, 1] else radii * 2,
            )
        )
        alpha.paste(quadrant, (x, y))

    img.putalpha(alpha)
    return img


async def fetch_avatar(user_id: str) -> Image.Image:
    """获取QQ用户头像（640x640）

    Args:
        user_id: QQ号

    Returns:
        PIL Image对象
    """
    avatar_url = f"http://q.qlogo.cn/headimg_dl?dst_uin={user_id}&spec=640"

    async with aiohttp.ClientSession() as session:
        async with session.get(avatar_url, timeout=15) as response:
            response.raise_for_status()
            img_bytes = await response.read()
            return Image.open(io.BytesIO(img_bytes))


def image_to_bytes(img: Image.Image) -> bytes:
    """将PIL图片转换为PNG bytes"""
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return buffer.getvalue()


def svg_to_png(svg_path: str, output_path: str, width: int, height: int) -> None:
    """将SVG文件转换为PNG并保存

    需要安装 cairosvg 库: pip install cairosvg
    """
    try:
        import cairosvg

        png_data = cairosvg.svg2png(
            url=svg_path, output_width=width, output_height=height, dpi=300
        )
        with open(output_path, "wb") as f:
            f.write(png_data)
    except ImportError:
        raise ImportError("需要安装 cairosvg 库: pip install cairosvg")
