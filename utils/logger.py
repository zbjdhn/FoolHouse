import sys
import os
from loguru import logger

def setup_logger():
    """
    配置 loguru 日志格式。
    在 Vercel 环境下，日志将直接输出到 stdout，以便 Vercel Logs 捕获。
    """
    # 移除默认配置
    logger.remove()
    
    # 添加自定义配置
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level="INFO",
        colorize=True
    )
    
    # 如果在本地运行，可以将日志同时写入文件（Vercel 环境不建议写本地文件）
    if not os.environ.get("VERCEL"):
        logger.add(
            "logs/app.log",
            rotation="10 MB",
            retention="1 week",
            level="DEBUG",
            encoding="utf-8"
        )
    
    return logger

# 全局 logger 实例
setup_logger()
