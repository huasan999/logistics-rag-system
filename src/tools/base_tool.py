"""
工具基类
定义统一的工具接口和规范
提供了统一的接口，用于工具的调用和管理。
"""
import json
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field
from enum import Enum


logger = logging.getLogger(__name__)


class ToolCategory(str, Enum):
    """工具分类枚举，用于标识不同类型的工具"""
    CALCULATOR = "calculator"      # 计算工具
    LOGISTICS = "logistics"        # 物流工具
    WEB = "web"                    # 网络工具
    UTILITY = "utility"            # 工具工具


class ToolParameter(BaseModel):
    """
    工具参数定义模型

    Attributes:
        name (str): 参数名称
        type (str): 参数类型（如 string、integer 等）
        description (str): 参数描述信息
        required (bool): 是否为必需参数，默认为 True
    """
    name: str = Field(..., description="参数名称")
    type: str = Field(..., description="参数类型")
    description: str = Field(..., description="参数描述")
    required: bool = Field(True, description="是否必需")


class ToolSchema(BaseModel):
    """
    工具模式定义模型，描述一个工具的基本信息与结构

    Attributes:
        name (str): 工具名称
        description (str): 工具的功能描述
        category (ToolCategory): 工具所属分类
        parameters (List[ToolParameter]): 工具所需的参数列表
        returns (Dict[str, Any]): 工具执行后的返回数据结构示例
    """
    name: str = Field(..., description="工具名称")
    description: str = Field(..., description="工具描述")
    category: ToolCategory = Field(..., description="工具分类")
    parameters: List[ToolParameter] = Field(default_factory=list, description="参数列表")
    returns: Dict[str, Any] = Field(default_factory=dict, description="返回类型")


class BaseTool(ABC):
    """
    抽象工具基类，所有具体工具需继承此类并实现其抽象方法。

    Attributes:
        schema (ToolSchema): 当前工具的模式定义对象
    """

    def __init__(self):
        """
        初始化工具实例，并加载对应的工具模式定义。
        """
        self.schema = self.get_schema()

    @abstractmethod
    def get_schema(self) -> ToolSchema:
        """
        获取当前工具的模式定义

        Returns:
            ToolSchema: 包含工具基本信息及参数定义的对象
        """
        pass

    @abstractmethod
    async def execute(self, **kwargs) -> Dict[str, Any]:
        """
        执行工具逻辑的核心方法，由子类实现具体的业务功能

        Args:
            **kwargs: 根据工具参数动态传入的键值对参数

        Returns:
            Dict[str, Any]: 执行结果以字典形式返回
        """
        pass

    def to_function_call_format(self) -> Dict[str, Any]:
        """
        将工具模式转换为标准函数调用格式，便于外部系统识别和使用

        Returns:
            Dict[str, Any]: 符合函数调用协议的数据结构
        """
        schema = self.get_schema()

        # 构建参数模式
        parameters = {
            "type": "object",
            "properties": {},
            "required": []
        }

        for param in schema.parameters:
            parameters["properties"][param.name] = {
                "type": param.type,
                "description": param.description
            }
            if param.required:
                parameters["required"].append(param.name)

        return {
            "type": "function",
            "function": {
                "name": schema.name,
                "description": schema.description,
                "parameters": parameters
            }
        }


class ToolError(Exception):
    """
    自定义工具异常类，用于处理工具执行过程中发生的错误

    Args:
        Exception (BaseException): Python 内置异常基类
    """
    pass
