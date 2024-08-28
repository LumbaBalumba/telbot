from telegram import ReplyKeyboardMarkup
from telegram.ext import (
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    Application,
    filters,
)
import asyncio
import re
import inspect
from functools import wraps
import logging

logger = logging.getLogger(__name__)


def reply(message: str, state: str) -> int:
    return 0


class TelegramBot:
    def __init__(self, token: str):
        self.token = token
        self.state_count = 0
        self.state_graph = {}
        self.application = Application.builder().token(self.token).build()

    def run(self):
        _ = self.application.job_queue
        conv_handler = ConversationHandler(
            entry_points=[CommandHandler("start", self.state_graph['start']['action'])],
            states={state['id']: [MessageHandler(filters.TEXT & ~filters.COMMAND, state['action'])] for state in
                    self.state_graph.values()},
            fallbacks=[],
        )
        self.application.add_handler(conv_handler)
        self.application.run_polling()

    def state(self, keyboard: list[list[str]] | list[str] | None = None, shape: tuple[int, ...] = None):
        if keyboard is not None and shape is not None:
            result_keyboard = []
            index = 0

            for size in shape:
                result_keyboard.append(keyboard[index: index + size])
                index += size
            keyboard = result_keyboard

        def decorator(func):
            self.state_graph[func.__name__] = {}
            self.state_graph[func.__name__]['keyboard'] = ReplyKeyboardMarkup(keyboard,
                                                                              one_time_keyboard=True) if keyboard is not None else keyboard
            self.state_graph[func.__name__]['id'] = self.state_count
            self.state_count += 1
            source_code = inspect.getsource(func)

            pattern = r'^\s*@(\w+)\.state\((.*?)\)\s*\n'

            match = re.search(pattern, source_code, flags=re.MULTILINE)
            bot_name = match.group(1)
            source_code = re.sub(pattern, '', source_code, flags=re.MULTILINE)

            pattern = r'^(\s*)reply\((.*?)\)\s*$'

            def replacement_function(reply_string):
                indent = reply_string.group(1)
                params_str = reply_string.group(2)

                params = re.findall(r'\'[^\']*\'|"[^"]*"|[^,]+', params_str)
                param1 = params[0].strip()
                param2 = params[1].strip()
                replacement_code = f"""{indent}await update.message.reply_text({param1}, reply_markup={bot_name}.state_graph[{param2}]['keyboard'])
{indent}return {bot_name}.state_graph[{param2}]['id']"""
                return replacement_code

            modified_code = re.sub(pattern, replacement_function, source_code, flags=re.MULTILINE)
            logger.debug(f"Modified code:\n{modified_code}")

            exec_globals = func.__globals__.copy()
            exec(modified_code, exec_globals)
            modified_func = exec_globals[func.__name__]

            @wraps(func)
            async def wrapper(*args, **kwargs):
                if asyncio.iscoroutinefunction(modified_func):
                    return await modified_func(*args, **kwargs)
                else:
                    return modified_func(*args, **kwargs)

            self.state_graph[func.__name__]['action'] = wrapper

            return wrapper

        return decorator
