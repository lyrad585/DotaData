import os
import sys
import logging
import requests
import mssql_python
import time
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
    and upserts the data into OpenDota.Players using a single try block.
    """
    # FIXED LOGIC: Strict adherence to your verified URL string
    api_url = f"https://api.opendota.com/api/players/{player_id}"
    logging.info(f"Extracting OpenDota player profile layer for ID: {player_id}")
    
    cursor = conn.cursor()
    try:
        response = requests.get(api_url, timeout=10)
        response.raise_for_status()
        data = response.json()

        profile = data.get('profile', {}) or {}
        account_id = profile.get('account_id')
        
        if not account_id:
            logging.warning(f"No account_id detected in the profile payload for player {player_id}. Skipping.")
            return False

        last_log_raw = profile.get('last_login')
        last_login = None
        if last_log_raw:
            clean_ts = last_log_raw.replace('T', ' ').replace('Z', '')
            last_login = datetime.strptime(clean_ts, '%Y-%m-%d %H:%M:%S.%f')

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
            int(account_id), data.get('tracked_until'), data.get('solo_competitive_rank'),
            data.get('competitive_rank'), data.get('rank_tier'), data.get('leaderboard_rank'),
            profile.get('personaname'), profile.get('name'), 1 if profile.get('plus') else 0,
            profile.get('cheese'), profile.get('steamid'), profile.get('avatar'),
            profile.get('avatarmedium'), profile.get('avatarfull'), profile.get('profileurl'),
            last_login, profile.get('loccountrycode'), 1 if profile.get('is_contributor') else 0,
            1 if profile.get('is_subscriber') else 0
        )
        
        cursor.execute(player_merge_sql, params + params[1:])
        conn.commit()
        logging.info(f"Successfully processed profile records for player {account_id} into OpenDota.Players.")
        return True

    except Exception as e:
        logging.error(f"Pipeline processing failed for player profile {player_id}: {e}")
        conn.rollback()
        return False
    finally:
        cursor.close()

def sync_opendota_player_aliases(player_id, conn):
    """
    Fetches profile telemetry data from OpenDota, extracts the historical aliases list,
    and populates OpenDota.Player_Aliases using a single, unified try block.
    """
    # FIXED LOGIC: Strict adherence to your verified URL string
    api_url = f"https://api.opendota.com/api/players/{player_id}"
    logging.info(f"Extracting historical aliases from OpenDota for ID: {player_id}")
    
    cursor = conn.cursor()
    try:
        response = requests.get(api_url, timeout=10)
        response.raise_for_status()
        data = response.json()

        profile = data.get('profile', {}) or {}
        account_id = profile.get('account_id')
        
        if not account_id:
            logging.warning(f"No valid account_id found for alias tracking on player {player_id}. Skipping.")
            return False

        aliases_list = profile.get('aliases', [])

        delete_sql = "DELETE FROM OpenDota.Player_Aliases WHERE account_id = ?;"
        cursor.execute(delete_sql, (int(account_id),))

        if aliases_list:
            insert_sql = """
                INSERT INTO OpenDota.Player_Aliases (account_id, alias_name)
                VALUES (?, ?);
            """
            for alias in aliases_list:
                if alias:
                    cursor.execute(insert_sql, (int(account_id), str(alias)))
                    
        conn.commit()
        logging.info(f"Successfully synchronized {len(aliases_list)} aliases for account {account_id} into OpenDota.Player_Aliases.")
        return True

    except Exception as e:
        logging.error(f"Pipeline processing failed for player aliases {player_id}: {e}")
        conn.rollback()
        return False
    finally:
        cursor.close()

def sync_opendota_player_matches(player_id, conn):
    """
    Fetches historical match list stubs from the correct OpenDota API path
    and upserts the data into OpenDota.Player_Matches using a single try block.
    """
    # VERIFIED CORRECT URL: Strictly using the /api/players/ route
    api_url = f"https://api.opendota.com/api/players/{player_id}/matches"
    logging.info(f"Extracting historic match overview stubs from OpenDota for ID: {player_id}")
    
    cursor = conn.cursor()
    try:
        # Step 1: Hit the network API endpoint
        response = requests.get(api_url, timeout=15)
        response.raise_for_status()
        matches = response.json()

        # Step 2: Execute Database Upsert (MERGE) Transaction Loop
        match_merge_sql = """
        MERGE OpenDota.Player_Matches AS target
        USING (SELECT ? AS match_id, ? AS account_id) AS source
        ON (target.match_id = source.match_id AND target.account_id = source.account_id)
        WHEN MATCHED THEN
            UPDATE SET 
                player_slot = ?, radiant_win = ?, duration = ?, game_mode = ?, 
                lobby_type = ?, hero_id = ?, hero_variant = ?, start_time = ?, 
                version = ?, kills = ?, deaths = ?, assists = ?, skill = ?, 
                average_rank = ?, leaver_status = ?, party_size = ?, last_synced_at = GETDATE()
        WHEN NOT MATCHED THEN
            INSERT (match_id, account_id, player_slot, radiant_win, duration, game_mode, 
                    lobby_type, hero_id, hero_variant, start_time, version, kills, deaths, 
                    assists, skill, average_rank, leaver_status, party_size)
            VALUES (source.match_id, source.account_id, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """
        
        for m in matches:
            match_id = m.get('match_id')
            if not match_id:
                continue
                
            radiant_win_bit = 1 if m.get('radiant_win') else 0
            
            core_params = (
                m.get('player_slot'),
                radiant_win_bit,
                m.get('duration'),
                m.get('game_mode'),
                m.get('lobby_type'),
                m.get('hero_id'),
                m.get('hero_variant'),
                m.get('start_time'),
                m.get('version'),
                m.get('kills'),
                m.get('deaths'),
                m.get('assists'),
                m.get('skill'),
                m.get('average_rank'),
                m.get('leaver_status'),
                m.get('party_size')
            )
            
            cursor.execute(match_merge_sql, (int(match_id), int(player_id)) + core_params + core_params)
            
        conn.commit()
        logging.info(f"Successfully processed match history records for player {player_id} into OpenDota.Player_Matches.")
        return True

    except Exception as e:
        logging.error(f"Pipeline processing failed for player match history stubs {player_id}: {e}")
        conn.rollback()
        return False
    finally:
        cursor.close()

def get_unsynced_match_ids(conn, limit=20):
    """
    Queries the database to find distinct match_ids that exist in the Player_Matches 
    table but have not yet been processed into the deep Match_Details table.
    """
    logging.info("Querying OpenDota database schemas for un-synced deep match targets...")
    
    cursor = conn.cursor()
    try:
        # Optimized lookup using a LEFT JOIN to find missing records
        query = """
            SELECT DISTINCT TOP (?) pm.match_id
            FROM OpenDota.Player_Matches pm
            LEFT JOIN OpenDota.Match_Details md ON pm.match_id = md.match_id
            WHERE md.match_id IS NULL
            ORDER BY pm.match_id DESC;
        """
        
        cursor.execute(query, (limit,))
        # Flatten the row tuples into a clean, list array of raw match IDs
        match_ids = [row[0] for row in cursor.fetchall()]
        
        logging.info(f"Discovery complete. Identified {len(match_ids)} un-synced matches ready for deep crawl.")
        return match_ids

    except Exception as e:
        logging.error(f"Failed to identify and queue un-synced match items: {e}")
        return []
    finally:
        cursor.close()

def sync_opendota_deep_match_details(match_id, conn):
    """
    Fetches comprehensive match telemetry from the correct OpenDota API path
    and updates both Match_Details and Match_Player_Performances within a single try block.
    """
    # FIXED: Verified exact functional endpoint path
    api_url = f"https://api.opendota.com/api/matches/{match_id}"
    logging.info(f"Extracting granular deep data metrics block from OpenDota for Match ID: {match_id}")
    
    cursor = conn.cursor()
    try:
        # Step 1: Hit the network API endpoint
        response = requests.get(api_url, timeout=15)
        response.raise_for_status()
        m = response.json()

        # Step 2: Ingest Match Header Summary Metrics (OpenDota.Match_Details)
        header_sql = """
        MERGE OpenDota.Match_Details AS target
        USING (SELECT ? AS match_id) AS source ON target.match_id = source.match_id
        WHEN MATCHED THEN
            UPDATE SET barracks_status_dire = ?, barracks_status_radiant = ?, cluster = ?, dire_score = ?, duration = ?, engine = ?, first_blood_time = ?, game_mode = ?, human_players = ?, match_seq_num = ?, radiant_score = ?, radiant_win = ?, skill = ?, start_time = ?, tower_status_dire = ?, tower_status_radiant = ?, version = ?, patch = ?, region = ?, last_updated_at = GETDATE()
        WHEN NOT MATCHED THEN
            INSERT (match_id, barracks_status_dire, barracks_status_radiant, cluster, dire_score, duration, engine, first_blood_time, game_mode, human_players, match_seq_num, radiant_score, radiant_win, skill, start_time, tower_status_dire, tower_status_radiant, version, patch, region)
            VALUES (source.match_id, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """
        h_params = (
            m.get('barracks_status_dire'), m.get('barracks_status_radiant'), m.get('cluster'), 
            m.get('dire_score'), m.get('duration'), m.get('engine'), m.get('first_blood_time'), 
            m.get('game_mode'), m.get('human_players'), m.get('match_seq_num'), m.get('radiant_score'), 
            1 if m.get('radiant_win') else 0, m.get('skill'), m.get('start_time'), m.get('tower_status_dire'), 
            m.get('tower_status_radiant'), m.get('version'), m.get('patch'), m.get('region')
        )
        cursor.execute(header_sql, (int(match_id),) + h_params + h_params)

        # Step 3: Ingest All 10 Participants Metrics (OpenDota.Match_Player_Performances)
        player_sql = """
        MERGE OpenDota.Match_Player_Performances AS target
        USING (SELECT ? AS match_id, ? AS player_slot) AS source ON target.match_id = source.match_id AND target.player_slot = source.player_slot
        WHEN MATCHED THEN
            UPDATE SET account_id = ?, kills = ?, deaths = ?, assists = ?, gold = ?, gold_per_min = ?, gold_spent = ?, net_worth = ?, total_gold = ?, xp_per_min = ?, total_xp = ?, level = ?, hero_id = ?, hero_variant = ?, hero_damage = ?, hero_healing = ?, tower_damage = ?, last_hits = ?, denies = ?, kda = ?, teamfight_participation = ?, stuns = ?, win = ?, lose = ?, last_updated_at = GETDATE()
        WHEN NOT MATCHED THEN
            INSERT (match_id, player_slot, account_id, kills, deaths, assists, gold, gold_per_min, gold_spent, net_worth, total_gold, xp_per_min, total_xp, level, hero_id, hero_variant, hero_damage, hero_healing, tower_damage, last_hits, denies, kda, teamfight_participation, stuns, win, lose)
            VALUES (source.match_id, source.player_slot, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """
        
        for p in m.get('players', []):
            slot = p.get('player_slot')
            if slot is None: 
                continue
                
            p_params = (
                p.get('account_id'), p.get('kills'), p.get('deaths'), p.get('assists'), 
                p.get('gold'), p.get('gold_per_min'), p.get('gold_spent'), p.get('net_worth'), 
                p.get('total_gold'), p.get('xp_per_min'), p.get('total_xp'), p.get('level'), 
                p.get('hero_id'), p.get('hero_variant'), p.get('hero_damage'), p.get('hero_healing'), 
                p.get('tower_damage'), p.get('last_hits'), p.get('denies'), p.get('kda'), 
                p.get('teamfight_participation'), p.get('stuns'), 
                1 if p.get('win') == 1 else 0, 1 if p.get('lose') == 1 else 0
            )
            cursor.execute(player_sql, (int(match_id), int(slot)) + p_params + p_params)

        conn.commit()
        logging.info(f"Successfully finalized deep database entries for Match ID {match_id}.")
        return True

    except Exception as e:
        logging.error(f"Pipeline error loading deep metrics for match {match_id}: {e}")
        conn.rollback()
        return False
    finally:
        cursor.close()

def sync_stratz_player_profile(account_id, conn):
    """
    Queries the STRATZ GraphQL API to extract player metadata metrics
    and updates both Stratz.Players and Stratz.Player_Aliases within a single try block.
    """
    stratz_token = os.getenv("STRATZ_TOKEN")
    if not stratz_token:
        logging.warning("STRATZ_TOKEN missing from environment configurations. Skipping STRATZ sync.")
        return False

    # FIXED: Verified exact functional endpoint path
    api_url = "https://api.stratz.com/graphql"
    headers = {
        "Authorization": f"Bearer {stratz_token}",
        "Content-Type": "application/json"
    }

    # Format the input account_id directly into the string query body
    graphql_query = """
    query GetPlayerProfile {
      player(steamAccountId: %d) {
        matchCount
        winCount
        imp
        firstMatchDate
        lastMatchDate
        lastMatchRegionId
        behaviorScore
        isFollowed
        names {
          name
          lastSeenDateTime
        }
      }
    }
    """ % int(account_id)

    logging.info(f"Extracting STRATZ player profile analytics for ID: {account_id}")

    cursor = conn.cursor()
    try:
        # Step 1: Execute the network POST query request to STRATZ
        response = requests.post(api_url, json={"query": graphql_query}, headers=headers, timeout=15)
        response.raise_for_status()
        res_data = response.json()

        if "errors" in res_data:
            logging.error(f"STRATZ GraphQL returned query validation errors for {account_id}: {res_data['errors']}")
            return False

        player_data = res_data.get("data", {}).get("player")
        if not player_data:
            logging.warning(f"No player database metrics profile returned from STRATZ for ID: {account_id}")
            return False

        # Step 2: Execute Upsert (MERGE) for Stratz.Players
        player_merge_sql = """
        MERGE Stratz.Players AS target
        USING (SELECT ? AS steam_account_id) AS source
        ON (target.steam_account_id = source.steam_account_id)
        WHEN MATCHED THEN
            UPDATE SET 
                match_count = ?, win_count = ?, imp = ?, first_match_date = ?, 
                last_match_date = ?, last_match_region_id = ?, behavior_score = ?, 
                is_followed = ?, last_updated_at = GETDATE()
        WHEN NOT MATCHED THEN
            INSERT (steam_account_id, match_count, win_count, imp, first_match_date, 
                    last_match_date, last_match_region_id, behavior_score, is_followed)
            VALUES (source.steam_account_id, ?, ?, ?, ?, ?, ?, ?, ?);
        """
        
        is_followed_bit = 1 if player_data.get("isFollowed") else 0
        core_params = (
            player_data.get("matchCount"),
            player_data.get("winCount"),
            player_data.get("imp"),
            player_data.get("firstMatchDate"),
            player_data.get("lastMatchDate"),
            player_data.get("lastMatchRegionId"),
            player_data.get("behaviorScore"),
            is_followed_bit
        )
        
        cursor.execute(player_merge_sql, (int(account_id),) + core_params + core_params)

        # Step 3: Clear and Sync child rows for Stratz.Player_Aliases
        cursor.execute("DELETE FROM Stratz.Player_Aliases WHERE steam_account_id = ?;", (int(account_id),))
        
        names_list = player_data.get("names", [])
        if names_list:
            insert_alias_sql = """
                INSERT INTO Stratz.Player_Aliases (steam_account_id, alias_name, last_seen_date_time)
                VALUES (?, ?, ?);
            """
            for n in names_list:
                alias_name = n.get("name")
                if alias_name:
                    cursor.execute(insert_alias_sql, (int(account_id), str(alias_name), n.get("lastSeenDateTime")))

        conn.commit()
        logging.info(f"Successfully processed profile records for player {account_id} into Stratz.Players and Stratz.Player_Aliases.")
        return True

    except Exception as e:
        logging.error(f"Pipeline processing failed for STRATZ player profile components {account_id}: {e}")
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
        
        # PHASE 1: Collect profiles, aliases, and historical stubs across all players
        for player_id in account_list:
            profile_success = sync_opendota_player_profile(player_id, conn)
            
        # PHASE 1: Collect profile layers and match stub entries
        for player_id in account_list:
            profile_success = sync_opendota_player_profile(player_id, conn)
            
            if profile_success:
                sync_opendota_player_aliases(player_id, conn)
                sync_opendota_player_matches(player_id, conn)
                
                # Layer on STRATZ profile metadata tracking sandboxes
                sync_stratz_player_profile(player_id, conn)
        
        # PHASE 2: Automatically discover missing matches from the combined pool
        unsynced_matches = get_unsynced_match_ids(conn, limit=20)
        
        # PHASE 3: Deep crawl match detail data layers
        if unsynced_matches:
            logging.info(f"Discovered {len(unsynced_matches)} missing match profiles. Starting crawlers.")
            for match_row in unsynced_matches:
                # Extract integer match_id safely from the row item query result
                match_id = match_row
                sync_opendota_deep_match_details(match_id, conn)
                time.sleep(1.1)  # Space calls out to stay well clear of standard public api tier blocking rules
        else:
            logging.info("OpenDota details tables are completely synchronized.")
                
    except Exception as e:
        logging.critical(f"Master pipeline control routine collapsed: {e}")
    finally:
        if conn:
            conn.close()
            logging.info("Pipeline database connection safely closed.")

if __name__ == "__main__":
    main()
