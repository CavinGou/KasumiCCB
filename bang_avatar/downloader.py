import asyncio
import os
from pathlib import Path
from typing import Dict, List

import aiofiles
import aiohttp


class AsyncDownloader:
    """异步资源下载器"""

    def __init__(self, cache_dir: Path, data_dir: Path, max_concurrent_tasks: int = 32):
        self.cache_dir: Path = cache_dir
        self.data_dir: Path = data_dir
        self.semaphore: asyncio.Semaphore = asyncio.Semaphore(max_concurrent_tasks)
        self.headers: Dict[str, str] = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/87.0.4280.67 Safari/537.36 Edg/87.0.664.47"
            ),
            "Referer": "https://bestdori.com/",
            "Host": "bestdori.com",
        }

    async def download_file(self, url: str, folder_name: str, file_name: str,
                          max_retries: int = 3, retry_delay: float = 1.0) -> None:
        """下载单个文件，带重试机制"""
        file_path: Path = self.data_dir / folder_name / file_name

        if not file_path.parent.exists():
            file_path.parent.mkdir(parents=True, exist_ok=True)

        async with self.semaphore:
            last_error = None
            for attempt in range(max_retries + 1):
                try:
                    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(60)) as session:
                        async with session.get(url, headers=self.headers) as response:
                            if response.status != 200:
                                return

                            data: bytes = await response.read()

                            # Bestdori 错误图片占位大小
                            if len(data) in (14559, 14084):
                                async with aiofiles.open(
                                    self.cache_dir / "bad_url.txt", "a"
                                ) as bad_file:
                                    await bad_file.write(url + "\n")
                            else:
                                async with aiofiles.open(file_path, "wb") as file:
                                    await file.write(data)
                                return
                except (aiohttp.ClientError, asyncio.TimeoutError, IOError) as e:
                    last_error = e
                    if attempt < max_retries:
                        await asyncio.sleep(retry_delay)
                    continue
                except Exception:
                    return

    async def download_cards(self, urls: List[str], folder_name: str, file_names: List[str]) -> None:
        """批量下载PNG卡片资源"""
        tasks = []
        for url, file_name in zip(urls, file_names):
            if not url.lower().endswith('.png'):
                continue
            tasks.append(self.download_file(url, folder_name, file_name))
        await asyncio.gather(*tasks)

    async def download_svgs(self, urls: List[str], folder_name: str, file_names: List[str]) -> None:
        """批量下载SVG资源"""
        tasks = []
        for url, file_name in zip(urls, file_names):
            if not url.lower().endswith('.svg'):
                continue
            tasks.append(self.download_file(url, folder_name, file_name))
        await asyncio.gather(*tasks)
