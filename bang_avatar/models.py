import random
from enum import IntEnum
from enum import StrEnum
from dataclasses import dataclass


class Band(IntEnum):
    """乐队枚举"""
    poppin_party = 1
    afterglow = 2
    hello_happy_world = 3
    pastel_palettes = 4
    roselia = 5
    raise_a_suilen = 18
    morfonica = 21
    mygo = 45


class Star(IntEnum):
    """星级枚举"""
    one = 1
    two = 2
    three = 3
    four = 4
    five = 5


class Attribute(StrEnum):
    """属性枚举"""
    cool = "cool"
    pure = "pure"
    powerful = "powerful"
    happy = "happy"


@dataclass
class WifeData:
    """卡片数据"""
    # 用户信息
    user_id: str
    target_id: str

    # 渲染数据
    band: int = None
    star: int = None
    attribute: str = None

    def generate(self):
        """生成随机卡片数据"""
        self.band = random.choice(list(Band))
        self.star = random.choice(list(Star))
        self.attribute = random.choice(list(Attribute))
        return self
