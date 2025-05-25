from enum import Enum

class ObjectClass(Enum):
    PAPER_BOX = "paper box"
    TRAFFIC_SIGN = "traffic sign"
    CONTAINER = "container"
    WOODEN_BUILDING = "wooden building"
    TREE = "tree"
    PLASTIC = "plastic"
    DISPOSABLE_CUP = "disposable cup"

name_to_enum = {
    "paper box": ObjectClass.PAPER_BOX,
    "traffic sign": ObjectClass.TRAFFIC_SIGN,
    "container": ObjectClass.CONTAINER,
    "wooden building": ObjectClass.WOODEN_BUILDING,
    "tree": ObjectClass.TREE,
    "plastic": ObjectClass.PLASTIC,
    "disposable cup": ObjectClass.DISPOSABLE_CUP
}