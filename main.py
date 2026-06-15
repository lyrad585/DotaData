
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





def initialize_sources():
    logging.info(f"Function: {sys._getframe().f_code.co_name}")

    try:
        load_dotenv()

        SOURCES_TO_SYNC = os.getenv("SOURCES_TO_SYNC")

        if not SOURCES_TO_SYNC:
            logging.critical("Missing SOURCES configuration, exiting.")
            sys.exit()

        sources = [src.strip() for src in SOURCES_TO_SYNC.split(",") if src.strip()]
        logging.info(f"SOURCES_TO_SYNC: {sources}")

        srcs = {}
        for src in sources:
            if src in conf_src:
                if conf_src[src]['sync']:
                    srcs[src] = conf_src[src]
                    logging.info(f"Loaded {src} config.")
                else:
                    logging.warning(f"Sync for {src} is {conf_src[src]['sync']}, skipping.")
            else:
                logging.warning(f"Source {src} not found in config_sources, skipping.")

        return srcs
    
    except Exception as e:
        logging.critical(f"{e}")
        logging.error("Traceback details:", exc_info=True) if conf_log['traceback'] else None
        sys.exit()





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





def initialize_account_ids(conn, srcs):
    logging.info(f"Function: {sys._getframe().f_code.co_name}")

    try:
        # Get new accounts and accounts to focus on from the .env file
        logging.info("Getting accounts to sync.")        
        ACCOUNT_IDS_NEW = os.getenv("ACCOUNT_IDS_NEW", "")
        ACCOUNT_IDS_FOCUS = os.getenv("ACCOUNT_IDS_FOCUS", "")
        logging.info(f"ACCOUNT_IDS_NEW: {ACCOUNT_IDS_NEW}")
        logging.info(f"ACCOUNT_IDS_FOCUS: {ACCOUNT_IDS_FOCUS}")

        # Get/list all accounts by source flagged in the database to ignore
        for src in srcs:
            srcs[src]['cat']['accounts']['ignore']['a_ids'] = db(conn, srcs[src]['cat']['accounts']['ignore']['select'])
            logging.info(f"{src} accounts to ignore: {srcs[src]['cat']['accounts']['ignore']['a_ids']}")

        # If there are accounts to focus on, sync those only.  Otherwise, get new and existing accounts to sync.
        # Unlike ignore, sync all accounts with all sources.
        all_a_ids = []
        if ACCOUNT_IDS_FOCUS:
            all_a_ids = [int(a_id.strip()) for a_id in ACCOUNT_IDS_FOCUS.split(",") if a_id.strip()]
        else:
            if ACCOUNT_IDS_NEW:
                for a_id in ACCOUNT_IDS_NEW.split(","):
                    if a_id not in all_a_ids:
                        all_a_ids.append(a_id)

            for src in srcs:
                srcs[src]['cat']['accounts']['a_ids'] = db(conn, srcs[src]['cat']['accounts']['select'])
                logging.info(f"{src} accounts to attempt to sync: {srcs[src]['cat']['accounts']['a_ids']}")
                for a_id in srcs[src]['cat']['accounts']['a_ids']:
                    if a_id not in all_a_ids:
                        all_a_ids.append(a_id)

        if len(all_a_ids) == 0:
            logging.warning(f"There aren't any accounts to check, exiting.")
            sys.exit()
        else:
            logging.info(f"The account list to check has been built.")

        return all_a_ids, srcs

    except Exception as e:
        logging.critical(f"{e}")
        logging.error("Traceback details:", exc_info=True) if conf_log['traceback'] else None
        sys.exit()





def db(conn, sql, params = []):
    logging.info(f"Function: {sys._getframe().f_code.co_name}") if "Account_Aliases" not in sql else None
    logging.info(f"SQL details: {sql}") if conf_log['sql_cmds'] else None
    logging.info(f"SQL parameter details: {params}") if conf_log['sql_params'] else None

    
    try:
        cursor = conn.cursor()
        cursor.execute(sql, params)
        if sql.startswith("SELECT"):
            rows = [row[0] for row in cursor.fetchall()]
        else:
            rows = []
            cursor.commit()

    except Exception as e:
        cursor.rollback()
        logging.critical(f"{e}")
        logging.error("Traceback details:", exc_info=True) if conf_log['traceback'] else None
        logging.error("SQL details:", exc_info=True) if conf_log['sql_cmds'] else None
        logging.error("SQL parameter details:", exc_info=True) if conf_log['sql_params'] else None

    finally:
        cursor.close()

    return rows





def sync_accounts(conn, all_a_ids, srcs):
    logging.info(f"Function: {sys._getframe().f_code.co_name}")

    try:
        for src in srcs:
            if "accounts" in srcs[src]['cat']:
                if srcs[src]['cat']['accounts']['sync']:
                    logging.info(f"Syncing {src} accounts.")
                else:
                    logging.warning(f"Account sync for {src} is {srcs[src]['cat']['accounts']['sync']}, skipping.")
                    continue
            else:
                logging.warning(f"Account sync for {src} has not been configured, skipping.")
                continue

            for src_url in srcs[src]['cat']['accounts']['urls']:
                logging.info(f"{src} base URL: {src_url}")

                # Unlike ignore, sync all accounts with all sources.  Only ignore from the source we're working with.
                for a_id in all_a_ids:
                    logging.info(f"{src} account: {a_id}")
                    if a_id in srcs[src]['cat']['accounts']['ignore']['a_ids']:
                        logging.warning(f"Ignoring...")
                        continue
                    
                    if 'graphql' in srcs[src]['cat']['accounts']:
                        headers = {
                            "Authorization": f"Bearer {srcs[src]['token']}",
                            "Content-Type": "application/json"
                        }
                        query = srcs[src]['cat']['accounts']['graphql'].replace("{a_id}", str(a_id))
                        response = requests.post(src_url, json={"query": query}, headers=headers, timeout=srcs[src]['timeout'])
                    else:
                        url = src_url.format(account_id=a_id)
                        response = requests.get(url, timeout=srcs[src]['timeout'])
                        
                    logging.info(f"Response: {response.status_code} - {response.reason}")
                    if response.status_code == 404:
                        logging.warning(f"Updating {src}.Accounts to ignore {a_id}.")
                        params = eval(srcs[src]['cat']['accounts']['ignore']['params'])
                        db(conn, srcs[src]['cat']['accounts']['ignore']['merge'], params + params)
                        continue 
                    response.raise_for_status()
                    data = response.json()  # Variable data is in config_sources.py "params"

                    # Account details
                    params = eval(srcs[src]['cat']['accounts']['ignore']['merge']['params'])
                    logging.info(f"Merging account into {src}.Accounts.")
                    db(conn, srcs[src]['cat']['accounts']['ignore']['merge']['sql'], params + params)

                    # Alias history
                    logging.info(f"Checking for new aliases.")
                    aliases = eval(srcs[src]['cat']['accounts']['aliases']['list'])
                    if aliases:
                        for alias in aliases:   # Variable alias is in config_sources.py "params"
                            params = eval(srcs[src]['cat']['accounts']['aliases']['params'])
                            db(conn, srcs[src]['cat']['accounts']['aliases']['sql'], params)

                    # Pause to help prevent 429 errors
                    logging.info(f"Sleeping for {srcs[src]['sleep']} seconds.") if conf_log['sleep'] else None
                    time.sleep(srcs[src]['sleep'])

    except Exception as e:
        logging.error(f"{e}")
        logging.error("Traceback details:", exc_info=True) if conf_log['traceback'] else None





def sync_account_matches(conn, all_a_ids, srcs):
    logging.info(f"Function: {sys._getframe().f_code.co_name}")

    try:
        for src in srcs:
            if "account_matches" in srcs[src]['cat']:
                if srcs[src]['cat']['account_matches']['sync']:
                    logging.info(f"Syncing {src} account matches.")
                else:
                    logging.warning(f"Account match sync for {src} is {srcs[src]['cat']['account_matches']['sync']}, skipping.")
                    continue
            else:
                logging.warning(f"Account match sync for {src} has not been configured, skipping.")
                continue

            for src_url in srcs[src]['cat']['account_matches']['urls']:
                logging.info(f"{src} base URL: {src_url}")

                for a_id in all_a_ids:    
                    logging.info(f"{src} matches account: {a_id}")
                    if a_id in srcs[src]['cat']['accounts']['ignore']['a_ids']:
                        logging.warning(f"Ignoring...")
                        continue
                    
                    if 'graphql' in srcs[src]['cat']['account_matches']:
                        headers = {
                            "Authorization": f"Bearer {srcs[src]['token']}",
                            "Content-Type": "application/json"
                        }
                        query = srcs[src]['cat']['account_matches']['graphql'].replace("{account_id}", str(a_id))
                        response = requests.post(src_url, json={"query": query}, headers=headers, timeout=srcs[src]['timeout'])
                        
                    else:
                        url = src_url.format(account_id=a_id)
                        response = requests.get(url, timeout=srcs[src]['timeout'])
                        
                    logging.info(f"Response: {response.status_code} - {response.reason}")

    except Exception as e:
        logging.error(f"{e}")
        logging.error("Traceback details:", exc_info=True) if conf_log['traceback'] else None





def sync_match(match_ids):
    logging.info(f"Function: {sys._getframe().f_code.co_name}")

# Stratz seems to have all matches a player has played vs OpenDota where they have a subset of past matches and 20 recent.
# Therefore, get Stratz matches first.
    try:
        pass

    except Exception as e:
        logging.error(f"{e}")
        logging.error("Traceback details:", exc_info=True) if conf_log['traceback'] else None

    




def sync_src_cats(conn, all_a_ids, src_name, src):
    logging.info(f"Function: {sys._getframe().f_code.co_name}")

    try:
        for cat in src['cat'].keys():
            cat_name = cat.replace('_',' ')
            if src['cat'][cat]['sync']:
                logging.info(f"Checking {src_name} {cat_name}.")
                urls = []
                if 'request' in src:
                    if src['request'] == "post":
                        urls = src['urls']
                    else:
                        urls = src['cat'][cat]['urls']
            else:
                logging.warning(f"Ignore flag for {src_name} {cat_name} is set to {src['sync']}, skipping..")
                continue

            for url in urls:
                logging.info(f"{src_name} {cat_name} base URL: {url}")

                for a_id in all_a_ids:
                    logging.info(f"Checking {src_name} for {cat_name}: {a_id}")

                    if a_id in src['cat']['accounts']['ignore']['a_ids']:
                        logging.warning(f"Ignoring...")
                        continue

                    # If working on matches, get the existing matches for the account being worked on to ignore later.
                    if src['cat'][cat]['existing']:
                        src['cat'][cat]['m_ids'] = []
                        src['cat'][cat]['m_ids'] = db(conn, src['cat'][cat]['existing'], a_id)
                        logging.info(f"{len(src['cat'][cat]['m_ids'])} {src} {cat_name} will be ignored for {a_id}.")
            
                    # Pause to help prevent 429 errors
                    logging.info(f"Sleeping for {src['sleep']} seconds.") if conf_log['sleep'] and src['sleep'] > 0 else None
                    time.sleep(src['sleep'])

                    if src['request'] == "post":
                        headers = {
                            "Authorization": f"Bearer {src['token']}",
                            "Content-Type": "application/json"
                        }
                        query = src['cat'][cat]['graphql'].replace("{a_id}", str(a_id))
                        response = requests.post(url, json={"query": query}, headers=headers, timeout=src['timeout'])

                    else:
                        url = url.replace("{a_id}", str(a_id))
                        response = requests.get(url, timeout=src['timeout'])

                    logging.info(f"Response: {response.status_code} - {response.reason}")

                    # What to do with a 400 bad request?
                    if response.status_code == 404 and cat == "accounts":
                        logging.warning(f"Updating {src_name} {cat_name} to ignore {a_id}.")
                        params = eval(src['cat'][cat]['ignore']['params'])
                        db(conn, src['cat'][cat]['ignore']['merge'], params + params)
                        continue 

                    response.raise_for_status()
                    data = response.json()  # Variable data is in config_sources.py "params"

                    if src['process_json'] and src['cat'][cat]['process_json']:
                        logging.info(f"Processing JSON.")
                        json_str = json.dumps(data, sort_keys=True, separators=(',', ':'))
                        if url.endswith("recentmatches"):
                            src['cat'][cat]['process_json_merge'] = src['cat'][cat]['process_json_merge'].replace("account_matches_json","account_matches_recent_json")
                        db(conn, src['cat'][cat]['process_json_merge'], (a_id, json_str))

                    # For accounts, go through 'accounts'['record']['merge'] and ['record']['aliases']
                    if src['cat'][cat]['record']['merge']:
                        logging.info(f"Merging account with the {src_name} {cat_name} table.")
                        params = eval(src['cat'][cat]['record']['params'])
                        db(conn, src['cat'][cat]['record']['merge'], params + params)
                        # Alias history
                        if src['cat'][cat]['record']['aliases']:
                            logging.info(f"Checking for new aliases.")
                            aliases = eval(src['cat'][cat]['record']['aliases']['list'])
                            if aliases:
                                for alias in aliases:   # Variable alias is in config_sources.py "params"
                                    params = eval(src['cat'][cat]['record']['aliases']['params'])
                                    db(conn, src['cat'][cat]['record']['aliases']['insert'], params)
                        continue

                    # For account matches, go through 'account_matches'['record']['details'], validate with 'account_matches'['m_ids']
                    # For matches, go through 'matches'['record']['details'] and 'matches'['record']['players'], validate with 'matches'['m_ids']
                    if src['cat'][cat]['record']:
                        logging.info(f"Checking {cat_name} with the {src_name} {cat_name} table.")
                        match_list = eval(src['cat'][cat]['list'])

                        if not match_list:
                            logging.info(f"No match details records returned from {src} for account: {a_id}")
                            continue

                        logging.info(f"Looking through {len(match_list):,} {src} matches.")
                        # Get the existing matches for the account being worked on to ignore later.
                        src['cat'][cat]['m_ids'] = []
                        if src['cat'][cat]['existing']:
                            src['cat'][cat]['m_ids'] = db(conn, src['cat'][cat]['existing'], a_id)
                            logging.info(f"{len(src['cat'][cat]['m_ids'])} {src} {cat_name} will be ignored for {a_id}.")

                        for m in match_list:
                            match_id = m.get(src['cat'][cat]['identifier'])
                            if not match_id or match_id in src['cat'][cat]['m_ids']:
#                                batch_skipped += 1
#                                total_skipped += 1
                                continue



                            params = eval(src['cat'][cat]['record']['details']['params'])
                            db(conn, src['cat'][cat]['details'], params + params)
                            # Player performance
                            if src['cat'][cat]['record']['players']:
                                continue
















    except Exception as e:
        logging.error(f"{e}")
        logging.error("Traceback details:", exc_info=True) if conf_log['traceback'] else None




def main():
    logging.info(f"Function: {sys._getframe().f_code.co_name}")

    try:
        srcs = initialize_sources()
        conn = initialize_db()
        all_a_ids, srcs = initialize_account_ids(conn, srcs)    # I pass srcs and return it with a_ids

        for src in srcs:
            sync_src_cats(conn, all_a_ids, src, srcs[src])

#        sync_accounts(conn, all_a_ids, srcs)
#        sync_account_matches(conn, all_a_ids, srcs)

    except Exception as e:
        logging.critical(f"{e}")
        logging.error("Traceback details:", exc_info=True) if conf_log['traceback'] else None





if __name__ == "__main__":
    logging.info(f"Starting {__file__}.")
    main()
    
