import logging
import sys
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s  - %(filename)s:%(lineno)d - %(message)s"

def setup_logging():
    logging.basicConfig(level=logging.INFO,
                        format=LOG_FORMAT,
                        handlers = [logging.StreamHandler(sys.stdout),# 输出到控制台
                                    # logging.FileHandler("app.log"),# 如果需要存文件,可以开启
                            ],
                        force = True
                        )