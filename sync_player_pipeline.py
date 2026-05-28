import os
import logging
import sys
import requests
import mssql_python
import time
from dotenv import load_dotenv

# Initialize environment variables
load_dotenv()

# Configure logging (Console + Log File)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler("opendota_pipeline.log"),
        logging.StreamHandler(sys.stdout)
    ]
)

# Pull database parameters from .env
DB_SERVER = os.getenv("DB_SERVER")
DB_DATABASE = os.getenv("DB_DATABASE")

if not DB_SERVER or not DB_DATABASE:
    logging.critical("Missing DB config in .env file. Terminating.")
    sys.exit(1)

CONN_STR = (
    f"Server={DB_SERVER};"
    f"Database={DB_DATABASE};"
    "Trusted_Connection=yes;"
    "Encrypt=yes;"
    "TrustServerCertificate=yes;"
)

def sync_player_profile(account_id, conn):
    # Fetches profile metrics and updates OpenDota_Players and Aliases.
    api_url = f"https://api.opendota.com/api/players/{account_id}"
    logging.info(f"Extracting profile for Player ID {account_id} using {api_url}")
    
    try:
        response = requests.get(api_url, timeout=10)
        logging.info(f"Response: {response.status_code} - {response.reason}")
        response.raise_for_status()
        data = response.json()
        profile = data.get('profile', {}) or {}
        account_id = profile.get('account_id')
        if not account_id:
            return False

        cursor = conn.cursor()
        try:
            player_merge_sql = """
                MERGE dbo.OpenDota_Players AS target
                USING (SELECT ? AS account_id) AS source ON (target.account_id = source.account_id)
                WHEN MATCHED THEN
                    UPDATE SET 
                        tracked_until = ?, solo_competitive_rank = ?, competitive_rank = ?, rank_tier = ?, leaderboard_rank = ?
                        ,personaname = ?, name = ?, plus_status = ?, cheese = ?, steamid = ?, avatar = ?
                        ,avatarmedium = ?, avatarfull = ?, profileurl = ?, last_login = ?, loccountrycode = ?
                        ,is_contributor = ?, is_subscriber = ?
                        ,last_updated_at = GETDATE()
                WHEN NOT MATCHED THEN
                    INSERT (
                        account_id
                        ,tracked_until, solo_competitive_rank, competitive_rank, rank_tier, leaderboard_rank
                        ,personaname, name, plus_status, cheese, steamid, avatar
                        ,avatarmedium, avatarfull, profileurl, last_login, loccountrycode
                        ,is_contributor, is_subscriber
                    )
                    VALUES (
                        ?
                        ,?, ?, ?, ?, ?
                        ,?, ?, ?, ?, ?, ?
                        ,?, ?, ?, ?, ?
                        ,?, ?
                    )
                ;
            """
            params = (
                account_id
                ,data.get('tracked_until'), data.get('solo_competitive_rank'), data.get('competitive_rank'), data.get('rank_tier'), data.get('leaderboard_rank')
                ,profile.get('personaname'), profile.get('name'), 1 if profile.get('plus') else 0, profile.get('cheese'), profile.get('steamid'), profile.get('avatar')
                ,profile.get('avatarmedium'), profile.get('avatarfull'), profile.get('profileurl'), profile.get('last_login'), profile.get('loccountrycode')
                ,1 if profile.get('is_contributor') else 0, 1 if profile.get('is_subscriber') else 0
            )
            cursor.execute(player_merge_sql, params + params)
            
            cursor.execute("DELETE FROM dbo.OpenDota_Player_Aliases WHERE account_id = ?", (account_id,))
            for alias in profile.get('aliases', []):
                if alias:
                    cursor.execute("INSERT INTO dbo.OpenDota_Player_Aliases (account_id, alias_name) VALUES (?, ?)", (account_id, str(alias)))
            
            conn.commit()
            return True
        except Exception as e:
            logging.error(f"Database profile error for player {account_id}: {e}")
            logging.error(f"Query: {player_merge_sql}")
            logging.error(f"Parameters: {params}")
#            logging.error("Traceback details:", exc_info=True)
            conn.rollback()
            return False
        finally:
            cursor.close()

    except Exception as e:
        logging.error(f"Failed to fetch profile for Player {account_id}: {e}")
#        logging.error("Traceback details:", exc_info=True)
        return False

#def sync_player_matches(account_id, conn):
#    # Fetches historic match list stubs to populate history.
#    api_url = f"https://api.opendota.com/api/players/{account_id}/matches"
#    logging.info(f"Fetching match overview stubs for Player ID {account_id} using {api_url}")
#    
#    try:
#        response = requests.get(api_url, timeout=15)
#        response.raise_for_status()
#        matches = response.json()
#        cursor = conn.cursor()
#
#        try:
#            match_merge_sql = """
#                MERGE dbo.OpenDota_Player_Matches AS target
#                USING (SELECT ? AS match_id, ? AS account_id) AS source
#                ON (target.match_id = source.match_id AND target.account_id = source.account_id)
#                WHEN MATCHED THEN
#                    UPDATE SET
#                        player_slot = ?, radiant_win = ?, duration = ?, game_mode = ?, lobby_type = ?
#                        ,hero_id = ?, hero_variant = ?, start_time = ?, version = ?, kills = ?, deaths = ?
#                        ,assists = ?, skill = ?, average_rank = ?, leaver_status = ?, party_size = ?
#                        ,last_synced_at = GETDATE()
#                WHEN NOT MATCHED THEN
#                    INSERT (
#                        match_id, account_id
#                        ,player_slot, radiant_win, duration, game_mode, lobby_type
#                        ,hero_id, hero_variant, start_time, version, kills, deaths
#                        ,assists, skill, average_rank, leaver_status, party_size
#                    )
#                    VALUES (
#                        source.match_id, source.account_id
#                        ,?, ?, ?, ?, ?
#                        ,?, ?, ?, ?, ?, ?
#                        ,?, ?, ?, ?, ?
#                    )
#                ;
#            """
#            for m in matches:
#                match_id = m.get('match_id')
#                if not match_id: continue
#                
#                core_params = (
#                    m.get('player_slot'), 1 if m.get('radiant_win') else 0, m.get('duration'), m.get('game_mode'), m.get('lobby_type')
#                    ,m.get('hero_id'), m.get('hero_variant'), m.get('start_time'), m.get('version'), m.get('kills'), m.get('deaths')
#                    ,m.get('assists'), m.get('skill'), m.get('average_rank'), m.get('leaver_status'), m.get('party_size')
#                )
#                cursor.execute(match_merge_sql, (match_id, account_id) + core_params + core_params)
#                
#            conn.commit()
#        except Exception as e:
#            logging.error(f"Database error saving match summaries for player {account_id}: {e}")
#            logging.error(f"Query: {match_merge_sql}")
#            logging.error(f"Parameters: {core_params}")
##            logging.error("Traceback details:", exc_info=True)
#            conn.rollback()
#        finally:
#            cursor.close()
#
#    except Exception as e:
#        logging.error(f"Failed to fetch match stubs for Player {account_id}: {e}")
##        logging.error("Traceback details:", exc_info=True)
#        return

def sync_player_matches_from_stratz(account_id, conn):
    """
    Queries STRATZ GraphQL API to pull ALL match stubs for an account_id,
    paginating 100 matches at a time and merging them into OpenDota_Player_Matches.
    """
    stratz_token = os.getenv("STRATZ_TOKEN")
    if not stratz_token:
        logging.error("STRATZ_TOKEN missing from environment variables. Skipping STRATZ sync.")
        return

    headers = {
        "Authorization": f"Bearer {stratz_token}",
        "User-Agent": "STRATZ_API",
        "Content-Type": "application/json"
    }
    
    cursor = conn.cursor()
    match_merge_sql = """
        MERGE OpenDota_Player_Matches AS target
        USING (SELECT ? AS match_id, ? AS account_id) AS source
        ON (target.match_id = source.match_id AND target.account_id = source.account_id)
        WHEN MATCHED THEN
            UPDATE SET player_slot = ?, radiant_win = ?, duration = ?, hero_id = ?, start_time = ?, last_synced_at = GETDATE()
        WHEN NOT MATCHED THEN
            INSERT (match_id, account_id, player_slot, radiant_win, duration, hero_id, start_time)
            VALUES (source.match_id, source.account_id, ?, ?, ?, ?, ?)
        ;
    """

    skip = 0
    take = 5
    keep_fetching = True
    total_inserted = 0

    logging.info(f"Initiating full STRATZ match history extraction for player: {account_id}")

    while keep_fetching:
        # STRATZ GraphQL Query mapping essential stub metrics

        try:
            query = """
                query GetPlayerMatchIds {
                    player(steamAccountId: %d) {
                        matches(request: { skip: %d, take: %d }) {
                            id
                            startDateTime
                            durationSeconds
                            gameMode
                            players(steamAccountId: %d) {
                                playerSlot
                                isRadiant
                                isVictory
                                heroId
                            }
                        }
                    }
                }
            """ % (int(account_id), skip, take, int(account_id))

            payload = {"query": query}
            response = requests.post(
                "https://api.stratz.com/graphql", json=payload, headers=headers
            )
            response.raise_for_status()
            logging.info(f"API Response Status: {response.status_code}")
            res_data = response.json()
            match_ids = [
                match["id"] for match in res_data["data"]["player"]["matches"]
            ]
            logging.info(f"Total matches fetched from STRATZ: {len(match_ids)}")
            
            # Check for structural errors returning inside the GraphQL context payload
            if "errors" in res_data:
                logging.error(f"STRATZ GraphQL Error: {res_data['errors']}")
                break
                
            match_list = res_data.get("data", {}).get("player", {}).get("matches", [])
            
            if not match_list:
                logging.info(f"No more matches returned from STRATZ for account {account_id}.")
                keep_fetching = False
                break

            logging.info(f"Retrieved {len(match_list)} matches from STRATZ (Offset: {skip}). Processing database write...")

            for m in match_list:
                match_id = m.get("id")
                if not match_id:
                    continue

                # Safely locate the specific player metrics container array segment
                players_array = m.get("players", [])
                if not players_array:
                    continue
                p = players_array[0]

                player_slot = p.get("playerSlot")
                rad_win = 1 if p.get("isVictory") else 0
                duration = m.get("durationSeconds")
                hero_id = p.get("heroId")
                start_time = m.get("startDateTime")

                core_params = (player_slot, rad_win, duration, hero_id, start_time)
                cursor.execute(match_merge_sql, (match_id, account_id) + core_params + core_params)
                total_inserted += 1

            conn.commit()
            
            # If the response returned less than the requested amount, we have reached the end of their history
            if len(match_list) < take:
                keep_fetching = False
            else:
                skip += take  # Shift pagination window forward

            time.sleep(1.1)

        except Exception as err:
            logging.error(f"STRATZ match sync loop encountered a critical error for player {account_id}: {err}")
            logging.error(f"GraphQL Query: {query}")
#            logging.error("Traceback details:", exc_info=True)
            conn.rollback()
            keep_fetching = False

    cursor.close()
    logging.info(f"STRATZ match extraction completed. Processed {total_inserted} records for account {account_id}.")

def get_unsynced_match_ids(conn, limit=5):
    # Identifies match IDs missing from the details tables.
    cursor = conn.cursor()
    query = """
        SELECT DISTINCT TOP (?) pm.match_id
        FROM dbo.OpenDota_Player_Matches pm
        LEFT JOIN dbo.OpenDota_Match_Details md ON pm.match_id = md.match_id
        WHERE md.match_id IS NULL
        ORDER BY pm.match_id DESC;
    """
    try:
        cursor.execute(query, (limit,))
        return [row[0] for row in cursor.fetchall()]
    except Exception as e:
        logging.error(f"Failed to query un-synced match items: {e}")
        logging.error(f"Query: {query}")
        logging.error(f"Limit: {limit}")
#        logging.error("Traceback details:", exc_info=True)
        return []
    
    finally:
        cursor.close()

def sync_deep_match_details(match_id, conn):
    # Pulls full /matches/{id} telemetry object payload parsing details.
    api_url = f"https://api.opendota.com/api/matches/{match_id}"
    logging.info(f"Extracting details for Match ID {match_id} using {api_url}")
    
    try:
        response = requests.get(api_url, timeout=15)
        response.raise_for_status()
        m = response.json()
        cursor = conn.cursor()

        try:
            # Step A: Upsert Match Header Summary Table Metrics
            header_sql = """
                MERGE dbo.OpenDota_Match_Details AS target
                USING (SELECT ? AS match_id) AS source ON target.match_id = source.match_id
                WHEN MATCHED THEN
                    UPDATE SET
                        barracks_status_dire = ?, barracks_status_radiant = ?, cluster = ?, dire_score = ?, duration = ?, engine = ?
                        ,first_blood_time = ?, game_mode = ?, human_players = ?, match_seq_num = ?, radiant_score = ?
                        ,radiant_win = ?, skill = ?, start_time = ?, tower_status_dire = ?, tower_status_radiant = ?
                        ,version = ?, patch = ?, region = ?
                        ,last_updated_at = GETDATE()
                WHEN NOT MATCHED THEN
                    INSERT (
                        match_id
                        ,barracks_status_dire, barracks_status_radiant, cluster, dire_score, duration, engine
                        ,first_blood_time, game_mode, human_players, match_seq_num, radiant_score
                        ,radiant_win, skill, start_time, tower_status_dire, tower_status_radiant
                        ,version, patch, region
                    )
                    VALUES (
                        source.match_id
                        ,?, ?, ?, ?, ?, ?
                        ,?, ?, ?, ?, ?
                        ,?, ?, ?, ?, ?
                        ,?, ?, ?
                    )
                ;
            """
            h_params = (
                m.get('barracks_status_dire'), m.get('barracks_status_radiant'), m.get('cluster'), m.get('dire_score'), m.get('duration'), m.get('engine')
                ,m.get('first_blood_time'), m.get('game_mode'), m.get('human_players'), m.get('match_seq_num'), m.get('radiant_score')
                ,1 if m.get('radiant_win') else 0, m.get('skill'), m.get('start_time'), m.get('tower_status_dire'), m.get('tower_status_radiant')
                ,m.get('version'), m.get('patch'), m.get('region')
            )
            cursor.execute(header_sql, (match_id,) + h_params + h_params)

            # Step B: Loop updating every player performance row (Up to 10 players)
            player_sql = """
                MERGE dbo.OpenDota_Match_Player_Performances AS target
                USING (SELECT ? AS match_id, ? AS player_slot) AS source ON target.match_id = source.match_id AND target.player_slot = source.player_slot
                WHEN MATCHED THEN
                    UPDATE SET
                        account_id = ?, kills = ?, deaths = ?, assists = ?, gold = ?, gold_per_min = ?, gold_spent = ?
                        ,net_worth = ?, total_gold = ?, xp_per_min = ?, total_xp = ?, level = ?, hero_id = ?, hero_variant = ?
                        ,hero_damage = ?, hero_healing = ?, tower_damage = ?, last_hits = ?, denies = ?, kda = ?
                        ,teamfight_participation = ?, stuns = ?, win = ?, lose = ?
                        ,last_updated_at = GETDATE()
                WHEN NOT MATCHED THEN
                    INSERT (
                        match_id, player_slot
                        ,account_id, kills, deaths, assists, gold, gold_per_min, gold_spent
                        ,net_worth, total_gold, xp_per_min, total_xp, level, hero_id, hero_variant
                        ,hero_damage, hero_healing, tower_damage, last_hits, denies, kda
                        ,teamfight_participation, stuns, win, lose
                    )
                    VALUES (
                        source.match_id, source.player_slot
                        ,?, ?, ?, ?, ?, ?, ?
                        ,?, ?, ?, ?, ?, ?, ?
                        ,?, ?, ?, ?, ?, ?
                        ,?, ?, ?, ?
                    )
                ;
            """
            for p in m.get('players', []):
                slot = p.get('player_slot')
                if slot is None: continue
                    
                p_params = (
                    p.get('account_id'), p.get('kills'), p.get('deaths'), p.get('assists'), p.get('gold'), p.get('gold_per_min'), p.get('gold_spent')
                    ,p.get('net_worth'), p.get('total_gold'), p.get('xp_per_min'), p.get('total_xp'), p.get('level'), p.get('hero_id'), p.get('hero_variant')
                    ,p.get('hero_damage'), p.get('hero_healing'), p.get('tower_damage'), p.get('last_hits'), p.get('denies'), p.get('kda')
                    ,p.get('teamfight_participation'), p.get('stuns'), 1 if p.get('win') == 1 else 0, 1 if p.get('lose') == 1 else 0
                )
                cursor.execute(player_sql, (match_id, slot) + p_params + p_params)

            conn.commit()
        except Exception as e:
            logging.error(f"Database error writing deep details for match {match_id}: {e}")
            logging.error(f"Query: {player_sql}")
            logging.error(f"Parameters: {p_params}")
#            logging.error("Traceback details:", exc_info=True)
            conn.rollback()
        finally:
            cursor.close()

    except Exception as e:
        logging.error(f"API Error pulling match metrics {match_id}: {e}")
#        logging.error("Traceback details:", exc_info=True)
        return


def main():
    raw_accounts = os.getenv("ACCOUNT_IDS", "")
    if not raw_accounts: return
    account_id_list = [a_id.strip() for a_id in raw_accounts.split(",") if a_id.strip()]
    
    conn = None
    try:
        logging.info("Opening connection to SQL Server.")
        conn = mssql_python.connect(CONN_STR)
        
        # Phase 1: Profiles & Stubs
        for account_id in account_id_list:
            if sync_player_profile(account_id, conn):
                # REPLACED OpenDota with STRATZ for comprehensive stub lists
                #sync_player_matches(account_id, conn)
                sync_player_matches_from_stratz(account_id, conn)

        
        # Phase 2 & 3: Match Discovery & Deep Crawling
        unsynced_matches = get_unsynced_match_ids(conn, limit=5)
        for match_id in unsynced_matches:
            sync_deep_match_details(match_id, conn)
                
    except Exception as e:
        logging.critical(f"Pipeline crashed: {e}")
    finally:
        if conn:
            conn.close()
            logging.info("Pipeline closed safely.")

if __name__ == "__main__":
    main()
