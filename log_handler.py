
import logging
import os
import sys



logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s.%(msecs)03d [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.FileHandler(os.getenv("LOG_FILE")),
        logging.StreamHandler(sys.stdout)
    ]
)

LOG_TRACEBACK = True if os.getenv("LOG_TRACEBACK").lower() == "true" else False
LOG_LOCALS = True if os.getenv("LOG_LOCALS").lower() == "true" else False
LOG_GLOBALS = True if os.getenv("LOG_GLOBALS").lower() == "true" else False

global_head_foot = """
    ***************************
    ***** BEGIN globals() *****
    ***************************
    <text>
    ***************************
    *****  END globals()  *****
    ***************************
"""
local_head_foot = global_head_foot.replace("globals", " locals")



def info(msg):
    logging.info(msg)
    if LOG_LOCALS:
        local_vars = local_head_foot.replace("<text>", str(locals()))
        logging.info(local_vars)
    if LOG_GLOBALS:
        global_vars = global_head_foot.replace("<text>", str(globals()))
        logging.info(global_vars)

def warning(msg):
    logging.warning(msg)
    if LOG_LOCALS:
        local_vars = local_head_foot.replace("<text>", str(locals()))
        logging.info(local_vars)
    if LOG_GLOBALS:
        global_vars = global_head_foot.replace("<text>", str(globals()))
        logging.info(global_vars)

def error(msg):
    logging.error(msg)
    if LOG_LOCALS:
        local_vars = local_head_foot.replace("<text>", str(locals()))
        logging.info(local_vars)
    if LOG_GLOBALS:
        global_vars = global_head_foot.replace("<text>", str(globals()))
        logging.info(global_vars)

def critical(msg):
    logging.critical(msg)
    if LOG_LOCALS:
        local_vars = local_head_foot.replace("<text>", str(locals()))
        logging.info(local_vars)
    if LOG_GLOBALS:
        global_vars = global_head_foot.replace("<text>", str(globals()))
        logging.info(global_vars)


