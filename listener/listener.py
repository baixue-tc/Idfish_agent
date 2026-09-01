import time

import requests

from .product_matcher import ProductImageMatcher
from .ui import IdlefishUI


# FastAPI Agent 接口地址
AGENT_URL = "http://127.0.0.1:8001/chat"
AGENT_REPLY_FIELD = "reply"
AGENT_TIMEOUT = 30


class MessageListener:

    def __init__(
        self,
        stop_event,
        interval=5.0,
        debounce_time=0.3,
        product_images_dir=None,
        unknown_products_dir=None,
        product_match_threshold=10,
        use_preview_on_miss=False
    ):
        self.stop_event = stop_event

        # 聊天列表检查间隔
        self.interval = interval

        # 防抖时间
        self.debounce_time = debounce_time

        # UI 操作对象
        self.ui = IdlefishUI()

        # 产品图片库匹配器
        self.product_matcher = ProductImageMatcher(
            library_dir=product_images_dir,
            unknown_dir=unknown_products_dir,
            distance_threshold=product_match_threshold
        )

        # 启动时先加载一次图片库
        self.product_matcher.refresh()

        # 匹配不到时，是否点击图片打开预览再试一次。
        # 默认关闭，避免点开后截到整窗/整屏画面。
        self.use_preview_on_miss = use_preview_on_miss

        # 每个用户的商品名称缓存
        self.product_name_cache = {}

        # 每个用户最近一次处理过的买家消息，
        # 用来避免商家回复导致重复处理
        self.last_processed_buyer_message = {}

        # 已经输出过产品图片诊断的用户
        self.debugged_users = set()

        # 本次运行已经保存过未知截图的用户
        self.unknown_saved = set()

        # ======================================================
        # 上一次聊天列表状态
        #
        # {
        #     "Babybany": "三头还是四头",
        #     "冰雪蓝的aaa": "看一下详情页"
        # }
        # ======================================================

        self.last_conversations = {}

        # ======================================================
        # 待处理消息
        #
        # {
        #     "Babybany": {
        #         "conversation": Conversation,
        #         "time": 123456.78
        #     }
        # }
        # ======================================================

        self.pending_messages = {}

        # 当前处理用户
        self.current_username = None

    # ==========================================================
    # 初始化
    # ==========================================================

    def initialize(self, conversations):
        """
        第一次启动时记录聊天列表状态。
        不处理任何已有消息。
        """

        self.last_conversations = {
            (conversation.key or conversation.username):
                conversation.last_message

            for conversation in conversations
        }

        print(
            f"已记录 "
            f"{len(self.last_conversations)} 个聊天"
        )

    # ==========================================================
    # 检测聊天变化
    # ==========================================================

    def detect_changes(self, conversations):

        changed = []

        current_state = {}

        for conversation in conversations:

            username = conversation.username
            conversation_key = (
                conversation.key or conversation.username
            )

            current_state[conversation_key] = (
                conversation.last_message
            )

            # --------------------------------------------------
            # 新聊天
            # --------------------------------------------------

            if conversation_key not in self.last_conversations:

                print(
                    f"\n发现新聊天："
                    f"{username}"
                )

                changed.append(
                    conversation
                )

                continue

            # --------------------------------------------------
            # 消息发生变化
            # --------------------------------------------------

            old_message = (
                self.last_conversations[conversation_key]
            )

            new_message = (
                conversation.last_message
            )

            if old_message != new_message:

                changed.append(
                    conversation
                )

        # 更新状态
        self.last_conversations = current_state

        return changed

    # ==========================================================
    # 加入待处理队列
    # ==========================================================

    def add_pending_message(
        self,
        conversation
    ):

        username = conversation.username
        conversation_key = (
            conversation.key or conversation.username
        )

        self.pending_messages[conversation_key] = {
            "conversation": conversation,
            "time": time.monotonic()
        }

        print(
            f"[队列] 加入待处理："
            f"{username}"
        )

    # ==========================================================
    # 检查是否有消息需要处理
    # ==========================================================

    def get_ready_messages(self):

        if not self.pending_messages:

            return []

        now = time.monotonic()

        ready = []

        for conversation_key, data in (
            self.pending_messages.items()
        ):

            elapsed = (
                now - data["time"]
            )

            if elapsed >= self.debounce_time:

                ready.append(
                    conversation_key
                )

        return ready

    # ==========================================================
    # 处理待处理消息
    # ==========================================================

    def process_pending_messages(
        self,
        conversation_list
    ):

        ready_keys = (
            self.get_ready_messages()
        )

        if not ready_keys:

            return 0

        processed = 0

        for conversation_key in ready_keys:

            if self.stop_event.is_set():

                break

            data = (
                self.pending_messages.pop(
                    conversation_key,
                    None
                )
            )

            if data is None:

                continue

            conversation = (
                data["conversation"]
            )

            username = conversation.username

            print()
            print(
                "=" * 70
            )

            print(
                f"[处理] 开始处理："
                f"{username}"
            )

            self.handle_conversation(
                conversation_list,
                conversation
            )

            print(
                f"[处理] 处理完成："
                f"{username}"
            )

            processed += 1

        return processed

    # ==========================================================
    # 处理一个聊天
    # ==========================================================

    def handle_conversation(
        self,
        conversation_list,
        conversation
    ):

        username = conversation.username
        conversation_key = (
            conversation.key or conversation.username
        )

        self.current_username = username

        print(
            f"检测到聊天变化："
            f"{username}"
        )

        print(
            f"列表最后消息："
            f"{conversation.last_message}"
        )

        # ======================================================
        # 打开聊天
        # ======================================================

        success = self.ui.open_conversation(
            conversation_list,
            conversation
        )

        if not success:

            print(
                f"无法打开聊天："
                f"{username}"
            )

            return

        # ======================================================
        # 等待 UI 切换
        # ======================================================

        time.sleep(0.3)

        # ======================================================
        # 找聊天区域
        # ======================================================

        chat_main = (
            self.find_chat_main_from_page()
        )

        if chat_main is None:

            print(
                "没有找到 chat-main"
            )

            return

        # ======================================================
        # 获取最新买家消息
        #
        # 只处理买家发来的消息，
        # 如果最后一条是商家自己的回复，就向前找最近的买家消息。
        # ======================================================

        message = self.ui.get_latest_buyer_message(
            chat_main
        )

        if message is None:

            print(
                "没有读取到买家消息"
            )

            return

        print()
        print(
            "最新消息"
        )
        print(
            "-" * 70
        )

        print(
            "发送者：",
            message.sender
        )

        print(
            "内容：",
            message.content
        )

        print(
            "自己：",
            message.is_self
        )

        # ======================================================
        # 防止商家回复触发重复处理
        # ======================================================

        last_processed = (
            self.last_processed_buyer_message.get(
                conversation_key
            )
        )

        if last_processed == message.content:

            print(
                f">>> 这条买家消息已经处理过，跳过："
                f"{message.content}"
            )

            return

        # ======================================================
        # 自己发送的消息
        # ======================================================

        if message.is_self:

            print(
                ">>> 这是自己发送的消息，忽略"
            )

            return

        # ======================================================
        # 买家消息
        # ======================================================

        print()
        print(
            ">>> 检测到买家新消息！"
        )

        print(
            f">>> 用户："
            f"{message.sender}"
        )

        print(
            f">>> 内容："
            f"{message.content}"
        )

        # ======================================================
        # 获取产品名称
        # ======================================================

        product_name = self.get_product_name(
            chat_main,
            conversation
        )

        message.product_name = (
            product_name or ""
        )

        # ======================================================
        # 组装给后端的数据
        # ======================================================

        payload = {
            "user_id": message.sender,
            "message": message.content,
            "product_id": message.product_name
        }

        print()
        print(
            ">>> 后端数据："
        )

        print(
            payload
        )

        agent_reply = self.call_agent(
            payload
        )

        if agent_reply:

            print(
                f">>> Agent 回复：{agent_reply}"
            )

            self.ui.send_message(
                chat_main,
                agent_reply
            )

        # 记录已处理的买家消息
        self.last_processed_buyer_message[conversation_key] = (
            message.content
        )

        # ======================================================
        # 后面接 FastAPI
        # ======================================================

        # self.call_agent(payload)

    def call_agent(self, payload):
        """
        调用 FastAPI Agent，返回回复文本。

        返回 None 表示调用失败或无回复。
        """

        try:

            response = requests.post(
                AGENT_URL,
                json=payload,
                timeout=AGENT_TIMEOUT
            )

            response.raise_for_status()

            try:

                data = response.json()

            except Exception:

                text = response.text.strip()

                return text or None

            if isinstance(data, dict):

                for key in (
                    AGENT_REPLY_FIELD,
                    "message",
                    "content",
                    "text",
                    "reply_text"
                ):

                    value = data.get(key)

                    if (
                        isinstance(value, str)
                        and value.strip()
                    ):

                        return value.strip()

                return None

            if (
                isinstance(data, str)
                and data.strip()
            ):

                return data.strip()

            return None

        except Exception as exc:

            print(
                f"[Agent] 请求失败：{exc}"
            )

            return None

    # ==========================================================
    # 查找聊天区域
    # ==========================================================

    def find_chat_main_from_page(self):

        window = self.ui.find_window()

        if window is None:

            return None

        controls = self.ui.find_controls(
            window,
            "chat-main",
            max_depth=30,
            time_limit=3.0
        )

        if not controls:

            return None

        return controls[0]

    # ==========================================================
    # 获取产品名称
    # ==========================================================

    def get_product_name(self, chat_main, conversation):

        username = conversation.username
        conversation_key = (
            conversation.key or conversation.username
        )

        if conversation_key in self.product_name_cache:

            return self.product_name_cache[conversation_key]

        control = self.ui.find_product_image(
            chat_main
        )

        if control is None:

            print(
                "[产品图片] 未找到产品图片控件，"
                "请确认闲鱼页面已经打开聊天"
            )

            return None

        image = self.ui.capture_control_image(
            control
        )

        if image is None:

            print(
                "[产品图片] 截图失败"
            )

            return None

        print(
            f"[产品图片] 截图尺寸："
            f"{image.width} x {image.height}"
        )

        product_name, distance = (
            self.product_matcher.match(image)
        )

        if product_name:

            print(
                f"[产品图片] 匹配成功："
                f"{product_name} "
                f"(距离 {distance})"
            )

            self.product_name_cache[conversation_key] = (
                product_name
            )

            return product_name

        if conversation_key not in self.debugged_users:

            self.ui.debug_product_area(chat_main)

            self.debugged_users.add(conversation_key)

        if distance is None:

            # 图片库为空时，不尝试点击预览，
            # 直接保存截图供用户扩充图片库
            if conversation_key not in self.unknown_saved:

                self.product_matcher.save_unknown(
                    image,
                    username
                )

                self.unknown_saved.add(conversation_key)

            return None

        if (
            self.use_preview_on_miss
            and conversation_key not in self.unknown_saved
        ):

            product_name = (
                self._match_preview_image(
                    control,
                    conversation,
                    image
                )
            )

            if product_name:

                self.product_name_cache[conversation_key] = (
                    product_name
                )

                return product_name

        if conversation_key not in self.unknown_saved:

            self.product_matcher.save_unknown(
                image,
                username
            )

            self.unknown_saved.add(conversation_key)

        return None

    def _match_preview_image(
        self,
        control,
        conversation,
        thumbnail_image
    ):
        """点击产品图片，从预览图再匹配一次。"""

        username = conversation.username
        conversation_key = (
            conversation.key or conversation.username
        )

        if not self.ui.click_product_image(
            control
        ):

            return None

        time.sleep(0.6)

        try:

            window = self.ui.find_window()

            image_control = (
                self.ui.find_preview_image(window)
            )

            if image_control is None:

                return None

            image = self.ui.capture_control_image(
                image_control
            )

            if image is None:

                return None

            product_name, distance = (
                self.product_matcher.match(image)
            )

            if product_name:

                print(
                    f"[产品图片] 预览匹配成功："
                    f"{product_name} "
                    f"(距离 {distance})"
                )

                return product_name

            self.product_matcher.save_unknown(
                thumbnail_image,
                username,
                suffix="thumb"
            )

            self.unknown_saved.add(conversation_key)

            return None

        finally:

            self.ui.close_preview()

            time.sleep(0.2)

    # ==========================================================
    # 主循环
    # ==========================================================

    def run(self):

        print()
        print("=" * 70)
        print("闲鱼监听器启动")
        print("=" * 70)

        print(
            f"检查间隔："
            f"{self.interval} 秒"
        )

        print(
            f"消息防抖："
            f"{self.debounce_time} 秒"
        )

        print(
            f"Agent 接口：{AGENT_URL}"
        )

        print(
            "输入 q / quit / exit 可以退出"
        )

        print()

        # 等待 UIAutomation / 浏览器控件树就绪，
        # 否则刚启动时搜索会失败或卡住
        print(
            "等待界面就绪...",
            flush=True
        )

        time.sleep(2)

        initialized = False

        while not self.stop_event.is_set():

            try:

                # ==================================================
                # 1. 找聊天列表
                # ==================================================

                print(
                    "[监听] 查找聊天列表...",
                    flush=True
                )

                conversation_list = (
                    self.ui.find_conversation_list()
                )

                print(
                    "[监听] 聊天列表："
                    f"{'已找到' if conversation_list is not None else '未找到'}",
                    flush=True
                )

                if conversation_list is None:

                    print(
                        "没有找到聊天列表，"
                        "请确认闲鱼聊天窗口已经打开",
                        flush=True
                    )

                    self.stop_event.wait(
                        self.interval
                    )

                    continue

                # ==================================================
                # 2. 读取聊天列表
                # ==================================================

                print(
                    "[监听] 开始读取聊天列表...",
                    flush=True
                )

                start_time = (
                    time.perf_counter()
                )

                conversations = (
                    self.ui.read_conversations(
                        conversation_list
                    )
                )

                elapsed = (
                    time.perf_counter()
                    - start_time
                )

                print(
                    f"[监听] 读取聊天列表耗时："
                    f"{elapsed:.3f} 秒",
                    flush=True
                )

                if not conversations:

                    self.stop_event.wait(
                        self.interval
                    )

                    continue

                # ==================================================
                # 3. 第一次运行
                # ==================================================

                if not initialized:

                    self.initialize(
                        conversations
                    )

                    initialized = True

                # ==================================================
                # 4. 检测聊天变化
                # ==================================================

                else:

                    changed = (
                        self.detect_changes(
                            conversations
                        )
                    )

                    if changed:

                        print(
                            f"[监听] "
                            f"发现 {len(changed)} "
                            f"个聊天发生变化"
                        )

                    # ----------------------------------------------
                    # 加入待处理队列
                    # ----------------------------------------------

                    for conversation in changed:

                        if self.stop_event.is_set():

                            break

                        print()
                        print(
                            "=" * 70
                        )

                        print(
                            f"检测到聊天变化："
                            f"{conversation.username}"
                        )

                        print(
                            f"列表最后消息："
                            f"{conversation.last_message}"
                        )

                        self.add_pending_message(
                            conversation
                        )

                # ==================================================
                # 5. 处理已经完成防抖的消息
                # ==================================================

                processed = (
                    self.process_pending_messages(
                        conversation_list
                    )
                )

                # ==================================================
                # 6. 处理完消息后立刻重新监听，
                #    不再等待下一个检查间隔
                # ==================================================

                if processed > 0:

                    continue

                self.stop_event.wait(
                    self.interval
                )

            except Exception as e:

                print()
                print(
                    "监听发生异常：",
                    repr(e)
                )

                self.ui.clear_caches()

                self.stop_event.wait(
                    self.interval
                )

        print()
        print("=" * 70)
        print("监听器已停止")
        print("=" * 70)
