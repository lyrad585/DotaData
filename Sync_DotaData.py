# In OpenDota.Account_Matches and Stratz.Account_Matchese, barracks_status_dire values are not the same between OpenDota and Stratz.
# Alias entries between OpenDota and Stratz appear to be tracked differently but accurate for the most part.

import os
import sys
import logging
from urllib import response
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

DB_SERVER = os.getenv("DB_SERVER")
DB_DATABASE = os.getenv("DB_DATABASE")
ACCOUNT_IDS = os.getenv("ACCOUNT_IDS", "")
soap = os.getenv("sync_opendota_account_profile")
ssap = os.getenv("sync_stratz_account_profile")
soam = os.getenv("sync_opendota_account_matches")
ssmd = os.getenv("sync_stratz_match_details")
somi = os.getenv("sync_opendota_match_ids")
traceback = os.getenv("traceback")

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

        player_merge_sql = """
            MERGE OpenDota.Accounts AS target
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
        logging.error(f"Merge SQL: {player_merge_sql}")
        logging.error(f"Merge Parameters: {params}")
        logging.error(f"Insert SQL: {insert_sql}")
        logging.error(f"Insert Parameters: {int(account_id)}, {str(alias_name)}, {name_since}, {int(account_id)}, {name_since}")
        logging.error("Traceback details:", exc_info=True) if traceback else None
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

    cursor = conn.cursor()
    try:
        response = requests.post(api_url, json={"query": graphql_query}, headers=headers, timeout=15)
        logging.info(f"Response: {response.status_code} - {response.reason}")
        response.raise_for_status()
        res_data = response.json()

        if "errors" in res_data:
            logging.error(f"STRATZ GraphQL returned query validation errors for {account_id}: {res_data['errors']}")
            logging.error(f"Query: {graphql_query}")
            logging.error("Traceback details:", exc_info=True) if traceback else None
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
        logging.error(f"Merge SQL: {player_merge_sql}")
        logging.error(f"Merge Parameters: {core_params}")
        logging.error(f"Insert SQL: {insert_alias_sql}")
        logging.error(f"Insert Values: {int(account_id)}, str{alias_name}, {n.get('lastSeenDateTime')}")
        logging.error("Traceback details:", exc_info=True) if traceback else None
        conn.rollback()
        return 
    finally:
        cursor.close()

def sync_opendota_account_matches(account_id, conn):
    """
    Fetches historical match list stubs from the correct OpenDota API path
    and upserts the data into OpenDota.Account_Matches using a single try block.
    """
    logging.info(f"Function: {sys._getframe().f_code.co_name}")
    logging.info(f"Account ID: {account_id}")

    # VERIFIED CORRECT URL: Strictly using the /api/players/ route
    api_url = f"https://api.opendota.com/api/players/{account_id}/matches"
    logging.info(f"URL: {api_url}")

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
        logging.info(f"Found {len(existing_match_ids)} existing account matches for {account_id} in OpenDota.Account_Matches.")

        # Step 1: Hit the network API endpoint
        response = requests.get(api_url, timeout=15)
        logging.info(f"Response: {response.status_code} - {response.reason}")
        response.raise_for_status()
        matches = response.json()
        logging.info(f"Retrieved {len(matches)} matches from {api_url}.")

        # Step 2: Execute Database INSERT Transaction Loop
        insert_match_sql = """
            INSERT INTO OpenDota.Account_Matches (match_id, account_id, player_slot, radiant_win, duration, game_mode, 
                    lobby_type, hero_id, hero_variant, start_time, version, kills, deaths, 
                    assists, skill, average_rank, leaver_status, party_size)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """
        insert_count = 0
        
        for m in matches:
            match_id = m.get('match_id')
            if not match_id or match_id in existing_match_ids:
                continue
                
            radiant_win_bit = 1 if m.get('radiant_win') else 0
            
            core_params = (
                int(match_id),
                int(account_id),
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
            
            cursor.execute(insert_match_sql, core_params)
            insert_count += 1
            
        conn.commit()
        logging.info(f"Inserted {insert_count} new matches for {api_url} into OpenDota.Account_Matches.")
        return 

    except Exception as e:
        logging.error(f"{api_url} processing failed: {e}")
        logging.error(f"Query: {insert_match_sql}")
        logging.error(f"Match ID: {int(match_id)}")
        logging.error(f"Core Parameters: {core_params}")
        logging.error("Traceback details:", exc_info=True) if traceback else None
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
    logging.info(f"Found {len(existing_match_ids)} existing account matches for {account_id} in Stratz.Match_Details.")

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
                logging.error(f"Query: {graphql_query}")
                logging.error("Traceback details:", exc_info=True) if traceback else None
                return 

            match_list = res_data.get("data", {}).get("player", {}).get("matches", []) or []
            logging.info(f"Looking through {len(match_list)} matches.")

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
                    1 if m.get("didRadiantWin") else 0, m.get("durationSeconds"), m.get("startDateTime"), m.get("endDateTime"),
                    m.get("towerStatusRadiant"), m.get("towerStatusDire"), m.get("barracksStatusRadiant"), m.get("barracksStatusDire"),
                    m.get("clusterId"), m.get("firstBloodTime"), m.get("lobbyType"), m.get("numHumanPlayers"), m.get("gameMode"),
                    1 if m.get("isStats") else 0, m.get("tournamentId"), m.get("tournamentRound"), m.get("actualRank"), m.get("averageRank"),
                    m.get("averageImp"), m.get("gameVersionId"), m.get("regionId"), m.get("sequenceNum"), m.get("rank"),
                    m.get("bracket"), m.get("analysisOutcome"), m.get("predictedOutcomeWeight"), m.get("bottomLaneOutcome"),
                    m.get("midLaneOutcome"), m.get("topLaneOutcome")
                )

                logging.info(f"Inserting match {match_id} into Stratz.Match_Details.")
                cursor.execute(insert_match_sql, match_params)
                batch_inserted += 1
                total_inserted += 1

                for p in m.get("players", []) or []:
                    slot = p.get("playerSlot")
                    if slot is None:
                        continue

                    player_params = (
                        match_id, slot,
                        p.get("steamAccountId"), 1 if p.get("isRadiant") else 0, 1 if p.get("isVictory") else 0,
                        p.get("heroId"), p.get("gameVersionId"), p.get("kills"), p.get('deaths'), p.get("assists"),
                        p.get("leaverStatus"), p.get("numLastHits"), p.get("numDenies"), p.get("goldPerMinute"),
                        p.get("networth"), p.get("experiencePerMinute"), p.get("level"), p.get("gold"), p.get("goldSpent"),
                        p.get("heroDamage"), p.get("towerDamage"), p.get("heroHealing"), p.get("partyId"),
                        1 if p.get("isRandom") else 0, p.get("lane"), p.get("position"), p.get("streakPrediction"),
                        1 if p.get("intentionalFeeding") else 0, p.get("role"), p.get("roleBasic"), p.get("imp"),
                        p.get("award"), p.get("behavior"), p.get("invisibleSeconds"), p.get("dotaPlusHeroXp"), p.get("variant")
                    )
                    cursor.execute(insert_player_sql, player_params)

            conn.commit()
            logging.info(f"Inserted {batch_inserted} new matches from batch.")
            logging.info(f"Skipped {batch_skipped} existing matches from batch.")

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
        logging.error("Traceback details:", exc_info=True) if traceback else None
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
            UNION
            SELECT smd.match_id
            FROM Stratz.Match_Details smd
            WHERE NOT EXISTS (
                SELECT 1
                FROM OpenDota.Match_Details omd
                WHERE omd.match_id = smd.match_id
            )
            ORDER BY am.match_id
        """
        
        logging.info(f"Checking for matches to sync.")
        cursor.execute(query)
        # Flatten the row tuples into a clean, list array of raw match IDs
        match_ids = [row[0] for row in cursor.fetchall()]
        logging.info(f"Found {len(match_ids)} existing matches between OpenDota.Account_Matches and Stratz.Match_Details.")
        return match_ids

    except Exception as e:
        logging.error(f"Checking for matches to sync failed: {e}")
        logging.error(f"Query: {query}")
        logging.error("Traceback details:", exc_info=True) if traceback else None
        return []
    finally:
        cursor.close()

def sync_opendota_match_details(match_id, conn):
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
    try:
        # Step 1: Hit the network API endpoint
        response = requests.get(api_url, timeout=15)
        logging.info(f"Response: {response.status_code} - {response.reason}")
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
        logging.info(f"Inserting {api_url} into OpenDota.Match_Details and OpenDota.Match_Player_Performances.")
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
        return 

    except Exception as e:
        logging.error(f"{api_url} processing failed: {e}")
        logging.error(f"Insert Match SQL: {header_sql}") if header_sql else None
        logging.error(f"Insert Match Parameters: {h_params}") if h_params else None
        logging.error(f"Match Player Performance SQL: {player_sql}") if player_sql else None
        logging.error(f"Match Player Performance Parameters: {p_params}") if p_params else None
        logging.error("Traceback details:", exc_info=True) if traceback else None
        conn.rollback()
        return 
    finally:
        cursor.close()

# 5. This is how the connection and cursor are physically created in your main execution loop:
def main():
    logging.info(f"Function: {sys._getframe().f_code.co_name}")
    
    if not ACCOUNT_IDS:
        logging.warning(f"{sys._getframe().f_code.co_name}: No account IDs identified.")
        return

    account_list = [aid.strip() for aid in ACCOUNT_IDS.split(",") if aid.strip()]
    logging.info(f"Account list: {account_list}.")
    
    conn = None
    try:
        logging.info(f"Opening database connection to SQL Server.")
        logging.info(f"Opening database connection to SQL Server.")
        logging.info(f"sync_opendota_account_profile: {soap}")
        logging.info(f"sync_stratz_account_profile: {ssap}")
        logging.info(f"sync_opendota_account_matches: {soam}")
        logging.info(f"sync_stratz_match_details: {ssmd}")
        logging.info(f"sync_opendota_match_ids: {somi}")
        logging.info(f"traceback: {traceback}")
        logging.info(f"Opening database connection to SQL Server.")
        logging.info(f"Opening database connection to SQL Server.")
        
        # Open the connection using mssql_python
        conn = mssql_python.connect(CONN_STR)
        
        # PHASE 1: Collect profiles, aliases, and historical stubs across all players
        for account_id in account_list:
            logging.info(f"Working on account {account_id} from list {account_list}.")
            sync_opendota_account_profile(account_id, conn) if soap == True else logging.info(f"Skipping OpenDota account profile sync for {account_id} as per configuration.")
            sync_stratz_account_profile(account_id, conn) if ssap == True else logging.info(f"Skipping Stratz account profile sync for {account_id} as per configuration.")
            sync_opendota_account_matches(account_id, conn) if soam == True else logging.info(f"Skipping OpenDota account matches sync for {account_id} as per configuration.")
            sync_stratz_match_details(account_id, conn) if ssmd == True else logging.info(f"Skipping Stratz match details sync for {account_id} as per configuration.")

        # PHASE 2: Automatically discover missing matches from the combined pool
        # Since Stratz appears to have more matches tied to an account, use both OpenDota and Stratz as a source
        # to get match details from OpenDota 
        matches_to_sync = sync_opendota_match_ids(conn) if somi == True else logging.info(f"Skipping OpenDota match ID sync for {account_id} as per configuration.")
        
        # PHASE 3: Deep crawl match detail data layers
        if matches_to_sync:
            logging.info(f"{sys._getframe().f_code.co_name}: Found {len(matches_to_sync)} matches to sync into OpenDota.Match_Details. Starting crawlers.")
            for match_row in matches_to_sync:
                # Extract integer match_id safely from the row item query result
                match_id = match_row
                sync_opendota_match_details(match_id, conn)
                time.sleep(1.4)  # Space calls out to stay well clear of standard public api tier blocking rules
        else:
            logging.info(f"{sys._getframe().f_code.co_name}: OpenDota.Match_Details is in sync.") if somi == True else None
                
    except Exception as e:
        logging.critical(f"{sys._getframe().f_code.co_name}: Master pipeline control routine collapsed: {e}")
        logging.error("Traceback details:", exc_info=True) if traceback else None
    finally:
        if conn:
            conn.close()
            logging.info("Database connection safely closed.")

if __name__ == "__main__":
    main()
