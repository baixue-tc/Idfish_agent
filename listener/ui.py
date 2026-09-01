import ctypes
import time
from ctypes import wintypes

import uiautomation as auto
from PIL import ImageGrab

from .message import Message, Conversation


class IdlefishUI:
    """闲鱼 UI 操作"""

    # 自己的闲鱼账号名称
    MY_NAME = "琪东设备"

    # 产品图片控件常见 class name
    PRODUCT_IMAGE_KEYWORDS = (
        "product-image",
        "product-img",
        "product-pic",
        "product-cover",
        "goods-image",
        "goods-img",
        "goods-pic",
        "goods-cover",
        "item-image",
        "item-img",
        "item-pic",
        "item-cover",
        "ant-image",
        "ant-image-img",
    )

    def __init__(self):
        # 缓存闲鱼窗口和聊天列表，避免每轮遍历整个桌面控件树
        self._window = None
        self._conversation_list = None

    # ==========================================================
    # 通用方法
    # ==========================================================

    @staticmethod
    def find_controls(
        control,
        keyword,
        max_depth=None,
        time_limit=None,
        _depth=0,
        _start=None
    ):
        """
        递归查找 class name 中包含 keyword 的控件。

        max_depth 和 time_limit 用于限制扫描范围，
        避免遍历整个浏览器控件树导致卡死。
        """

        if _start is None:

            _start = time.perf_counter()

        results = []

        if (
            max_depth is not None
            and _depth >= max_depth
        ):

            return results

        for child in control.GetChildren():

            if (
                time_limit is not None
                and time.perf_counter() - _start
                > time_limit
            ):

                break

            class_name = child.ClassName or ""

            if keyword in class_name:
                results.append(child)

            results.extend(
                IdlefishUI.find_controls(
                    child,
                    keyword,
                    max_depth=max_depth,
                    time_limit=time_limit,
                    _depth=_depth + 1,
                    _start=_start
                )
            )

        return results

    @staticmethod
    def find_controls_by_keywords(control, keywords):
        """
        递归查找 class name 中包含任意 keyword 的控件。

        一次遍历完成多关键词匹配，避免重复递归整棵树。
        """

        results = []

        for child in control.GetChildren():

            class_name = child.ClassName or ""

            if any(
                keyword in class_name
                for keyword in keywords
            ):

                results.append(child)

            results.extend(
                IdlefishUI.find_controls_by_keywords(
                    child,
                    keywords
                )
            )

        return results

    @staticmethod
    def find_controls_by_name_keywords(control, keywords):
        """
        递归查找 Name 中包含任意 keyword 的控件。
        有些按钮 class name 不含 send/发送，只能靠 Name 找到。
        """

        results = []

        for child in control.GetChildren():

            name = child.Name or ""

            if any(
                keyword in name
                for keyword in keywords
            ):

                results.append(child)

            results.extend(
                IdlefishUI.find_controls_by_name_keywords(
                    child,
                    keywords
                )
            )

        return results

    @staticmethod
    def find_text_controls(control):
        """
        递归查找所有 TextControl
        """

        results = []

        for child in control.GetChildren():

            if child.ControlTypeName == "TextControl":

                if child.Name:
                    results.append(child)

            results.extend(
                IdlefishUI.find_text_controls(
                    child
                )
            )

        return results

    # ==========================================================
    # 找聊天列表
    # ==========================================================

    def find_conversation_list(self):
        """
        优先使用缓存的聊天列表，
        找不到时直接从闲鱼窗口内查找。

        不再依赖鼠标位置取控件，
        避免 ControlFromCursor 在网页控件树上阻塞。
        """

        if self._conversation_list is not None:

            return self._conversation_list

        print(
            "[监听] 定位闲鱼窗口...",
            flush=True
        )

        window = self.find_window()

        if window is None:

            return None

        # 先用原生 class name 精确查找，速度最快
        print(
            "[监听] 按 class 查找聊天列表...",
            flush=True
        )

        try:

            exact_control = auto.Control(
                searchFromControl=window,
                searchDepth=12,
                searchInterval=0.05,
                ClassName="conversation-list"
            )

            if exact_control.Exists(0.3):

                self._conversation_list = exact_control

                return exact_control

        except Exception:

            pass

        controls = self.find_controls(
            window,
            "conversation-list",
            max_depth=30,
            time_limit=3.0
        )

        if controls:

            self._conversation_list = controls[0]

            return controls[0]

        return None

    @staticmethod
    def _find_hwnd_by_title(title):
        """按精确标题查找顶层窗口句柄。"""

        hwnd = ctypes.windll.user32.FindWindowW(
            None,
            title
        )

        return hwnd or None

    @staticmethod
    def _find_hwnd_by_subtitle(subtitle):
        """按标题包含关键字查找顶层窗口句柄。"""

        found = []

        WNDENUMPROC = ctypes.WINFUNCTYPE(
            wintypes.BOOL,
            wintypes.HWND,
            wintypes.LPARAM
        )

        def enum_proc(hwnd, lparam):

            length = (
                ctypes.windll.user32
                .GetWindowTextLengthW(hwnd)
            )

            if length <= 0:

                return True

            buffer = ctypes.create_unicode_buffer(
                length + 1
            )

            ctypes.windll.user32.GetWindowTextW(
                hwnd,
                buffer,
                length + 1
            )

            if subtitle in buffer.value:

                found.append(hwnd)

                return False

            return True

        ctypes.windll.user32.EnumWindows(
            WNDENUMPROC(enum_proc),
            0
        )

        if found:

            return found[0]

        return None

    # ==========================================================
    # 找当前聊天区域
    # ==========================================================

    def find_window(self):
        """
        查找闲鱼聊天窗口。

        先用 Win32 按标题精确查找，
        找不到再用标题包含“闲鱼”的窗口。
        拿到句柄后直接转成 UIAutomation 控件，
        避免 UIAutomation 自带窗口搜索在网页窗口上阻塞。
        """

        if self._window is not None:

            return self._window

        hwnd = self._find_hwnd_by_title(
            "聊天_闲鱼"
        )

        if not hwnd:

            hwnd = self._find_hwnd_by_subtitle(
                "闲鱼"
            )

        if not hwnd:

            return None

        window = auto.ControlFromHandle(hwnd)

        if window is None:

            return None

        self._window = window

        return window

    def clear_caches(self):
        """控件失效时清空缓存，下次重新定位。"""

        self._window = None
        self._conversation_list = None

        return None

    def find_chat_main(self):
        """
        从鼠标当前位置向上寻找当前聊天区域。

        鼠标放在闲鱼聊天消息区域即可。
        """

        control = auto.ControlFromCursor()

        while control:

            class_name = control.ClassName or ""

            if "chat-main" in class_name:

                return control

            control = control.GetParentControl()

        return None

    # ==========================================================
    # 产品图片
    # ==========================================================

    def find_product_image(self, chat_main):
        """
        在聊天区域中寻找产品图片控件。

        先按位置找：价格/运费/地址等商品信息左侧的图片。
        位置找不到时，再退回 class name 关键词匹配。
        """

        positional = self.find_product_image_by_position(
            chat_main
        )

        if positional is not None:

            return positional

        # class name 关键词兜底
        candidates = []

        for control in self.find_controls_by_keywords(
            chat_main,
            self.PRODUCT_IMAGE_KEYWORDS
        ):

            class_name = (
                control.ClassName or ""
            ).lower()

            # 跳过消息列表里的头像/图片，
            # 只取聊天头部产品卡片
            if (
                "message" in class_name
                or "conversation" in class_name
            ):

                continue

            if self._control_area(control) < 2000:

                continue

            candidates.append(control)

        if not candidates:

            return None

        candidates.sort(
            key=self._control_area,
            reverse=True
        )

        return candidates[0]

    def find_product_image_by_position(self, chat_main):
        """
        在价格/运费/地址等商品信息文字的左侧找产品图片。

        闲鱼产品图片通常位于聊天头部，
        用户名下方、价格运费地址的左边。
        """

        info_keywords = (
            "价格",
            "运费",
            "地址",
            "发货",
            "包邮",
            "库存",
            "宝贝",
            "商品",
        )

        info_rects = []

        for text in self.find_text_controls(chat_main):

            if not any(
                keyword in text.Name
                for keyword in info_keywords
            ):

                continue

            rect = text.BoundingRectangle

            if (
                rect.right > rect.left
                and rect.bottom > rect.top
            ):

                info_rects.append(rect)

        image_controls = (
            self._find_image_like_controls(chat_main)
        )

        candidates = []

        if info_rects:

            band_top = min(
                rect.top
                for rect in info_rects
            )

            band_bottom = max(
                rect.bottom
                for rect in info_rects
            )

            right_limit = min(
                rect.left
                for rect in info_rects
            )

            for control in image_controls:

                rect = control.BoundingRectangle

                center_y = (
                    rect.top + rect.bottom
                ) / 2

                if (
                    rect.left <= right_limit
                    and band_top - 40
                    <= center_y
                    <= band_bottom + 40
                    and self._control_area(control) >= 2000
                ):

                    candidates.append(control)

        if not candidates:

            # 找不到商品信息文字时，
            # 取聊天区域上半部分最大的图片
            chat_rect = chat_main.BoundingRectangle

            top_limit = (
                chat_rect.top
                + (
                    chat_rect.bottom
                    - chat_rect.top
                ) * 0.45
            )

            for control in image_controls:

                rect = control.BoundingRectangle

                if (
                    rect.bottom <= top_limit
                    and self._control_area(control) >= 2000
                ):

                    candidates.append(control)

        if not candidates:

            return None

        candidates.sort(
            key=self._control_area,
            reverse=True
        )

        return candidates[0]

    def debug_product_area(self, chat_main):
        """
        打印聊天区域里商品信息文字和图片控件的真实信息，
        用于定位产品图片控件。
        """

        info_keywords = (
            "价格",
            "运费",
            "地址",
            "发货",
            "包邮",
            "库存",
            "宝贝",
            "商品",
        )

        print(
            "[产品图片] 商品信息文字：",
            flush=True
        )

        for text in self.find_text_controls(chat_main):

            if not any(
                keyword in text.Name
                for keyword in info_keywords
            ):

                continue

            rect = text.BoundingRectangle

            print(
                f"  {text.Name!r} "
                f"rect=({rect.left}, {rect.top}, "
                f"{rect.right}, {rect.bottom})",
                flush=True
            )

        print(
            "[产品图片] 图片控件：",
            flush=True
        )

        for control in self._find_image_like_controls(
            chat_main
        ):

            rect = control.BoundingRectangle

            print(
                f"  class={control.ClassName!r} "
                f"type={control.ControlTypeName} "
                f"rect=({rect.left}, {rect.top}, "
                f"{rect.right}, {rect.bottom}) "
                f"size={rect.right - rect.left} x "
                f"{rect.bottom - rect.top}",
                flush=True
            )

    def _find_image_like_controls(
        self,
        control,
        _depth=0,
        _start=None
    ):
        """收集聊天区域里的图片类控件。"""

        if _start is None:

            _start = time.perf_counter()

        results = []

        if (
            _depth >= 20
            or time.perf_counter() - _start > 1.0
        ):

            return results

        keywords = (
            "img",
            "image",
            "picture",
            "pic",
            "cover",
        )

        for child in control.GetChildren():

            class_name = (
                child.ClassName or ""
            ).lower()

            control_type = (
                child.ControlTypeName or ""
            )

            is_image = (
                control_type == "ImageControl"
                or any(
                    keyword in class_name
                    for keyword in keywords
                )
            )

            if is_image:

                rect = child.BoundingRectangle

                if (
                    rect.right > rect.left
                    and rect.bottom > rect.top
                ):

                    results.append(child)

            results.extend(
                self._find_image_like_controls(
                    child,
                    _depth + 1,
                    _start
                )
            )

        return results

    @staticmethod
    def _conversation_key(item, values=None):
        """
        生成一个会话控件的稳定标识。

        优先使用 UIAutomation RuntimeId，
        同一个会话在页面重新渲染前保持不变；
        拿不到时退回 AutomationId / 文本内容。
        """

        try:

            runtime_id = item.GetRuntimeId()

            if runtime_id:

                return "|".join(
                    str(part)
                    for part in runtime_id
                )

        except Exception:

            pass

        try:

            automation_id = item.AutomationId

            if automation_id:

                return f"aid:{automation_id}"

        except Exception:

            pass

        if values:

            return "text:" + "|".join(values)

        return ""

    @staticmethod
    def _control_area(control):
        """控件在屏幕上的面积，用来过滤头像等小图。"""

        rect = control.BoundingRectangle

        width = max(0, rect.right - rect.left)
        height = max(0, rect.bottom - rect.top)

        return width * height

    def capture_control_image(self, control):
        """
        截取控件当前在屏幕上的画面。

        直接用控件坐标抓屏，不需要保存临时文件。
        """

        rect = control.BoundingRectangle

        if (
            rect.right <= rect.left
            or rect.bottom <= rect.top
        ):

            return None

        return ImageGrab.grab(
            bbox=(
                int(rect.left),
                int(rect.top),
                int(rect.right),
                int(rect.bottom)
            )
        )

    def click_product_image(self, control):
        """点击产品图片，打开预览。"""

        try:

            control.Click()

            return True

        except Exception as exc:

            print(
                f"点击产品图片失败：{exc}"
            )

            return False

    def find_preview_image(self, window):
        """
        产品图片点开后，在弹层中寻找更大的图片。

        同样按常见 class name 关键词匹配。
        """

        if window is None:

            return None

        keywords = (
            "preview",
            "image-viewer",
            "img-viewer",
            "zoom",
            "modal",
            "dialog",
        )

        candidates = []

        for control in self.find_controls_by_keywords(
            window,
            keywords
        ):

            class_name = (
                control.ClassName or ""
            ).lower()

            if (
                control.ControlTypeName != "ImageControl"
                and "image" not in class_name
                and "img" not in class_name
            ):

                continue

            rect = control.BoundingRectangle

            if (
                rect.right <= rect.left
                or rect.bottom <= rect.top
            ):

                continue

            candidates.append(control)

        if not candidates:

            return None

        candidates.sort(
            key=lambda control: (
                control.BoundingRectangle.right
                - control.BoundingRectangle.left
            )
            * (
                control.BoundingRectangle.bottom
                - control.BoundingRectangle.top
            ),
            reverse=True
        )

        return candidates[0]

    def close_preview(self):
        """关闭可能打开的产品图片预览。"""

        try:

            auto.SendKeys("{ESC}")

        except Exception:

            pass

    # ==========================================================
    # 发送消息
    # ==========================================================

    def find_message_input(self, chat_main):
        """在聊天区域里寻找消息输入框。"""

        for root in (
            chat_main,
            self.find_window()
        ):

            if root is None:

                continue

            for control in self.find_controls_by_keywords(
                root,
                (
                    "textarea",
                    "chat-input",
                    "message-input",
                    "ant-input",
                )
            ):

                if self._is_editable(control):

                    return control

            for control in self.find_controls_by_keywords(
                root,
                ("input",)
            ):

                if self._is_editable(control):

                    return control

        return None

    @staticmethod
    def _is_editable(control):
        """判断控件是否像可输入的文本框。"""

        control_type = (
            control.ControlTypeName or ""
        )

        if control_type not in (
            "EditControl",
            "DocumentControl",
            "PaneControl",
            "CustomControl",
        ):

            return False

        rect = control.BoundingRectangle

        return (
            rect.right > rect.left
            and rect.bottom > rect.top
        )

    def find_send_button(self, chat_main):
        """寻找发送按钮：优先聊天区，再按离右下角最近选择。"""

        candidates = []

        seen = set()

        def add_candidate(control):

            try:

                runtime_id = control.GetRuntimeId()

                control_id = (
                    str(runtime_id)
                    if runtime_id
                    else str(id(control))
                )

            except Exception:

                control_id = str(id(control))

            if control_id in seen:

                return

            seen.add(control_id)

            rect = control.BoundingRectangle

            if (
                rect.right > rect.left
                and rect.bottom > rect.top
            ):

                candidates.append(control)

        def collect(root):

            if root is None:

                return

            for control in self.find_controls_by_keywords(
                root,
                (
                    "send",
                    "submit",
                    "发送",
                )
            ):

                add_candidate(control)

            for control in self.find_controls_by_name_keywords(
                root,
                (
                    "发送",
                    "send",
                    "submit",
                )
            ):

                add_candidate(control)

        collect(chat_main)

        if not candidates:

            collect(self.find_window())

        if not candidates:

            return None

        if chat_main is not None:

            chat_rect = chat_main.BoundingRectangle

            def bottom_right_score(control):

                rect = control.BoundingRectangle

                center_x = (
                    rect.left + rect.right
                ) / 2

                center_y = (
                    rect.top + rect.bottom
                ) / 2

                return (
                    abs(center_x - chat_rect.right)
                    + abs(center_y - chat_rect.bottom)
                )

            candidates.sort(
                key=bottom_right_score
            )

        else:

            candidates.sort(
                key=self._control_area
            )

        return candidates[0]

    @staticmethod
    def _set_clipboard_unicode(text):
        """用系统剪贴板 API 写入 Unicode，避免 emoji 被截断。"""

        text_utf16 = text.encode("utf-16-le")
        byte_len = len(text_utf16) + 2

        opened = False

        for _ in range(5):

            if ctypes.windll.user32.OpenClipboard(0):

                opened = True
                break

            time.sleep(0.1)

        if not opened:

            raise OSError("无法打开剪贴板")

        try:

            ctypes.windll.user32.EmptyClipboard()

            h_mem = ctypes.windll.kernel32.GlobalAlloc(
                0x0042,  # GMEM_MOVEABLE | GMEM_ZEROINIT
                byte_len
            )

            if not h_mem:

                raise OSError("分配剪贴板内存失败")

            try:

                dest = ctypes.windll.kernel32.GlobalLock(
                    ctypes.c_void_p(h_mem)
                )

                if not dest:

                    raise OSError("锁定剪贴板内存失败")

                try:

                    ctypes.memmove(
                        dest,
                        text_utf16,
                        len(text_utf16)
                    )

                finally:

                    ctypes.windll.kernel32.GlobalUnlock(
                        ctypes.c_void_p(h_mem)
                    )

                if not ctypes.windll.user32.SetClipboardData(
                    ctypes.c_uint(13),  # CF_UNICODETEXT
                    ctypes.c_void_p(h_mem)
                ):

                    raise OSError("设置剪贴板数据失败")

                h_mem = None

            finally:

                if h_mem:

                    ctypes.windll.kernel32.GlobalFree(
                        ctypes.c_void_p(h_mem)
                    )

        finally:

            ctypes.windll.user32.CloseClipboard()

    def send_message(self, chat_main, text):
        """把 Agent 回复输入到消息栏并发送。"""

        input_control = self.find_message_input(
            chat_main
        )

        if input_control is None:

            print(
                "[发送] 未找到消息输入框"
            )

            return False

        try:

            input_control.Click()

            time.sleep(0.2)

            try:

                # 用剪贴板粘贴，保留中文和 emoji，
                # SendKeys 会把 emoji 转成乱码
                self._set_clipboard_unicode(text)
                input_control.SendKeys("{Ctrl}v")

            except Exception:

                try:

                    input_control.SetValue(text)

                except Exception:

                    input_control.SendKeys(text)

            time.sleep(0.3)

        except Exception as exc:

            print(
                f"[发送] 输入消息失败：{exc}"
            )

            return False

        # 闲鱼网页版回车即可发送，优先用回车发送
        try:

            input_control.SendKeys("{ENTER}")

            time.sleep(0.3)

            return True

        except Exception as exc:

            print(
                f"[发送] 按回车发送失败：{exc}"
            )

        # 回车失败后再找发送按钮补发
        send_button = self.find_send_button(
            chat_main
        )

        if send_button is not None:

            try:

                print(
                    "[发送] 找到发送按钮："
                    f"{send_button.Name} / "
                    f"{send_button.ClassName} / "
                    f"{send_button.ControlTypeName}"
                )

                try:

                    send_button.Invoke()

                except Exception:

                    send_button.Click()

                time.sleep(0.3)

                return True

            except Exception as exc:

                print(
                    f"[发送] 点击发送按钮失败：{exc}"
                )

        else:

            print(
                "[发送] 未找到发送按钮"
            )

        return False

    # ==========================================================
    # 读取聊天列表
    # ==========================================================

    def read_conversations(self, conversation_list):
        """
        读取当前聊天列表。
        """

        items = self.get_conversation_items(
            conversation_list
        )

        conversations = []

        for item in items:

            texts = self.find_text_controls(item)

            if not texts:
                continue

            values = [
                text.Name
                for text in texts
                if text.Name
            ]

            # 通知消息跳过
            if "通知消息" in values:
                continue

            # 普通聊天：
            #
            # 用户名
            # 最后一条消息
            # 时间
            #
            if len(values) < 3:
                continue

            username = values[0]
            last_message = values[1]
            time_text = values[2]

            conversations.append(
                Conversation(
                    username=username,
                    last_message=last_message,
                    time=time_text,
                    key=self._conversation_key(
                        item,
                        values
                    )
                )
            )

        return conversations
    # ==========================================================
    # 找指定用户
    # ==========================================================

    def find_conversation(
        self,
        conversation_list,
        username=None,
        key=None
    ):
        """
        在当前聊天列表中寻找指定会话。

        优先按会话 key 匹配，
        找不到再退回按用户名匹配。
        """

        items = self.find_controls(
            conversation_list,
            "conversation-item"
        )

        if key:

            for item in items:

                texts = self.find_text_controls(item)

                values = [
                    text.Name
                    for text in texts
                    if text.Name
                ]

                item_key = self._conversation_key(
                    item,
                    values
                )

                if item_key == key:

                    return item

        if username:

            for item in items:

                texts = self.find_text_controls(item)

                values = [
                    text.Name
                    for text in texts
                    if text.Name
                ]

                if username in values:

                    return item

        return None

    # ==========================================================
    # 打开指定聊天
    # ==========================================================

    def open_conversation(
        self,
        conversation_list,
        conversation
    ):
        """
        点击指定会话。
        """

        item = self.find_conversation(
            conversation_list,
            username=conversation.username,
            key=conversation.key
        )

        if item is None:

            print(
                f"没有找到聊天：{conversation.username}"
            )

            return False

        try:

            item.Click()

            return True

        except Exception as e:

            print(
                f"打开聊天失败：{e}"
            )

            return False

    # ==========================================================
    # 读取当前聊天消息
    # ==========================================================

    def read_messages(self, chat_main):
        """
        读取当前聊天中的所有消息。
        """

        items = self.find_controls(
            chat_main,
            "ant-list-item"
        )

        messages = []

        for item in items:

            # 找消息中的 TextControl
            texts = self.find_text_controls(item)

            values = [
                text.Name
                for text in texts
                if text.Name
            ]

            if len(values) < 2:
                continue

            sender = values[0]
            content = values[1]

            # --------------------------------------------------
            # 判断消息方向
            # --------------------------------------------------

            message_controls = []

            def find_message_text(control):

                for child in control.GetChildren():

                    class_name = child.ClassName or ""

                    if "message-text-" in class_name:

                        message_controls.append(
                            child
                        )

                    find_message_text(child)

            find_message_text(item)

            is_self = False

            for control in message_controls:

                class_name = control.ClassName or ""

                if "message-text-right" in class_name:

                    is_self = True
                    break

                if "message-text-left" in class_name:

                    is_self = False
                    break

            # class name 识别不到时，用账号名兜底，
            # 避免把商家自己的回复当成买家消息
            if sender == self.MY_NAME:
                is_self = True

            messages.append(
                Message(
                    sender=sender,
                    content=content,
                    is_self=is_self
                )
            )

        return messages

    # ==========================================================
    # 获取当前聊天最新消息
    # ==========================================================

    def get_latest_message(self, chat_main):
        """
        获取当前聊天最后一条消息。
        """

        messages = self.read_messages(
            chat_main
        )

        if not messages:

            return None

        return messages[-1]

    def get_latest_buyer_message(self, chat_main):
        """
        获取当前聊天中最新的一条买家消息。

        如果最后一条是商家自己的回复，
        会继续向前找最近一条买家消息。
        """

        messages = self.read_messages(
            chat_main
        )

        for message in reversed(messages):

            if not message.is_self:

                return message

        return None

    def get_conversation_items(self, conversation_list):
        """
        只在 conversation-list 内递归寻找
        conversation-item。
        """

        items = []

        def search(control):

            for child in control.GetChildren():

                class_name = child.ClassName or ""

                # 找到聊天项
                if "conversation-item" in class_name:
                    items.append(child)

                    # 已经找到 conversation-item
                    # 不需要继续往里面找
                    continue

                # 没找到，继续向下寻找
                search(child)

        search(conversation_list)

        return items
