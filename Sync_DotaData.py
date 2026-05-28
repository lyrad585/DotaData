import os
import sys
import logging
import requests
import mssql_python
from datetime import datetime
from dotenv import load_dotenv

# 1. Initialize environment variables from your local .env file
load_dotenv()

# 2. Configure the logging layout (Outputs to console and updates 'opendota_sync.log')
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler("opendota_sync.log"),
        logging.StreamHandler(sys.stdout)
    ]
)

# 3. Pull database credentials out of the environment variables safely
DB_SERVER = os.getenv("DB_SERVER")
DB_DATABASE = os.getenv("DB_DATABASE")
ACCOUNT_IDS = os.getenv("ACCOUNT_IDS", "")

if not DB_SERVER or not DB_DATABASE:
    logging.critical("Missing DB configuration (DB_SERVER or DB_DATABASE) inside your .env file. Terminating.")
    sys.exit(1)

# 4. Assemble your standard Microsoft SQL Server connection string parameters
CONN_STR = (
    f"Server={DB_SERVER};"
    f"Database={DB_DATABASE};"
    "Trusted_Connection=yes;"
    "Encrypt=yes;"
    "TrustServerCertificate=yes;"
)

import logging
import requests
from datetime import datetime

def sync_opendota_player_profile(player_id, conn):
    """
    Fetches a single player profile from the correct OpenDota API path
    and upserts the data into OpenDota.Players.
    """
    # CORRECT ENDPOINT: Verified functional route
    api_url = f"https://api.opendota.com/api/players/{player_id}"
    logging.info(f"Extracting OpenDota player profile layer for ID: {player_id}")
    
    try:
        response = requests.get(api_url, timeout=10)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        logging.error(f"Failed to fetch profile for Player {player_id} via OpenDota API: {e}")
        return False

    # Isolate profile tracking keys safely
    profile = data.get('profile', {}) or {}
    account_id = profile.get('account_id')
    
    if not account_id:
        logging.warning(f"No account_id detected in the profile payload for player {player_id}. Skipping.")
        return False

    # Parse timestamps into native datetime objects for SQL Server
    last_log_raw = profile.get('last_login')
    last_login = None
    if last_log_raw:
        try:
            clean_ts = last_log_raw.replace('T', ' ').replace('Z', '')
            last_login = datetime.strptime(clean_ts, '%Y-%m-%d %H:%M:%S.%f')
        except Exception:
            last_login = None

    cursor = conn.cursor()
    try:
        # Targets the explicit OpenDota.Players schema path
        player_merge_sql = """
        MERGE OpenDota.Players AS target
        USING (SELECT ? AS account_id) AS source
        ON (target.account_id = source.account_id)
        WHEN MATCHED THEN
            UPDATE SET 
                tracked_until = ?, solo_competitive_rank = ?, competitive_rank = ?, 
                rank_tier = ?, leaderboard_rank = ?, personaname = ?, name = ?, 
                plus_status = ?, cheese = ?, steamid = ?, avatar = ?, avatarmedium = ?, 
                avatarfull = ?, profileurl = ?, last_login = ?, loccountrycode = ?, 
                is_contributor = ?, is_subscriber = ?, last_updated_at = GETDATE()
        WHEN NOT MATCHED THEN
            INSERT (account_id, tracked_until, solo_competitive_rank, competitive_rank, 
                    rank_tier, leaderboard_rank, personaname, name, plus_status, cheese, 
                    steamid, avatar, avatarmedium, avatarfull, profileurl, last_login, 
                    loccountrycode, is_contributor, is_subscriber)
            VALUES (source.account_id, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """
        
        params = (
            int(account_id),
            data.get('tracked_until'),
            data.get('solo_competitive_rank'),
            data.get('competitive_rank'),
            data.get('rank_tier'),
            data.get('leaderboard_rank'),
            profile.get('personaname'),
            profile.get('name'),
            1 if profile.get('plus') else 0,
            profile.get('cheese'),
            profile.get('steamid'),
            profile.get('avatar'),
            profile.get('avatarmedium'),
            profile.get('avatarfull'),
            profile.get('profileurl'),
            last_login,
            profile.get('loccountrycode'),
            1 if profile.get('is_contributor') else 0,
            1 if profile.get('is_subscriber') else 0
        )
        
        cursor.execute(player_merge_sql, params + params[1:])
        conn.commit()
        logging.info(f"Successfully processed profile records for player {account_id} into OpenDota.Players.")
        return True

    except Exception as e:
        logging.error(f"Database transaction failed for player row entry {account_id}: {e}")
        conn.rollback()
        return False
    finally:
        cursor.close()

def sync_opendota_player_aliases(player_id, conn):
    """
    Fetches a player's profile data from OpenDota, extracts their historic
    aliases list, and syncs them into the OpenDota.Player_Aliases table.
    """
    api_url = f"https://opendota.com{player_id}"
    logging.info(f"Extracting historic aliases from OpenDota for ID: {player_id}")
    
    try:
        response = requests.get(api_url, timeout=10)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        logging.error(f"Failed to fetch aliases for Player {player_id}: {e}")
        return False

    profile = data.get('profile', {}) or {}
    account_id = profile.get('account_id')
    
    if not account_id:
        logging.warning(f"No valid account_id found for alias tracking on player {player_id}. Skipping.")
        return False

    # Extract the nested raw aliases array list
    aliases_list = profile.get('aliases', [])

    cursor = conn.cursor()
    try:
        # Step A: Delete historic entries to maintain clean row continuity
        delete_sql = "DELETE FROM OpenDota.Player_Aliases WHERE account_id = ?;"
        cursor.execute(delete_sql, (int(account_id),))

        # Step B: Insert array entries if any are present
        if aliases_list:
            insert_sql = """
                INSERT INTO OpenDota.Player_Aliases (account_id, alias_name)
                VALUES (?, ?);
            """
            for alias in aliases_list:
                if alias:  # Protect against blank records or empty elements
                    cursor.execute(insert_sql, (int(account_id), str(alias)))
                    
        conn.commit()
        logging.info(f"Successfully synchronized {len(aliases_list)} aliases for account {account_id} into OpenDota.Player_Aliases.")
        return True

    except Exception as e:
        logging.error(f"Database transaction failed during alias write sequence for account {account_id}: {e}")
        conn.rollback()
        return False
    finally:
        cursor.close()

# 5. This is how the connection and cursor are physically created in your main execution loop:
def main():
    if not ACCOUNT_IDS:
        logging.warning("No tracking IDs identified inside ACCOUNT_IDS in your .env file.")
        return

    account_list = [aid.strip() for aid in ACCOUNT_IDS.split(",") if aid.strip()]
    
    conn = None
    try:
        logging.info("Opening master pipeline database connection to SQL Server.")
        
        # Open the connection using mssql_python
        conn = mssql_python.connect(CONN_STR)
        
        for player_id in account_list:
            # Sync parent metadata row first to maintain foreign key constraint rules
            profile_success = sync_opendota_player_profile(player_id, conn)
            
            # Sync child historical names only if the parent constraint is satisfied
            if profile_success:
                sync_opendota_player_aliases(player_id, conn)
                
    except Exception as e:
        logging.critical(f"Master pipeline control routine collapsed: {e}")
    finally:
        if conn:
            conn.close()
            logging.info("Pipeline database connection safely closed.")

if __name__ == "__main__":
    main()
