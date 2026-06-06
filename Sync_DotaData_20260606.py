# In OpenDota.Account_Matches and Stratz.Account_Matchese, barracks_status_dire values are not the same between OpenDota and Stratz.
# Alias entries between OpenDota and Stratz appear to be tracked differently but accurate for the most part.

import logging
import mssql_python
import os
import requests
import subprocess
import sys
import time
from datetime import datetime
from dotenv import find_dotenv, load_dotenv, set_key
from urllib import response

# 1. Initialize environment variables from your local .env file
load_dotenv()

# 2. Configure the logging layout (Outputs to console and updates 'opendota_sync.log')
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s.%(msecs)03d [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.FileHandler("opendota_sync.log"),
        logging.StreamHandler(sys.stdout)
    ]
)

DB_SERVER = os.getenv("DB_SERVER")
DB_DATABASE = os.getenv("DB_DATABASE")
ACCOUNT_IDS = os.getenv("ACCOUNT_IDS", "")
VPN_ENABLED = True if os.getenv("VPN_ENABLED").lower() == "true" else False
if VPN_ENABLED:
    VPN_PATH = os.getenv(r"VPN_PATH", r"C:\Program Files\Windscribe\windscribe-cli.exe")
    VPN_LOCATIONS = os.getenv("VPN_LOCATIONS", "Not set")
    VPN_LOCATIONS = VPN_LOCATIONS.split(",") if VPN_LOCATIONS else []
    VPN_LOCATION_START_INDEX = int(os.getenv("VPN_LOCATION_START_INDEX", 0))
SOAP = True if os.getenv("SYNC_OPENDOTA_ACCOUNT_PROFILE_FLAG").lower() == "true" else False
SSAP = True if os.getenv("SYNC_STRATZ_ACCOUNT_PROFILE_FLAG").lower() == "true" else False
SOAM = True if os.getenv("SYNC_OPENDOTA_ACCOUNT_MATCHES_FLAG").lower() == "true" else False
SSMD = True if os.getenv("SYNC_STRATZ_MATCH_DETAILS_FLAG").lower() == "true" else False
SOMI = True if os.getenv("SYNC_OPENDOTA_MATCH_IDS_FLAG").lower() == "true" else False
TRACEBACK = True if os.getenv("TRACEBACK_FLAG").lower() == "true" else False

logging.info("Starting Dota 2 data synchronization process.")
logging.info(f"Environment variables:")
logging.info(f"\tACCOUNT_IDS: {ACCOUNT_IDS}")
logging.info(f"\tVPN_ENABLED: {VPN_ENABLED}")
if VPN_ENABLED:
    if not os.path.exists(VPN_PATH):
        logging.warning(f"VPN executable not found at {VPN_PATH}. VPN functionality will be disabled.")
        VPN_ENABLED = False
    else:
        logging.info(f"\tVPN_PATH: {VPN_PATH}")
        logging.info(f"\tVPN_LOCATIONS: {VPN_LOCATIONS}")
        logging.info(f"\tVPN_LOCATION_START_INDEX: {VPN_LOCATION_START_INDEX}")
logging.info(f"\tSYNC_OPENDOTA_ACCOUNT_PROFILE_FLAG: {SOAP}")
logging.info(f"\tSYNC_STRATZ_ACCOUNT_PROFILE_FLAG: {SSAP}")
logging.info(f"\tSYNC_OPENDOTA_ACCOUNT_MATCHES_FLAG: {SOAM}")
logging.info(f"\tSYNC_STRATZ_MATCH_DETAILS_FLAG: {SSMD}")
logging.info(f"\tSYNC_OPENDOTA_MATCH_IDS_FLAG: {SOMI}")
logging.info(f"\tTRACEBACK_FLAG: {TRACEBACK}")

# 3. Pull database credentials out of the environment variables safely
if not DB_SERVER or not DB_DATABASE:
    logging.critical("{sys._getframe().f_code.co_name}: Missing DB configuration (DB_SERVER or DB_DATABASE) inside your .env file. Terminating.")
    sys.exit(1)

# 4. Assemble your standard Microsoft SQL Server connection string parameters
CONN_STR = (
    f"Server={DB_SERVER};"
    f"Database={DB_DATABASE};"
    "Trusted_Connection=yes;"
    "Encrypt=yes;"
    "TrustServerCertificate=yes;"
)

def sync_opendota_account_profile(account_id, conn):
    """
    Fetches a single player profile from the correct OpenDota API path
    and upserts the data into OpenDota.Accounts using a single try block.
    """
    logging.info(f"Function: {sys._getframe().f_code.co_name}")
    logging.info(f"Account ID: {account_id}")

    # FIXED LOGIC: Strict adherence to your verified URL string
    api_url = f"https://api.opendota.com/api/players/{account_id}"
    logging.info(f"URL: {api_url}")
    
    cursor = conn.cursor()
    try:
        response = requests.get(api_url, timeout=10)
        logging.info(f"Response: {response.status_code} - {response.reason}")

        if response.status_code == 404:
            logging.warning(f"Ignoring Account ID: {account_id}, inserting into OpenDota.Ignored_Accounts.")
            cursor.execute("" \
                "INSERT INTO OpenDota.Ignored_Accounts (account_id, reason)" \
                "VALUES (?, ?)", (account_id, f"Response: {response.status_code} - {response.reason}"))
            conn.commit()
            cursor.close()
            return 
        
        response.raise_for_status()
        data = response.json()

        # Get the profile data from the root 'data' object
        profile = data.get('profile', {}) or {}
        account_id = profile.get('account_id')
        
        if not account_id:
            logging.warning(f"{api_url} not detected. Skipping.")
            return 

        last_log_raw = profile.get('last_login')
        last_login = None
        if last_log_raw:
            clean_ts = last_log_raw.replace('T', ' ').replace('Z', '')
            last_login = datetime.strptime(clean_ts, '%Y-%m-%d %H:%M:%S.%f')

    except Exception as e:
        logging.error(f"{api_url} processing failed: {e}")
        logging.error("Traceback details:", exc_info=True) if TRACEBACK else None
        return 

    try:
        player_merge_sql = """
            MERGE OpenDota.Accounts AS target
            USING (SELECT ? AS account_id) AS source
            ON (target.account_id = source.account_id)
            WHEN MATCHED THEN
                UPDATE SET 
                    tracked_until = ?, solo_competitive_rank = ?, competitive_rank = ?, 
                    rank_tier = ?, leaderboard_rank = ?, 
                    computed_mmr = ?, computed_mmr_turbo = ?, 
                    personaname = ?, name = ?, 
                    plus_status = ?, cheese = ?, steamid = ?, avatar = ?, avatarmedium = ?, 
                    avatarfull = ?, profileurl = ?, last_login = ?, loccountrycode = ?, 
                    is_contributor = ?, is_subscriber = ?, last_updated_at = GETDATE()
            WHEN NOT MATCHED THEN
                INSERT (account_id, tracked_until, solo_competitive_rank, competitive_rank, 
                        rank_tier, leaderboard_rank, 
                        computed_mmr, computed_mmr_turbo,
                        personaname, name, plus_status, cheese, 
                        steamid, avatar, avatarmedium, avatarfull, profileurl, last_login, 
                        loccountrycode, is_contributor, is_subscriber)
                VALUES (source.account_id, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """
        
        params = (
            int(account_id), data.get('tracked_until'), data.get('solo_competitive_rank'),
            data.get('competitive_rank'), data.get('rank_tier'), data.get('leaderboard_rank'),
            data.get('computed_mmr'), data.get('computed_mmr_turbo'),
            profile.get('personaname'), profile.get('name'), profile.get('plus'),
            profile.get('cheese'), profile.get('steamid'), profile.get('avatar'),
            profile.get('avatarmedium'), profile.get('avatarfull'), profile.get('profileurl'),
            last_login, profile.get('loccountrycode'), profile.get('is_contributor'),
            profile.get('is_subscriber')
        )
        
        logging.info(f"Merging account into OpenDota.Accounts.")
        cursor.execute(player_merge_sql, params + params[1:])

        # Get the aliases list from the root 'data' object
        logging.info(f"Checking for aliases.")
        aliases_list = data.get('aliases', [])

        if aliases_list:

            insert_sql = """
                IF NOT EXISTS (
                    SELECT 1
                    FROM OpenDota.Account_Aliases
                    WHERE account_id = ?
                    AND name_since = ?
                )
                INSERT INTO OpenDota.Account_Aliases (account_id, alias_name, name_since)
                VALUES (?, ?, ?);
            """
            for alias_obj in aliases_list:
                # FIX 2: Safely extract the structural string name from the object dictionary mapping
                alias_name = alias_obj.get('personaname')
                name_since = alias_obj.get('name_since')
                if alias_name:
                    cursor.execute(insert_sql, (int(account_id), name_since, int(account_id), str(alias_name), name_since))

        conn.commit()
        logging.info(f"{api_url} processed into OpenDota.Accounts and OpenDota.Account_Aliases.")
        return 

    except Exception as e:
        logging.error(f"{api_url} processing failed: {e}")
        logging.error(f"Merge SQL: {player_merge_sql}") if player_merge_sql else None
        logging.error(f"Merge Parameters: {params}") if params else None
        logging.error(f"Insert SQL: {insert_sql}") if insert_sql else None
        logging.error(f"Insert Parameters: {int(account_id)}, {str(alias_name)}, {name_since}, {int(account_id)}, {name_since}") if alias_name else None
        logging.error("Traceback details:", exc_info=True) if TRACEBACK else None
        conn.rollback()
        return 
    finally:
        cursor.close()

def sync_stratz_account_profile(account_id, conn):
    """
    Queries the STRATZ GraphQL API to extract player metadata metrics
    and updates both Stratz.Players and Stratz.Player_Aliases within a single try block.
    """
    logging.info(f"Function: {sys._getframe().f_code.co_name}")
    logging.info(f"Account ID: {account_id}")

    stratz_token = os.getenv("STRATZ_TOKEN")
    if not stratz_token:
        logging.warning(f"STRATZ_TOKEN missing from environment configurations. Skipping STRATZ sync.")
        return 
    
    # EXACT EXPLICIT URL: No variations, no version numbers
    api_url = "https://api.stratz.com/graphql"
    headers = {
        "Authorization": f"Bearer {stratz_token}",
        "Content-Type": "application/json"
    }

    graphql_query = """
        query GetPlayerMatchIds {
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

    cursor = conn.cursor()
    try:
        response = requests.post(api_url, json={"query": graphql_query}, headers=headers, timeout=15)
        logging.info(f"Response: {response.status_code} - {response.reason}")
        response.raise_for_status()
        res_data = response.json()

        if "errors" in res_data:
            # 1. Safely extract the message from the first error object
            errors_list = res_data.get("errors", [])
            first_error_msg = errors_list[0].get("message", "") if errors_list else ""

            # 2. Check for your specific ignorable error condition
            if first_error_msg.startswith("Player Id is missing or anonymous"):
                logging.info(f"Player {account_id} is missing or anonymous. Continuing processing.")
                # Do NOT return here. Letting the code pass through allows it to continue.
            else:
                # 3. Handle all other legitimate API errors by logging and exiting
                logging.error(f"STRATZ GraphQL returned query validation errors for {account_id}: {res_data['errors']}")
                logging.error(f"Query: {graphql_query}") if graphql_query else None
                logging.error("Traceback details:", exc_info=True) if TRACEBACK else None
                return

        player_data = res_data.get("data", {}).get("player")
        if not player_data:
            logging.warning(f"No account profile returned from STRATZ for ID: {account_id}")
            return 

        player_merge_sql = """
            MERGE Stratz.Accounts AS target
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
        
        logging.info(f"Merging account into Stratz.Accounts.")
        cursor.execute(player_merge_sql, (int(account_id),) + core_params + core_params)
        
        logging.info(f"Checking for aliases.")
        names_list = player_data.get("names", [])
        if names_list:
            insert_alias_sql = """
                IF NOT EXISTS (
                    SELECT 1
                    FROM Stratz.Account_Aliases
                    WHERE steam_account_id = ?
                    AND last_seen_date_time = ?
                )
                INSERT INTO Stratz.Account_Aliases (steam_account_id, alias_name, last_seen_date_time)
                VALUES (?, ?, ?);
            """
            for n in names_list:
                alias_name = n.get("name")
                if alias_name:
                    cursor.execute(insert_alias_sql, (int(account_id), n.get("lastSeenDateTime"), int(account_id), str(alias_name), n.get("lastSeenDateTime")))
                    
        conn.commit()
        logging.info(f"{account_id} processed into Stratz.Accounts and Stratz.Account_Aliases.")
        return 

    except Exception as e:
        logging.error(f"STRATZ {account_id} processing failed: {e}")
        logging.error(f"Merge SQL: {player_merge_sql}") if player_merge_sql else None
        logging.error(f"Merge Parameters: {core_params}") if core_params else None
        logging.error(f"Insert SQL: {insert_alias_sql}") if insert_alias_sql else None
        logging.error(f"Insert Values: {int(account_id)}, str{alias_name}, {n.get('lastSeenDateTime')}") if alias_name else None
        logging.error("Traceback details:", exc_info=True) if TRACEBACK else None
        conn.rollback()
        return 
    finally:
        cursor.close()

def sync_opendota_account_matches(account_id, conn):
    """
    Fetches historical match list stubs from the correct OpenDota API path
    and inserts the data into OpenDota.Account_Matches using a single try block.
    """
    logging.info(f"Function: {sys._getframe().f_code.co_name}")
    logging.info(f"Account ID: {account_id}")

    # VERIFIED CORRECT URL: Strictly using the /api/players/ route
    # /matches isn't return the most recent so I've added /recentmatches as well, which returns the most recent 20 matches 
    # and should be used in conjunction with /matches to ensure we have the latest data.
    api_urls = [
        f"https://api.opendota.com/api/players/{account_id}/matches",
        f"https://api.opendota.com/api/players/{account_id}/recentmatches"
    ]

    cursor = conn.cursor()
    try:
        query = """
            SELECT am.match_id
            FROM OpenDota.Account_Matches am
            WHERE am.account_id = ?
            ORDER BY am.match_id
        """

        logging.info(f"Checking for existing matches.")
        cursor.execute(query, (int(account_id),))
        existing_match_ids = [row[0] for row in cursor.fetchall()]
        logging.info(f"Found {len(existing_match_ids):,} existing account matches for {account_id} in OpenDota.Account_Matches.")
        
        for api_url in api_urls:
            logging.info(f"URL: {api_url}")

            # Step 1: Hit the network API endpoint
            response = requests.get(api_url, timeout=15)
            logging.info(f"Response: {response.status_code} - {response.reason}")
#            time.sleep(120) if response.status_code == 429 else time.sleep(0)  # Space out calls if successful to stay clear of rate limits
            response.raise_for_status()
            matches = response.json()
            logging.info(f"Retrieved {len(matches):,} matches from {api_url}.")

            # Step 2: Execute Database INSERT Transaction Loop
            insert_match_sql = """
                INSERT INTO OpenDota.Account_Matches (match_id, account_id, player_slot, radiant_win, duration, game_mode, 
                        lobby_type, hero_id, hero_variant, start_time, version, kills, deaths, 
                        assists, skill, average_rank, leaver_status, party_size,
                        xp_per_min, gold_per_min, hero_damage, tower_damage, hero_healing, last_hits, lane, lane_role, is_roaming, cluster)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """
            insert_count = 0
            
            for m in matches:
                match_id = m.get('match_id')
                if not match_id or match_id in existing_match_ids:
                    continue
                                
                core_params = (
                    int(match_id), int(account_id), m.get('player_slot'), m.get('radiant_win'), m.get('duration'), m.get('game_mode'),
                    m.get('lobby_type'), m.get('hero_id'), m.get('hero_variant'), m.get('start_time'), m.get('version'), m.get('kills'),
                    m.get('deaths'), m.get('assists'), m.get('skill'), m.get('average_rank'), m.get('leaver_status'), m.get('party_size'),
                    m.get('xp_per_min'), m.get('gold_per_min'), m.get('hero_damage'), m.get('tower_damage'), m.get('hero_healing'),
                    m.get('last_hits'), m.get('lane'), m.get('lane_role'),m.get('is_roaming'), m.get('cluster')
                )
                
                cursor.execute(insert_match_sql, core_params)
                existing_match_ids.append(match_id)  # Append to existing list to prevent duplicates within the same run
                insert_count += 1
                
        conn.commit()
        logging.info(f"Inserted {insert_count} new matches for {api_url} into OpenDota.Account_Matches.")
        return 

    except Exception as e:
        logging.error(f"{api_url} processing failed: {e}")
        logging.error(f"Query: {insert_match_sql}") if insert_match_sql else None
        logging.error(f"Match ID: {int(match_id)}") if match_id else None
        logging.error(f"Parameters: {core_params}") if core_params else None
        logging.error("Traceback details:", exc_info=True) if TRACEBACK else None
        conn.rollback()
        return 
    finally:
        cursor.close()

def sync_stratz_match_details(account_id, conn):
    """
    Queries the STRATZ GraphQL API to extract match history details and individual
    player performance telemetry matrices, populating Stratz.Match_Details and 
    Stratz.Match_Player_Performances within a single try block.
    """
    logging.info(f"Function: {sys._getframe().f_code.co_name}")
    logging.info(f"Account ID: {account_id}")

    # Assume the respective player performance records already exist in Stratz.Match_Player_Performances
    query = """
        SELECT md.match_id
        FROM Stratz.Match_Details md
        ORDER BY md.match_id
    """
    logging.info(f"Checking for existing matches.")
    cursor = conn.cursor()    
    cursor.execute(query, (int(account_id),))
    existing_match_ids = [row[0] for row in cursor.fetchall()]
    logging.info(f"Found {len(existing_match_ids):,} existing matches in Stratz.Match_Details.")

    stratz_token = os.getenv("STRATZ_TOKEN")
    if not stratz_token:
        logging.warning(f"STRATZ_TOKEN missing from environment configurations. Skipping STRATZ sync.")
        return 

    max_batch_skip = int(os.getenv("STRATZ_MAX_MATCH_BATCH_SKIP", 5))
    logging.info(f"STRATZ_MAX_MATCH_BATCH_SKIP set to {max_batch_skip}.")
    batch_skip_count = 0

    # EXACT EXPLICIT URL: No variations, no version numbers
    api_url = "https://api.stratz.com/graphql"
    headers = {
        "Authorization": f"Bearer {stratz_token}",
        "Content-Type": "application/json"
    }

    insert_match_sql = """
        INSERT INTO Stratz.Match_Details (match_id, did_radiant_win, duration_seconds, start_date_time, end_date_time, tower_status_radiant, 
                tower_status_dire, barracks_status_radiant, barracks_status_dire, cluster_id, first_blood_time, 
                lobby_type, num_human_players, game_mode, is_stats, tournament_id, tournament_round, actual_rank, 
                average_rank, average_imp, game_version_id, region_id, sequence_num, player_rank, bracket, 
                analysis_outcome, predicted_outcome_weight, bottom_lane_outcome, mid_lane_outcome, top_lane_outcome)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """

    insert_player_sql = """
        INSERT INTO Stratz.Match_Player_Performances(match_id, player_slot, steam_account_id, is_radiant, is_victory, hero_id, game_version_id, 
                kills, deaths, assists, leaver_status, num_last_hits, num_denies, gold_per_minute, networth, 
                experience_per_minute, level, gold, gold_spent, hero_damage, tower_damage, hero_healing, party_id, 
                is_random, lane, position, streak_prediction, intentional_feeding, role, role_basic, imp, award, 
                behavior, invisible_seconds, dota_plus_hero_xp, variant)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """

    skip = 0
    take = 100
    total_skipped = 0
    total_inserted = 0
    keep_fetching = True

    try:
        while keep_fetching:
            batch_skipped = 0
            batch_inserted = 0
            logging.info(f"skip: {skip}, take: {take} for account {account_id}.")

            graphql_query = """
                query GetPlayerMatchDetails {
                    player(steamAccountId: %d) {
                        matches(request: { skip: %d, take: %d }) {
                            id didRadiantWin durationSeconds startDateTime endDateTime
                            towerStatusRadiant towerStatusDire barracksStatusRadiant barracksStatusDire
                            clusterId firstBloodTime lobbyType numHumanPlayers gameMode isStats
                            tournamentId tournamentRound actualRank averageRank averageImp
                            gameVersionId regionId sequenceNum rank bracket analysisOutcome
                            predictedOutcomeWeight bottomLaneOutcome midLaneOutcome topLaneOutcome
                            players {
                                matchId playerSlot steamAccountId isRadiant isVictory heroId
                                gameVersionId kills deaths assists leaverStatus numLastHits numDenies
                                goldPerMinute networth experiencePerMinute level gold goldSpent
                                heroDamage towerDamage heroHealing partyId isRandom lane position
                                streakPrediction intentionalFeeding role roleBasic imp award
                                behavior invisibleSeconds dotaPlusHeroXp variant
                            }
                        }
                    }
                }
            """ % (int(account_id), skip, take)

            cursor = conn.cursor()

            response = requests.post(api_url, json={"query": graphql_query}, headers=headers, timeout=25)
            logging.info(f"Response: {response.status_code} - {response.reason}")
            response.raise_for_status()
            res_data = response.json()

            if "errors" in res_data:
                logging.error(f"STRATZ GraphQL returned query validation errors for {account_id}: {res_data['errors']}")
                logging.error(f"Query: {graphql_query}") if graphql_query else None
                logging.error("Traceback details:", exc_info=True) if TRACEBACK else None
                return 

            match_list = res_data.get("data", {}).get("player", {}).get("matches", []) or []
            logging.info(f"Looking through {len(match_list):,} matches.")

            if not match_list:
                logging.info(f"No match details records returned from STRATZ for ID: {account_id}")
                keep_fetching = False
                break

            for m in match_list:
                match_id = m.get("id")
                if not match_id or match_id in existing_match_ids:
                    batch_skipped += 1
                    total_skipped += 1
                    continue

                match_params = (
                    match_id,
                    m.get("didRadiantWin"), m.get("durationSeconds"), m.get("startDateTime"), m.get("endDateTime"),
                    m.get("towerStatusRadiant"), m.get("towerStatusDire"), m.get("barracksStatusRadiant"), m.get("barracksStatusDire"),
                    m.get("clusterId"), m.get("firstBloodTime"), m.get("lobbyType"), m.get("numHumanPlayers"), m.get("gameMode"),
                    m.get("isStats"), m.get("tournamentId"), m.get("tournamentRound"), m.get("actualRank"), m.get("averageRank"),
                    m.get("averageImp"), m.get("gameVersionId"), m.get("regionId"), m.get("sequenceNum"), m.get("rank"),
                    m.get("bracket"), m.get("analysisOutcome"), m.get("predictedOutcomeWeight"), m.get("bottomLaneOutcome"),
                    m.get("midLaneOutcome"), m.get("topLaneOutcome")
                )

#                logging.info(f"Inserting match {match_id} into Stratz.Match_Details.")
                cursor.execute(insert_match_sql, match_params)
                batch_inserted += 1
                total_inserted += 1

                for p in m.get("players", []) or []:
                    slot = p.get("playerSlot")
                    if slot is None:
                        continue

                    player_params = (
                        match_id, slot,
                        p.get("steamAccountId"), p.get("isRadiant"), p.get("isVictory"),
                        p.get("heroId"), p.get("gameVersionId"), p.get("kills"), p.get('deaths'), p.get("assists"),
                        p.get("leaverStatus"), p.get("numLastHits"), p.get("numDenies"), p.get("goldPerMinute"),
                        p.get("networth"), p.get("experiencePerMinute"), p.get("level"), p.get("gold"), p.get("goldSpent"),
                        p.get("heroDamage"), p.get("towerDamage"), p.get("heroHealing"), p.get("partyId"),
                        p.get("isRandom"), p.get("lane"), p.get("position"), p.get("streakPrediction"),
                        p.get("intentionalFeeding"), p.get("role"), p.get("roleBasic"), p.get("imp"),
                        p.get("award"), p.get("behavior"), p.get("invisibleSeconds"), p.get("dotaPlusHeroXp"), p.get("variant")
                    )
                    cursor.execute(insert_player_sql, player_params)

            conn.commit()
            logging.info(f"Inserted {batch_inserted} new matches from batch.")
            logging.info(f"Skipped {batch_skipped} existing matches from batch.")

            # If we skipped the entire batch, increment the batch skip counter. If we inserted any matches, reset the batch skip counter.
            # Exit the loop if STRATZ_MAX_MATCH_BATCH_SKIP threshold is reached 5 times in a row, which means we've likely have all of 
            # the latest matches.
            if batch_skipped == take:
                batch_skip_count += 1
                if batch_skip_count > max_batch_skip:
                    logging.info(f"STRATZ_MAX_MATCH_BATCH_SKIP reached for account {account_id}, moving on.")
                    keep_fetching = False
                else:
                    logging.info(f"Batch skip count increased to {batch_skip_count} for account {account_id}.")
            else:
                batch_skip_count = 0

            # If the response returned less than the requested amount, we have reached the end of their history
            if len(match_list) < take:
                keep_fetching = False
            else:
                skip += take  # Shift pagination window forward
            time.sleep(1.1)

        logging.info(f"Inserted {total_inserted} total matches for account {account_id} into Stratz.Match_Details and Stratz.Match_Player_Performances.")
        logging.info(f"Skipped {total_skipped} total matches for account {account_id}.")
        return            

    except Exception as e:
        logging.error(f"STRATZ {account_id} match data processing failed: {e}")
        logging.error(f"Insert Match SQL: {insert_match_sql}") if insert_match_sql else None
        logging.error(f"Insert Match Parameters: {match_params}") if match_params else None
        logging.error(f"Match Player Performance SQL: {insert_player_sql}") if insert_player_sql else None
        logging.error(f"Match Player Performance Parameters: {player_params}") if player_params else None
        logging.error("Traceback details:", exc_info=True) if TRACEBACK else None
        keep_fetching = False
        conn.rollback()
        return 
    finally:
        cursor.close()

def sync_opendota_match_ids(conn):
    """
    Queries the database to find distinct match_ids that exist in the Player_Matches 
    table but have not yet been processed into the deep Match_Details table.
    """
    logging.info(f"Function: {sys._getframe().f_code.co_name}")
    
    cursor = conn.cursor()
    try:
        # Optimized lookup using a LEFT JOIN to find missing records
        query = """
            SELECT am.match_id
            FROM OpenDota.Account_Matches am
            WHERE NOT EXISTS (
                SELECT 1
                FROM OpenDota.Match_Details md
                WHERE md.match_id = am.match_id
            )
            AND am.match_id NOT IN (SELECT match_id FROM OpenDota.Ignored_Matches)
            UNION
            SELECT smd.match_id
            FROM Stratz.Match_Details smd
            WHERE NOT EXISTS (
                SELECT 1
                FROM OpenDota.Match_Details omd
                WHERE omd.match_id = smd.match_id
            )
            AND smd.match_id NOT IN (SELECT match_id FROM OpenDota.Ignored_Matches)
            ORDER BY am.match_id
        """
        
        logging.info(f"Checking for matches to sync.")
        cursor.execute(query)
        # Flatten the row tuples into a clean, list array of raw match IDs
        match_ids = [row[0] for row in cursor.fetchall()]
        return match_ids

    except Exception as e:
        logging.error(f"Checking for matches to sync failed: {e}")
        logging.error(f"Query: {query}") if query else None
        logging.error("Traceback details:", exc_info=True) if TRACEBACK else None
        return []
    finally:
        cursor.close()

def sync_opendota_match_details(match_id, conn, vpn_location_index):
    """
    Fetches comprehensive match telemetry from the correct OpenDota API path
    and updates both Match_Details and Match_Player_Performances within a single try block.
    """
    logging.info(f"Function: {sys._getframe().f_code.co_name}")
    logging.info(f"Match ID: {match_id}")

    # FIXED: Verified exact functional endpoint path
    api_url = f"https://api.opendota.com/api/matches/{match_id}"
    logging.info(f"URL: {api_url}")
    
    cursor = conn.cursor()

    # Step 1: Hit the network API endpoint
    max_retries = int(os.getenv("MAX_RETRIES", 3))
    retry_delay = int(os.getenv("RETRY_DELAY_SECONDS", 60))
    retry_count = 0

    while retry_count <= max_retries:
        try:
            response = requests.get(api_url, timeout=15)
            logging.info(f"Response: {response.status_code} - {response.reason}")

            if response.status_code == 404:
                logging.warning(f"Ignoring Match ID: {match_id}, inserting into OpenDota.Ignored_Matches.")
                cursor.execute("" \
                    "INSERT INTO OpenDota.Ignored_Matches (match_id, reason)" \
                    "VALUES (?, ?)", (match_id, f"Response: {response.status_code} - {response.reason}"))
                conn.commit()
                cursor.close()
                return True, vpn_location_index

            if response.status_code == 429:
                logging.warning(f"Rate limit hit for {api_url}.")

# Need VPN_PATH, VPN_LOCATIONS, vpn_location_index, VPN_ENABLED, VPN_LOCATION_START_INDEX


                if VPN_ENABLED:
                    first_attempt = True
                    vpn_result = subprocess.run([VPN_PATH, "disconnect", VPN_LOCATIONS[vpn_location_index]], capture_output=True, text=True, check=True)
                    logging.info(f"VPN disconnected from '{VPN_LOCATIONS[vpn_location_index]}'.")
                    vpn_location_index = (vpn_location_index + 1) % len(VPN_LOCATIONS)

                    while first_attempt or vpn_location_index != VPN_LOCATION_START_INDEX:
                        first_attempt = False
                        logging.info(f"Attempting to connect to '{VPN_LOCATIONS[vpn_location_index]}'...")
                        vpn_result = subprocess.run([VPN_PATH, "connect", VPN_LOCATIONS[vpn_location_index]], capture_output=True, text=True, check=True)
                        if vpn_result.returncode == 0:
                            logging.info(f"...connected!")
                            time.sleep(5)  # Wait for DNS and network adapter to fully stabilize
                            logging.info(f"Updating VPN_LOCATION_START_INDEX value to {vpn_location_index}.")
                            set_key(find_dotenv(), "VPN_LOCATION_START_INDEX", int(vpn_location_index), quote_mode="never")
                            break
                        else:
                            logging.error(f"Failed to connect to '{VPN_LOCATIONS[vpn_location_index]}'.")
                            vpn_location_index = (vpn_location_index + 1) % len(VPN_LOCATIONS)



            m = response.json()
            break  # Exit the retry loop if the request was successful

        except Exception as e:
            logging.error(f"{api_url} processing failed: {e}")
            logging.error("Traceback details:", exc_info=True) if TRACEBACK else None

            retry_count += 1
            if retry_count > max_retries:
                logging.error(f"Max retries reached for {api_url}. Status code: {response.status_code}")
                cursor.close()
                return False, vpn_location_index
            else:
                logging.warning(f"Will retry after {retry_delay} seconds, attempt {retry_count} of {max_retries}...")
                time.sleep(int(retry_delay))
                retry_delay = retry_delay * 2  # Exponential backoff
                continue  # Retry the request

    try:
        # Step 2: Ingest Match Header Summary Metrics (OpenDota.Match_Details)
        insert_match_sql = """
            INSERT INTO OpenDota.Match_Details (
                match_id, barracks_status_dire, barracks_status_radiant, cluster, dire_score, duration, engine, first_blood_time, 
                game_mode, human_players, leagueid, lobby_type, match_seq_num, negative_votes, positive_votes, radiant_score, radiant_win, 
                skill, start_time, tower_status_dire, tower_status_radiant, version, replay_salt, series_id, series_type, patch, region,
                throw, comeback, loss, win, replay_url
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        insert_match_params = (
            match_id, m.get('barracks_status_dire'), m.get('barracks_status_radiant'), m.get('cluster'), 
            m.get('dire_score'), m.get('duration'), m.get('engine'), m.get('first_blood_time'), 
            m.get('game_mode'), m.get('human_players'), m.get('leagueid'), m.get('lobby_type'), m.get('match_seq_num'), 
            m.get('negative_votes'), m.get('positive_votes'), m.get('radiant_score'), 
            m.get('radiant_win'), m.get('skill'), m.get('start_time'), m.get('tower_status_dire'), 
            m.get('tower_status_radiant'), m.get('version'), m.get('replay_salt'), m.get('series_id'), m.get('series_type'), 
            m.get('patch'), m.get('region'),
            m.get('throw'), m.get('comeback'), m.get('loss'), m.get('win'), m.get('replay_url')
        )
        cursor.execute(insert_match_sql, insert_match_params)

    except Exception as e:
        logging.error(f"{api_url} processing failed: {e}")
        logging.error(f"Insert Match SQL: {insert_match_sql}") if insert_match_sql else None
        logging.error(f"Insert Match Parameters: {insert_match_params}") if insert_match_params else None
        logging.error("Traceback details:", exc_info=True) if TRACEBACK else None
        conn.rollback()
        return False, vpn_location_index

    try:
        # Step 3: Ingest All 10 Participants Metrics (OpenDota.Match_Player_Performances)
        insert_player_perf_sql = """
            INSERT INTO OpenDota.Match_Player_Performances (
                match_id, player_slot, account_id, kills, deaths, assists, leaver_status, aghanims_scepter, aghanims_shard, 
                moonshard, personaname, name, rank_tier, computed_mmr, is_subscriber, lobby_type, is_contributor, radiant_win, 
                kills_per_minute, abandons, gold, gold_per_min, gold_spent, net_worth, total_gold, xp_per_min, total_xp, level, 
                hero_id, hero_variant, hero_damage, hero_healing, tower_damage, last_hits, denies, kda, teamfight_participation, 
                stuns, win, lose
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """
        for p in m.get('players', []):
            slot = p.get('player_slot')
            if slot is None: 
                continue
                
            insert_player_perf_params = (
                match_id, slot, p.get('account_id'), p.get('kills'), p.get('deaths'), p.get('assists'), 
                p.get('leaver_status'), p.get('aghanims_scepter'), p.get('aghanims_shard'), 
                p.get('moonshard'), p.get('personaname'), p.get('name'), p.get('rank_tier'), 
                p.get('computed_mmr'), p.get('is_subscriber'), p.get('lobby_type'), p.get('is_contributor'), 
                p.get('radiant_win'), p.get('kills_per_minute'), p.get('abandons'), 
                p.get('gold'), p.get('gold_per_min'), p.get('gold_spent'), p.get('net_worth'), 
                p.get('total_gold'), p.get('xp_per_min'), p.get('total_xp'), p.get('level'), 
                p.get('hero_id'), p.get('hero_variant'), p.get('hero_damage'), p.get('hero_healing'), 
                p.get('tower_damage'), p.get('last_hits'), p.get('denies'), p.get('kda'), 
                p.get('teamfight_participation'), p.get('stuns'), 
                p.get('win'), p.get('lose')
            )
            cursor.execute(insert_player_perf_sql, insert_player_perf_params)
            cursor.commit() 

        logging.info(f"Inserted {api_url} into OpenDota.Match_Details and OpenDota.Match_Player_Performances.")
        conn.commit()
        return True, vpn_location_index

    except Exception as e:
        logging.error(f"{api_url} processing failed: {e}")
        logging.error(f"Match Player Performance SQL: {insert_player_perf_sql}") if insert_player_perf_sql else None
        logging.error(f"Match Player Performance Parameters: {insert_player_perf_params}") if insert_player_perf_params else None
        logging.error("Traceback details:", exc_info=True) if TRACEBACK else None
        conn.rollback()
        return False, vpn_location_index
    finally:
        cursor.close()

# 5. This is how the connection and cursor are physically created in your main execution loop:
def main():
    logging.info(f"Function: {sys._getframe().f_code.co_name}")
    
    if not ACCOUNT_IDS:
        logging.warning(f"{sys._getframe().f_code.co_name}: No account IDs identified.")
#        return

    account_list = [aid.strip() for aid in ACCOUNT_IDS.split(",") if aid.strip()]
    logging.info(f"Account list: {account_list}.")
    
    conn = None
    try:
        logging.info(f"Opening database connection to SQL Server.")
        
        # Open the connection using mssql_python
        conn = mssql_python.connect(CONN_STR)

        # Get OpenDota accounts to ignore
        cursor = conn.cursor()
        cursor.execute("SELECT account_id FROM OpenDota.Ignored_Accounts")
        opendota_ignored_accounts = {row[0] for row in cursor.fetchall()}
        logging.info(f"OpenDota ignored accounts: {opendota_ignored_accounts}.")

        # PHASE 1: Collect profiles, aliases, and historical stubs across all players
        for account_id in account_list:
            logging.info(f"Working on account {account_id}.")
            if int(account_id) in opendota_ignored_accounts:
                logging.warning(f"Account {account_id} is in OpenDota.Ignored_Accounts, skipping OpenDota account processing.")
            else:
                sync_opendota_account_profile(account_id, conn) if SOAP == True else logging.warning(f"Skipping OpenDota account profile sync for {account_id} as per configuration.")
                sync_opendota_account_matches(account_id, conn) if SOAM == True else logging.warning(f"Skipping OpenDota account matches sync for {account_id} as per configuration.")
            sync_stratz_account_profile(account_id, conn) if SSAP == True else logging.warning(f"Skipping Stratz account profile sync for {account_id} as per configuration.")
            sync_stratz_match_details(account_id, conn) if SSMD == True else logging.warning(f"Skipping Stratz match details sync for {account_id} as per configuration.")

        # PHASE 2: Automatically discover missing matches from the combined pool
        # Since Stratz appears to have more matches tied to an account, use both OpenDota and Stratz as a source
        # to get match details from OpenDota 
        if SOMI:
            # PHASE 3: Deep crawl match detail data layers
            matches_to_sync = sync_opendota_match_ids(conn)
            if matches_to_sync:
                num_matches = len(matches_to_sync)
                match_progress_update = int(num_matches * (int(os.getenv("MATCH_PROGRESS_THRESHOLD_PCT", 10)) / 100))
                next_update = match_progress_update
                logging.info(f"{sys._getframe().f_code.co_name}: Found {num_matches:,} matches to sync into OpenDota.Match_Details. Starting crawlers.")

                if VPN_ENABLED:
                    first_attempt = True
                    vpn_location_index = VPN_LOCATION_START_INDEX
                    logging.info(f"VPN_ENABLED = {VPN_ENABLED}, attempting to connect to '{VPN_LOCATIONS[vpn_location_index]}'...")
                    vpn_result = subprocess.run([VPN_PATH, "connect", VPN_LOCATIONS[vpn_location_index]], capture_output=True, text=True, check=True)

                    while first_attempt or vpn_location_index != VPN_LOCATION_START_INDEX:
                        first_attempt = False
                        logging.info(f"Attempting to connect to '{VPN_LOCATIONS[vpn_location_index]}'...")
                        vpn_result = subprocess.run([VPN_PATH, "connect", VPN_LOCATIONS[vpn_location_index]], capture_output=True, text=True, check=True)
                        if vpn_result.returncode == 0:
                            logging.info(f"...connected!")
                            time.sleep(5)  # Wait for DNS and network adapter to fully stabilize
                            logging.info(f"Updating VPN_LOCATION_START_INDEX value to {vpn_location_index}.")
                            set_key(find_dotenv(), "VPN_LOCATION_START_INDEX", str(vpn_location_index), quote_mode="never")
                            break
                        else:
                            logging.error(f"Failed to connect to '{VPN_LOCATIONS[vpn_location_index]}'.")
                            vpn_location_index = (vpn_location_index + 1) % len(VPN_LOCATIONS)

                for index, match_id in enumerate(matches_to_sync):
                    # Extract integer match_id safely from the row item query result
                    success, vpn_location_index = sync_opendota_match_details(match_id, conn, vpn_location_index)
                    if success:
                        time.sleep(1.5)  # Space calls out to stay well clear of standard public api tier blocking rules
                    else:
                        break  # If a single match detail crawl fails, break the loop to avoid cascading failures and hitting rate limits
                    if index == next_update:
                        logging.info(f"{index / num_matches * 100:.2f}% complete, processed {index:,} of {num_matches:,} matches into OpenDota.Match_Details.")
                        next_update += match_progress_update
            else:
                logging.info(f"{sys._getframe().f_code.co_name}: OpenDota.Match_Details is in sync.") if SOMI == True else None
        else:
            logging.warning(f"Skipping OpenDota match ID sync for {account_id} as per configuration.")
                        
    except Exception as e:
        logging.critical(f"{sys._getframe().f_code.co_name}: Master pipeline control routine collapsed: {e}")
        logging.error("Traceback details:", exc_info=True) if TRACEBACK else None
    finally:
        if conn:
            conn.close()
            logging.info("Database connection safely closed.")
        if 'vpn_location_index' in locals():
            vpn_result = subprocess.run([VPN_PATH, "disconnect", VPN_LOCATIONS[vpn_location_index]], capture_output=True, text=True, check=True)
            logging.info(f"VPN disconnected from '{VPN_LOCATIONS[vpn_location_index]}'.")

if __name__ == "__main__":
    main()
