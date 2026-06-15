
import logging
import mssql_python
import os
import sys





class dotadata_logger:
    def __init__(self):

        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s.%(msecs)03d [%(levelname)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S',
            handlers=[
                logging.FileHandler(os.getenv("LOG_FILE")),
                logging.StreamHandler(sys.stdout)
            ]
        )

        self.LOG_TRACEBACK = True if os.getenv("LOG_TRACEBACK").lower() == "true" else False
        self.LOG_LOCALS = True if os.getenv("LOG_LOCALS").lower() == "true" else False
        self.LOG_GLOBALS = True if os.getenv("LOG_GLOBALS").lower() == "true" else False
        self.global_head_foot = """
            ***************************
            ***** BEGIN globals() *****
            ***************************
            <text>
            ***************************
            *****  END globals()  *****
            ***************************
        """
        self.local_head_foot = self.global_head_foot.replace("globals", " locals")

    def info(self, msg):
        logging.info(msg)
        if self.LOG_LOCALS:
            local_vars = self.local_head_foot.replace("<text>", str(locals()))
            logging.info(local_vars)
        if self.LOG_GLOBALS:
            global_vars = self.global_head_foot.replace("<text>", str(globals()))
            logging.info(global_vars)

    def warning(self, msg):
        logging.warning(msg)
        if self.LOG_LOCALS:
            local_vars = self.local_head_foot.replace("<text>", str(locals()))
            logging.info(local_vars)
        if self.LOG_GLOBALS:
            global_vars = self.global_head_foot.replace("<text>", str(globals()))
            logging.info(global_vars)

    def error(self, msg):
        logging.error(msg)
        if self.LOG_LOCALS:
            local_vars = self.local_head_foot.replace("<text>", str(locals()))
            logging.info(local_vars)
        if self.LOG_GLOBALS:
            global_vars = self.global_head_foot.replace("<text>", str(globals()))
            logging.info(global_vars)

    def critical(self, msg):
        logging.critical(msg)
        if self.LOG_LOCALS:
            local_vars = self.local_head_foot.replace("<text>", str(locals()))
            logging.info(local_vars)
        if self.LOG_GLOBALS:
            global_vars = self.global_head_foot.replace("<text>", str(globals()))
            logging.info(global_vars)





logger = dotadata_logger()

DB_SERVER = os.getenv("DB_SERVER")
DB_DATABASE = os.getenv("DB_DATABASE")

if not DB_SERVER or not DB_DATABASE:
    logger.critical("Missing DB configuration (DB_SERVER or DB_DATABASE). Terminating.")
    sys.exit(1)

CONN_STR = (
    f"Server={DB_SERVER};"
    f"Database={DB_DATABASE};"
    "Trusted_Connection=yes;"
    "Encrypt=yes;"
    "TrustServerCertificate=yes;"
)

logger.info(f"Opening database connection to SQL Server.")
conn = mssql_python.connect(CONN_STR)





class account_ids():

    NEW_ACCOUNT_IDS = os.getenv("NEW_ACCOUNT_IDS", "")
    FOCUS_ACCOUNT_IDS = os.getenv("FOCUS_ACCOUNT_IDS", "")
    logger.info(f"NEW_ACCOUNT_IDS: {NEW_ACCOUNT_IDS}")
    logger.info(f"FOCUS_ACCOUNT_IDS: {FOCUS_ACCOUNT_IDS}")

    opendota_ignore_ids = []
    sql = """
        SELECT a.account_id
        FROM OpenDota.Accounts a
        WHERE a.ignore = 1
    """
    cursor = conn.cursor()
    cursor.execute(sql)
    opendota_ignore_ids = [row[0] for row in cursor.fetchall()]
    opendota_ignore_ids = [1,2,3,4,5]
    logger.info(f"OpenDota accounts to ignore: {opendota_ignore_ids}")

    stratz_ignore_ids = []
    sql = """
        SELECT a.steam_account_id
        FROM Stratz.Accounts a
        WHERE a.ignore = 1
    """
    cursor = conn.cursor()
    cursor.execute(sql)
    stratz_ignore_ids = [row[0] for row in cursor.fetchall()]
    stratz_ignore_ids = [10,11,12,13]
    logger.info(f"Stratz accounts to ignore: {stratz_ignore_ids}")

    all_not_ignore_ids = []
    if FOCUS_ACCOUNT_IDS:
        all_not_ignore_ids = [int(a_id.strip()) for a_id in FOCUS_ACCOUNT_IDS.split(",") if a_id.strip()]
    else:
        sql = """
            SELECT a.account_id
            FROM OpenDota.Accounts a
            WHERE a.ignore = 0
            UNION
            SELECT a.steam_account_id
            FROM Stratz.Accounts a
            WHERE a.ignore = 0
        """
        cursor = conn.cursor()
        cursor.execute(sql)
        all_not_ignore_ids = [row[0] for row in cursor.fetchall()]
        if NEW_ACCOUNT_IDS:
            for a_id in NEW_ACCOUNT_IDS.split(","):
                all_not_ignore_ids.append(int(a_id))

    all_ignore_ids = set().union(opendota_ignore_ids, stratz_ignore_ids)
    process_ids = [id for id in all_not_ignore_ids if id not in all_ignore_ids]
    print(all_ignore_ids)
















def opendota():
    logger.info(f"Function: {sys._getframe().f_code.co_name}")
    def opendota_sync_account():
        logger.info(f"Function: {sys._getframe().f_code.co_name}")
        pass
    def opendota_get_account_matches():
        logger.info(f"Function: {sys._getframe().f_code.co_name}")
        pass
    def opendota_get_match_details():
        logger.info(f"Function: {sys._getframe().f_code.co_name}")
        pass
    return
    
def stratz():
    logger.info(f"Function: {sys._getframe().f_code.co_name}")
    def stratz_sync_account():
        logger.info(f"Function: {sys._getframe().f_code.co_name}")
        pass
    def stratz_get_match_details():
        logger.info(f"Function: {sys._getframe().f_code.co_name}")
        pass
    return

def main():
    logger.info(f"Function: {sys._getframe().f_code.co_name}")
    logger.info(f"Getting accounts to sync.")
    a_ids = account_ids()
    logger.info(f"Accounts to process: {a_ids.all_not_ignore_ids}")
    return

if __name__ == "__main__":
    logger.info(f"Starting {__file__}.")
    main()
    
