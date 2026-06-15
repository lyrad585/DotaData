
from config_logging import LOGGING_CONFIG as conf_log
from config_sources import SOURCES_CONFIG as conf_src
from dotenv import find_dotenv, load_dotenv, set_key
import json
import logging
import mssql_python
import os
import requests
import sys
import time

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s.%(msecs)03d [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.FileHandler(conf_log['file']),
        logging.StreamHandler(sys.stdout)
    ]
)





def initialize_db():
    logging.info(f"Function: {sys._getframe().f_code.co_name}")

    try:
        load_dotenv()

        DB_SERVER = os.getenv("DB_SERVER")
        DB_DATABASE = os.getenv("DB_DATABASE")

        if not DB_SERVER or not DB_DATABASE:
            logging.critical("Missing DB configuration (DB_SERVER or DB_DATABASE), exiting.")
            sys.exit()

        CONN_STR = (
            f"Server={DB_SERVER};"
            f"Database={DB_DATABASE};"
            "Trusted_Connection=yes;"
            "Encrypt=yes;"
            "TrustServerCertificate=yes;"
        )

        logging.info("Opening connection to the database.")
        conn = mssql_python.connect(CONN_STR)
        return conn
    
    except Exception as e:
        logging.critical(f"{e}")
        logging.error("Traceback details:", exc_info=True) if conf_log['traceback'] else None
        sys.exit()





def main():
    logging.info(f"Function: {sys._getframe().f_code.co_name}")

    try:
        conn = initialize_db()

    except Exception as e:
        logging.critical(f"{e}")
        logging.error("Traceback details:", exc_info=True) if conf_log['traceback'] else None





if __name__ == "__main__":
    logging.info(f"Starting {__file__}.")
    main()
