from dataclasses import dataclass


@dataclass
class Message:
    """一条聊天消息"""

    sender: str
    content: str
    is_self: bool
    product_name: str = ""


@dataclass
class Conversation:
    """一个聊天会话"""

    username: str
    last_message: str
    time: str
    key: str = ""
