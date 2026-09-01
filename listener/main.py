import threading

from .listener import MessageListener


def wait_for_exit(stop_event):
    """
    等待用户输入退出命令。
    """

    while not stop_event.is_set():

        try:

            command = input(
                "\n输入 q 退出监听："
            ).strip().lower()

        except EOFError:

            stop_event.set()
            break

        if command in (
            "q",
            "quit",
            "exit"
        ):

            print(
                "\n正在停止监听..."
            )

            stop_event.set()

            break


def main():

    # ==========================================================
    # 停止事件
    # ==========================================================

    stop_event = threading.Event()

    # ==========================================================
    # 创建监听器
    # ==========================================================

    listener = MessageListener(
        stop_event=stop_event,
        interval=5.0
    )

    # ==========================================================
    # 只把“输入退出命令”放到线程
    #
    # 注意：
    # uiautomation 不放在线程里！
    # ==========================================================

    exit_thread = threading.Thread(
        target=wait_for_exit,
        args=(stop_event,),
        daemon=True
    )

    exit_thread.start()

    # ==========================================================
    # UIAutomation 必须在主线程运行
    # ==========================================================

    try:

        listener.run()

    except KeyboardInterrupt:

        print(
            "\n\n收到 Ctrl+C，"
            "正在停止监听..."
        )

        stop_event.set()

    finally:

        stop_event.set()

        print(
            "\n程序已经安全退出。"
        )


if __name__ == "__main__":
    main()
