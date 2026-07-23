import logging
from pathlib import Path

from PIL import Image

from .downloader import AsyncDownloader
from .models import Band, Star, Attribute
from .utils import resize_img, svg_to_png

logger = logging.getLogger(__name__)

BAND_URL = "https://bestdori.com/res/icon/band_{}.svg"
CARD_URL = "https://bestdori.com/res/image/card-{}.png"
ATTRIBUTE_URL = "https://bestdori.com/res/icon/{}.svg"
ONE_STAR_CARD_URL = "https://bestdori.com/res/image/card-1-{}.png"
STAR_URL = "https://bestdori.com/res/icon/star.png"
STAR_TRAINED_URL = "https://bestdori.com/res/icon/star_trained.png"


async def ensure_resources(src_path: Path, cache_path: Path = None):
    """检查并下载卡片渲染所需的资源文件

    Args:
        src_path: 素材存放路径
        cache_path: 缓存路径（SVG临时存放），默认为 src_path 同级的 cache 目录
    """
    if cache_path is None:
        cache_path = src_path.parent / "cache"

    logger.info("BanGDream卡片: 正在检查资源...")

    # 检查所有处理后的PNG资源是否已存在
    all_resources_exist = True

    # 检查band PNG资源 (170x170)
    for band in Band:
        if not (src_path / f"band_{band.value}.png").exists():
            all_resources_exist = False
            break

    # 检查attr PNG资源 (160x160)
    for attr in Attribute:
        if not (src_path / f"{attr.value}.png").exists():
            all_resources_exist = False
            break

    # 检查card PNG资源 (640x640)
    for star in Star:
        if star == Star.one:
            continue
        if not (src_path / f"card-{star.value}.png").exists():
            all_resources_exist = False
            break

    # 检查card-1 PNG资源 (640x640)
    for attr in Attribute:
        if not (src_path / f"card-1-{attr.value}.png").exists():
            all_resources_exist = False
            break

    # 检查star PNG资源
    if not (src_path / "star.png").exists() or not (src_path / "star_trained.png").exists():
        all_resources_exist = False

    if all_resources_exist:
        logger.info("BanGDream卡片: 所有资源已存在，跳过初始化")
        return

    logger.info("BanGDream卡片: 开始下载资源...")

    # 确保目录存在
    src_path.mkdir(parents=True, exist_ok=True)
    cache_path.mkdir(parents=True, exist_ok=True)

    # 初始化下载器
    svg_downloader = AsyncDownloader(cache_path, cache_path)
    png_downloader = AsyncDownloader(cache_path, src_path)

    # 准备下载列表
    band_resources = [
        (BAND_URL.format(band.value), f"band_{band.value}.svg")
        for band in Band
    ]

    card_resources = [
        (CARD_URL.format(star.value), f"card-{star.value}.png")
        for star in Star if star != Star.one
    ]

    attribute_resources = [
        (ATTRIBUTE_URL.format(attr.value), f"{attr.value}.svg")
        for attr in Attribute
    ]

    one_star_card_resources = [
        (ONE_STAR_CARD_URL.format(attr.value), f"card-1-{attr.value}.png")
        for attr in Attribute
    ]

    star_resources = [
        (STAR_URL, "star.png"),
        (STAR_TRAINED_URL, "star_trained.png")
    ]

    # 下载SVG资源到cache目录
    svg_urls = [url for url, _ in band_resources + attribute_resources]
    svg_names = [name for _, name in band_resources + attribute_resources]
    await svg_downloader.download_svgs(svg_urls, "", svg_names)

    # 下载PNG资源到src目录
    png_urls = [url for url, _ in card_resources + one_star_card_resources + star_resources]
    png_names = [name for _, name in card_resources + one_star_card_resources + star_resources]
    await png_downloader.download_cards(png_urls, "", png_names)

    # SVG转PNG预处理
    logger.info("BanGDream卡片: SVG转PNG预处理...")
    try:
        for band in Band:
            svg_path = cache_path / f"band_{band.value}.svg"
            png_path = src_path / f"band_{band.value}.png"
            if svg_path.exists() and not png_path.exists():
                svg_to_png(str(svg_path), str(png_path), 170, 170)

        for attr in Attribute:
            svg_path = cache_path / f"{attr.value}.svg"
            png_path = src_path / f"{attr.value}.png"
            if svg_path.exists() and not png_path.exists():
                svg_to_png(str(svg_path), str(png_path), 160, 160)

        logger.info("BanGDream卡片: SVG转PNG完成")
    except Exception as e:
        logger.error(f"BanGDream卡片: SVG转PNG失败: {e}")

    # PNG图片缩放预处理
    logger.info("BanGDream卡片: PNG缩放预处理...")
    try:
        for star in Star:
            if star == Star.one:
                continue
            png_path = src_path / f"card-{star.value}.png"
            if png_path.exists():
                img = Image.open(png_path)
                img = resize_img(img, 640)
                img.save(png_path)

        for attr in Attribute:
            png_path = src_path / f"card-1-{attr.value}.png"
            if png_path.exists():
                img = Image.open(png_path)
                img = resize_img(img, 640)
                img.save(png_path)

        for star_file in ["star.png", "star_trained.png"]:
            png_path = src_path / star_file
            if png_path.exists():
                img = Image.open(png_path)
                img = resize_img(img, 107)
                img.save(png_path)

        logger.info("BanGDream卡片: PNG缩放完成")
    except Exception as e:
        logger.error(f"BanGDream卡片: PNG缩放失败: {e}")

    logger.info("BanGDream卡片: 资源初始化完成")
