SOURCES_CONFIG = {
    "OpenDota" : {
        "sync" : True,
        "process_json" : True,
        "request" : "get",
        "sleep" : 1.3,
        "timeout" : 10,
        "vpn" : False,
        "cat" : {
            "accounts" : {
                "sync" : True,
                "process_json" : True,
                "process_json_merge" : (
                    "MERGE OpenDota.Accounts_JSON AS t "
                    "USING (SELECT ? AS account_id, ? AS account_json) AS s "
                    "ON (t.account_id = s.account_id) "
                    "WHEN MATCHED AND cast(t.account_json AS NVARCHAR(max)) <> s.account_json THEN "
                    "    UPDATE SET "
                    "        t.account_json = s.account_json, reprocess_tables = 1, last_updated_at = GETDATE() "
                    "WHEN NOT MATCHED THEN "
                    "    INSERT (account_id, account_json) "
                    "    VALUES (s.account_id, s.account_json) "
                    "; "
                ),
                "urls" : [
                    "https://api.opendota.com/api/players/{a_id}"
                ],
                "select" : (
                    "SELECT a.account_id "
                    "FROM OpenDota.Accounts a "
                    "WHERE a.ignore = 0 "
                ),
                "a_ids" : [],
                "record" : {
                    "merge" : (
                        "MERGE OpenDota.Accounts AS t "
                        "USING (SELECT ? AS account_id) AS s "
                        "ON (t.account_id = s.account_id) "
                        "WHEN MATCHED THEN "
                        "    UPDATE SET "
                        "        tracked_until = ?, solo_competitive_rank = ?, competitive_rank = ?, rank_tier = ?, leaderboard_rank = ?, "
                        "        computed_mmr = ?, computed_mmr_turbo = ?, personaname = ?, name = ?, plus_status = ?, "
                        "        cheese = ?, steamid = ?, avatar = ?, avatarmedium = ?, avatarfull = ?, "
                        "        profileurl = ?, last_login = ?, loccountrycode = ?, is_contributor = ?, is_subscriber = ?, "
                        "        last_updated_at = GETDATE() "
                        "WHEN NOT MATCHED THEN "
                        "    INSERT ( "
                        "        account_id, "
                        "        tracked_until, solo_competitive_rank, competitive_rank, rank_tier, leaderboard_rank, "
                        "        computed_mmr, computed_mmr_turbo, personaname, name, plus_status, "
                        "        cheese, steamid, avatar, avatarmedium, avatarfull, "
                        "        profileurl, last_login, loccountrycode, is_contributor, is_subscriber "
                        "    ) "
                        "    VALUES ( "
                        "        ?,  "
                        "        ?, ?, ?, ?, ?, "
                        "        ?, ?, ?, ?, ?, "
                        "        ?, ?, ?, ?, ?, "
                        "        ?, ?, ?, ?, ? "
                        "   ) "
                        "; "
                    ),
                    "params" : (
                        "data.get('profile').get('account_id'), "
                        "data.get('profile').get('tracked_until'), data.get('profile').get('solo_competitive_rank'), data.get('profile').get('competitive_rank'), data.get('rank_tier'), data.get('leaderboard_rank'), "
                        "data.get('computed_mmr'), data.get('computed_mmr_turbo'), data.get('profile').get('personaname'), data.get('profile').get('name'), data.get('profile').get('plus'), "
                        "data.get('profile').get('cheese'), data.get('profile').get('steamid'), data.get('profile').get('avatar'), data.get('profile').get('avatarmedium'), data.get('profile').get('avatarfull'), "
                        "data.get('profile').get('profileurl'), data.get('profile').get('last_login'), data.get('profile').get('loccountrycode'), data.get('profile').get('is_contributor'), data.get('profile').get('is_subscriber') "
                    ),
                    "aliases" : {
                        "list" : "data.get('aliases')",
                        "insert" : (
                            "IF NOT EXISTS ( "
                            "    SELECT 1 "
                            "    FROM OpenDota.Account_Aliases "
                            "    WHERE account_id = ? "
                            "    AND name_since = ? "
                            ") "
                            "INSERT INTO OpenDota.Account_Aliases (account_id, alias_name, name_since) "
                            "VALUES (?, ?, ?); "
                        ),
                        "params" : (
                            "data.get('profile').get('account_id'), "
                            "alias['name_since'], "
                            "data.get('profile').get('account_id'), alias['personaname'], alias['name_since'] "
                        )
                    }
                },
                "ignore" : {
                    "select" : (
                        "SELECT a.account_id "
                        "FROM OpenDota.Accounts a "
                        "WHERE a.ignore = 1 "
                    ),
                    "a_ids" : [],
                    "merge" : (
                        "MERGE OpenDota.Accounts AS t "
                        "USING (SELECT ? AS account_id) AS s "
                        "ON (t.account_id = s.account_id) "
                        "WHEN MATCHED THEN "
                        "   UPDATE SET "
                        "       ignore = 1, ignore_reason = ?, last_updated_at = GETDATE() "
                        "WHEN NOT MATCHED THEN "
                        "   INSERT (account_id, ignore, ignore_reason) VALUES (?, 1, ?) "
                        "; "
                    ),
                    "params" : "account_id, f'Response: {response.status_code} - {response.reason}'"
                },
            },
            "account_matches" : {
                "sync" : False,
                "process_json" : True,
                "process_json_merge" : (
                    "MERGE OpenDota.Account_Matches_JSON AS t "
                    "USING (SELECT ? AS account_id, ? AS account_matches_json) AS s "
                    "ON (t.account_id = s.account_id) "
                    "WHEN MATCHED AND cast(t.account_matches_json AS NVARCHAR(max)) <> s.account_matches_json THEN "
                    "    UPDATE SET "
                    "        t.account_matches_json = s.account_matches_json, reprocess_tables = 1, last_updated_at = GETDATE() "
                    "WHEN NOT MATCHED THEN "
                    "    INSERT (account_id, account_matches_json) "
                    "    VALUES (s.account_id, s.account_matches_json) "
                    "; "
                ),
                "urls" : [
                    "https://api.opendota.com/api/players/{a_id}/matches",
                    "https://api.opendota.com/api/players/{a_id}/recentmatches"
                ],
                "existing" : (
                    "SELECT am.match_id "
                    "FROM OpenDota.Account_Matches am "
                    "WHERE am.account_id = ? "
                    "ORDER BY am.match_id "
                ),
                "m_ids" : [],
                "record" : {
                    "details" : {
                        "insert" : (
                            "INSERT INTO OpenDota.Account_Matches ( "
                            "    match_id, account_id, player_slot, radiant_win, duration, "
                            "    game_mode, lobby_type, hero_id, hero_variant, start_time, "
                            "    version, kills, deaths, assists, skill, "
                            "    average_rank, leaver_status, party_size, xp_per_min, gold_per_min, "
                            "    hero_damage, tower_damage, hero_healing, last_hits, lane, "
                            "    lane_role, is_roaming, cluster "
                            ") "
                            "VALUES ( "
                            "    ?, ?, ?, ?, ?, "
                            "    ?, ?, ?, ?, ?, "
                            "    ?, ?, ?, ?, ?, "
                            "    ?, ?, ?, ?, ?, "
                            "    ?, ?, ?, ?, ?, "
                            "    ?, ?, ? "
                            "); "
                        ),
                        "params" : (
                            "int(match_id), int(account_id), m.get('player_slot'), m.get('radiant_win'), m.get('duration'), "
                            "m.get('game_mode'), m.get('lobby_type'), m.get('hero_id'), m.get('hero_variant'), m.get('start_time'), "
                            "m.get('version'), m.get('kills'), m.get('deaths'), m.get('assists'), m.get('skill'), "
                            "m.get('average_rank'), m.get('leaver_status'), m.get('party_size'), m.get('xp_per_min'), m.get('gold_per_min'), "
                            "m.get('hero_damage'), m.get('tower_damage'), m.get('hero_healing'), m.get('last_hits'), m.get('lane'), "
                            "m.get('lane_role'),m.get('is_roaming'), m.get('cluster') "
                        )
                    },
                },
            },
            "matches" : {
                "sync" : False,
                "process_json" : False,
                "process_json_merge" : (
                    "MERGE OpenDota.Match_Details_JSON AS t "
                    "USING (SELECT ? AS match_id, ? AS match_detail_json) AS s "
                    "ON (t.match_id = s.match_id) "
                    "WHEN MATCHED AND cast(t.match_detail_json AS NVARCHAR(max)) <> s.match_detail_json THEN "
                    "    UPDATE SET "
                    "        t.match_detail_json = s.match_detail_json, reprocess_tables = 1, last_updated_at = GETDATE() "
                    "WHEN NOT MATCHED THEN "
                    "    INSERT (match_id, match_detail_json) "
                    "    VALUES (s.match_id, s.match_detail_json) "
                    "; "
                ),
                "urls" : [
                    "https://api.opendota.com/api/matches/{m_id}",
                ],
                "existing" : (
                    "SELECT am.match_id "
                    "FROM OpenDota.Account_Matches am "
                    "ORDER BY am.match_id "
                ),
                "m_ids" : [],
                "list" : "",
                "identifier" : "match_id",
                "record" : {
                    "details" : {
                        "insert" : (
                            "INSERT INTO OpenDota.Match_Details ( "
                            "    match_id, barracks_status_dire, barracks_status_radiant, cluster, dire_score, "
                            "    duration, engine, first_blood_time, game_mode, human_players, "
                            "    leagueid, lobby_type, match_seq_num, negative_votes, positive_votes, "
                            "    radiant_score, radiant_win, skill, start_time, tower_status_dire, "
                            "    tower_status_radiant, version, replay_salt, series_id, series_type, "
                            "    patch, region, throw, comeback, loss, "
                            "    win, replay_url "
                            ") "
                            "VALUES ( "
                            "    ?, ?, ?, ?, ?, "
                            "    ?, ?, ?, ?, ?, "
                            "    ?, ?, ?, ?, ?, "
                            "    ?, ?, ?, ?, ?, "
                            "    ?, ?, ?, ?, ?, "
                            "    ?, ?, ?, ?, ?, "
                            "    ?, ? "
                            ") "
                        ),
                        "params" : (
                            "match_id, m.get('barracks_status_dire'), m.get('barracks_status_radiant'), m.get('cluster'), m.get('dire_score'), "
                            "m.get('duration'), m.get('engine'), m.get('first_blood_time'), m.get('game_mode'), m.get('human_players'), "
                            "m.get('leagueid'), m.get('lobby_type'), m.get('match_seq_num'), m.get('negative_votes'), m.get('positive_votes'), "
                            "m.get('radiant_score'), m.get('radiant_win'), m.get('skill'), m.get('start_time'), m.get('tower_status_dire'), "
                            "m.get('tower_status_radiant'), m.get('version'), m.get('replay_salt'), m.get('series_id'), m.get('series_type'), "
                            "m.get('patch'), m.get('region'), m.get('throw'), m.get('comeback'), m.get('loss'), "
                            "m.get('win'), m.get('replay_url') "
                        )
                    },
                    "players" : {
                        "insert" : (
                            "INSERT INTO OpenDota.Match_Player_Performances ( "
                            "    match_id, player_slot, account_id, kills, deaths, "
                            "    assists, leaver_status, aghanims_scepter, aghanims_shard, moonshard, "
                            "    personaname, name, rank_tier, computed_mmr, is_subscriber, "
                            "    lobby_type, is_contributor, radiant_win, kills_per_minute, abandons, "
                            "    gold, gold_per_min, gold_spent, net_worth, total_gold, "
                            "    xp_per_min, total_xp, level, hero_id, hero_variant, "
                            "    hero_damage, hero_healing, tower_damage, last_hits, denies, "
                            "    kda, teamfight_participation, stuns, win, lose "
                            ") "
                            "VALUES ( "
                            "    ?, ?, ?, ?, ?, "
                            "    ?, ?, ?, ?, ?, "
                            "    ?, ?, ?, ?, ?, "
                            "    ?, ?, ?, ?, ?, "
                            "    ?, ?, ?, ?, ?, "
                            "    ?, ?, ?, ?, ?, "
                            "    ?, ?, ?, ?, ?, "
                            "    ?, ?, ?, ?, ? "
                            "); "
                        ),
                        "params" : (
                            "match_id, slot, p.get('account_id'), p.get('kills'), p.get('deaths'), "
                            "p.get('assists'), p.get('leaver_status'), p.get('aghanims_scepter'), p.get('aghanims_shard'), p.get('moonshard'), "
                            "p.get('personaname'), p.get('name'), p.get('rank_tier'), p.get('computed_mmr'), p.get('is_subscriber'), "
                            "p.get('lobby_type'), p.get('is_contributor'), p.get('radiant_win'), p.get('kills_per_minute'), p.get('abandons'), "
                            "p.get('gold'), p.get('gold_per_min'), p.get('gold_spent'), p.get('net_worth'), p.get('total_gold'), "
                            "p.get('xp_per_min'), p.get('total_xp'), p.get('level'), p.get('hero_id'), p.get('hero_variant'), "
                            "p.get('hero_damage'), p.get('hero_healing'), p.get('tower_damage'), p.get('last_hits'), p.get('denies'), "
                            "p.get('kda'), p.get('teamfight_participation'), p.get('stuns'), p.get('win'), p.get('lose') "
                        )
                    }
                }
            }
        }
    },

    "Stratz" : {
        "sync" : True,
        "process_json" : True,
        "request" : "post",
        "sleep" : 0,
        "timeout" : 10,
        "take" : 100,
        "vpn" : False,
        "token" : "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJTdWJqZWN0IjoiOGQ5NzAxZjEtNzRhZC00YmIzLWI1NDYtZjkyYTE5OTBlZDgwIiwiU3RlYW1JZCI6IjE0NDU0ODczMSIsIkFQSVVzZXIiOiJ0cnVlIiwibmJmIjoxNzczMjYxNzAyLCJleHAiOjE4MDQ3OTc3MDIsImlhdCI6MTc3MzI2MTcwMiwiaXNzIjoiaHR0cHM6Ly9hcGkuc3RyYXR6LmNvbSJ9.jBuKEZ_TR1YCPmgPZZQmrRcyGTdaUMXOGZNNslVmnsw",
        "urls" : [
            "https://api.stratz.com/graphql"
        ],
        "headers" : "'Authorization' : 'Bearer {stratz_token}', 'Content-Type' : 'application/json'",         
        "cat" : {
            "accounts" : {
                "sync" : True,
                "process_json" : True,
                "process_json_merge" : (
                    "MERGE Stratz.Accounts_JSON AS t "
                    "USING (SELECT ? AS steam_account_id, ? AS account_json) AS s "
                    "ON (t.steam_account_id = s.steam_account_id) "
                    "WHEN MATCHED AND cast(t.account_json AS NVARCHAR(max)) <> s.account_json THEN "
                    "    UPDATE SET "
                    "        t.account_json = s.account_json, reprocess_tables = 1, last_updated_at = GETDATE() "
                    "WHEN NOT MATCHED THEN "
                    "    INSERT (steam_account_id, account_json) "
                    "    VALUES (s.steam_account_id, s.account_json) "
                    "; "
                ),
                "select" : (
                    "SELECT a.steam_account_id "
                    "FROM Stratz.Accounts a "
                    "WHERE a.ignore = 0 "
                ),
                "a_ids" : [],
                "graphql" : (
                    "query GetPlayerMatchIds { "
                    "    player(steamAccountId: {a_id}) { "
                    "        steamAccountId "
                    "        matchCount "
                    "        winCount "
                    "        imp "
                    "        firstMatchDate "
                    "        lastMatchDate "
                    "        lastMatchRegionId "
                    "        behaviorScore "
                    "        isFollowed "
                    "        names { "
                    "        name "
                    "        lastSeenDateTime "
                    "        } "
                    "    } "
                    "} "
                ),
                "record" : {
                    "merge" : (
                        "MERGE Stratz.Accounts AS t "
                        "USING (SELECT ? AS steam_account_id) AS s "
                        "ON (t.steam_account_id = s.steam_account_id) "
                        "WHEN MATCHED THEN "
                        "    UPDATE SET "
                        "        match_count = ?, win_count = ?, imp = ?, first_match_date = ?, last_match_date = ?, "
                        "        last_match_region_id = ?, behavior_score = ?, is_followed = ?, last_updated_at = GETDATE() "
                        "WHEN NOT MATCHED THEN "
                        "    INSERT ( "
                        "        steam_account_id, "
                        "        match_count, win_count, imp, first_match_date, last_match_date, "
                        "        last_match_region_id, behavior_score, is_followed "
                        "    ) "
                        "    VALUES ( "
                        "        ?, "
                        "        ?, ?, ?, ?, ?, "
                        "        ?, ?, ? "
                        "   ) "
                        "; "
                    ),
                    "params" : (
                        "data.get('data').get('player').get('steamAccountId'), "
                        "data.get('data').get('player').get('matchCount'), data.get('data').get('player').get('winCount'), data.get('data').get('player').get('imp'), data.get('data').get('player').get('firstMatchDate'), data.get('data').get('player').get('lastMatchDate'), "
                        "data.get('data').get('player').get('lastMatchRegionId'), data.get('data').get('player').get('behaviorScore'), data.get('data').get('player').get('isFollowed') "
                    ),
                    "aliases" : {
                        "list" : "data.get('data').get('player').get('names')",
                        "insert" : (
                            "IF NOT EXISTS ( "
                            "    SELECT 1 "
                            "    FROM Stratz.Account_Aliases "
                            "    WHERE steam_account_id = ? "
                            "    AND last_seen_date_time = ? "
                            ") "
                            "INSERT INTO Stratz.Account_Aliases (steam_account_id, alias_name, last_seen_date_time) "
                            "VALUES (?, ?, ?); "
                        ),
                        "params" : (
                            "data.get('data').get('player').get('steamAccountId'), "
                            "alias['lastSeenDateTime'], "
                            "data.get('data').get('player').get('steamAccountId'), alias['name'], alias['lastSeenDateTime'] "
                        )
                    },
                },
                "ignore" : {
                        "select" : (
                            "SELECT a.steam_account_id "
                            "FROM Stratz.Accounts a "
                            "WHERE a.ignore = 1 "
                        ),
                        "a_ids" : [],
                    "merge" : (
                        "MERGE OpenDota.Accounts AS t "
                        "USING (SELECT ? AS account_id) AS s "
                        "ON (t.account_id = s.account_id) "
                        "WHEN MATCHED THEN "
                        "   UPDATE SET "
                        "       ignore = 1, ignore_reason = ?, last_updated_at = GETDATE() "
                        "WHEN NOT MATCHED THEN "
                        "   INSERT (account_id, ignore, ignore_reason) VALUES (?, 1, ?) "
                        "; "
                    ),
                    "params" : "account_id, f'Response: {response.status_code} - {response.reason}'"
                },
            },
            "matches" : {
                "sync" : False,
                "process_json" : False,
                "process_json_merge" : (
                    "MERGE Stratz.Match_Details_JSON AS t "
                    "USING (SELECT ? AS match_id, ? AS match_detail_json) AS s "
                    "ON (t.match_id = s.match_id) "
                    "WHEN MATCHED AND cast(t.account_json AS NVARCHAR(max)) <> s.match_detail_json THEN "
                    "    UPDATE SET "
                    "        t.match_detail_json = s.match_detail_json, reprocess_tables = 1, last_updated_at = GETDATE() "
                    "WHEN NOT MATCHED THEN "
                    "    INSERT (match_id, match_detail_json) "
                    "    VALUES (s.match_id, s.match_detail_json) "
                    "; "
                ),
                "existing" : (
                    "SELECT md.match_id "
                    "FROM Stratz.Match_Details md "
                    "JOIN Stratz.Match_Player_Performances mpp ON mpp.match_id = md.match_id "
                    "WHERE mpp.steam_account_id = ? "
                    "ORDER BY md.match_id "
                ),
                "m_ids" : [],
                "graphql" : (
                    "query GetPlayerMatchDetails { "
                    "    player(steamAccountId: {a_id}) { "
                    "        matches(request: { skip: {skip}, take: {take} }) { "
                    "            id didRadiantWin durationSeconds startDateTime endDateTime "
                    "            towerStatusRadiant towerStatusDire barracksStatusRadiant barracksStatusDire "
                    "            clusterId firstBloodTime lobbyType numHumanPlayers gameMode isStats "
                    "            tournamentId tournamentRound actualRank averageRank averageImp "
                    "            gameVersionId regionId sequenceNum rank bracket analysisOutcome "
                    "            predictedOutcomeWeight bottomLaneOutcome midLaneOutcome topLaneOutcome "
                    "            players { "
                    "                matchId playerSlot steamAccountId isRadiant isVictory heroId "
                    "                gameVersionId kills deaths assists leaverStatus numLastHits numDenies "
                    "                goldPerMinute networth experiencePerMinute level gold goldSpent "
                    "                heroDamage towerDamage heroHealing partyId isRandom lane position "
                    "                streakPrediction intentionalFeeding role roleBasic imp award "
                    "                behavior invisibleSeconds dotaPlusHeroXp variant "
                    "            } "
                    "        } "
                    "    } "
                    "} "
                ),
                "list" : "data.get('data', {}).get('player'', {}).get('matches', []) or []",
                "identifier" : "id",
                "record" : {
                    "details" : {
                        "insert" : (
                            "INSERT INTO Stratz.Match_Details ( "
                            "    match_id, did_radiant_win, duration_seconds, start_date_time, end_date_time, "
                            "    tower_status_radiant, tower_status_dire, barracks_status_radiant, barracks_status_dire, cluster_id, "
                            "    first_blood_time, lobby_type, num_human_players, game_mode, is_stats, "
                            "    tournament_id, tournament_round, actual_rank, average_rank, average_imp, "
                            "    game_version_id, region_id, sequence_num, player_rank, bracket, "
                            "    analysis_outcome, predicted_outcome_weight, bottom_lane_outcome, mid_lane_outcome, top_lane_outcome "
                            ") "
                            "VALUES ( "
                            "    ?, ?, ?, ?, ?, "
                            "    ?, ?, ?, ?, ?, "
                            "    ?, ?, ?, ?, ?, "
                            "    ?, ?, ?, ?, ?, "
                            "    ?, ?, ?, ?, ?, "
                            "    ?, ?, ?, ?, ? "
                            "); "
                        ),
                        "params" : (
                            "match_id, m.get('didRadiantWin'), m.get('durationSeconds'), m.get('startDateTime'), m.get('endDateTime'), "
                            "m.get('towerStatusRadiant'), m.get('towerStatusDire'), m.get('barracksStatusRadiant'), m.get('barracksStatusDire'), m.get('clusterId'), "
                            "m.get('firstBloodTime'), m.get('lobbyType'), m.get('numHumanPlayers'), m.get('gameMode'), m.get('isStats'), "
                            "m.get('tournamentId'), m.get('tournamentRound'), m.get('actualRank'), m.get('averageRank'), m.get('averageImp'), "
                            "m.get('gameVersionId'), m.get('regionId'), m.get('sequenceNum'), m.get('rank'), m.get('bracket'), "
                            "m.get('analysisOutcome'), m.get('predictedOutcomeWeight'), m.get('bottomLaneOutcome'), m.get('midLaneOutcome'), m.get('topLaneOutcome') "
                        )
                    },
                    "players" : {
                        "insert" : (
                            "INSERT INTO Stratz.Match_Player_Performances( "
                            "    match_id, player_slot, steam_account_id, is_radiant, is_victory, "
                            "    hero_id, game_version_id, kills, deaths, assists, "
                            "    leaver_status, num_last_hits, num_denies, gold_per_minute, networth, "
                            "    experience_per_minute, level, gold, gold_spent, hero_damage, "
                            "    tower_damage, hero_healing, party_id, is_random, lane, "
                            "    position, streak_prediction, intentional_feeding, role, role_basic, "
                            "    imp, award, behavior, invisible_seconds, dota_plus_hero_xp, "
                            "    variant "
                            ") "
                            "VALUES ( "
                            "    ?, ?, ?, ?, ?, "
                            "    ?, ?, ?, ?, ?, "
                            "    ?, ?, ?, ?, ?, "
                            "    ?, ?, ?, ?, ?, "
                            "    ?, ?, ?, ?, ?, "
                            "    ?, ?, ?, ?, ?, "
                            "    ?, ?, ?, ?, ?, "
                            "    ? "
                            "); "
                        ),
                        "params" : (
                            "match_id, slot, p.get('steamAccountId'), p.get('isRadiant'), p.get('isVictory'), "
                            "p.get('heroId'), p.get('gameVersionId'), p.get('kills'), p.get('deaths'), p.get('assists'), "
                            "p.get('leaverStatus'), p.get('numLastHits'), p.get('numDenies'), p.get('goldPerMinute'), p.get('networth'), "
                            "p.get('experiencePerMinute'), p.get('level'), p.get('gold'), p.get('goldSpent'), p.get('heroDamage'), "
                            "p.get('towerDamage'), p.get('heroHealing'), p.get('partyId'), p.get('isRandom'), p.get('lane'), "
                            "p.get('position'), p.get('streakPrediction'), p.get('intentionalFeeding'), p.get('role'), p.get('roleBasic'), "
                            "p.get('imp'), p.get('award'), p.get('behavior'), p.get('invisibleSeconds'), p.get('dotaPlusHeroXp'), "
                            "p.get('variant') "
                        )
                    }
                }
            }
        }
    }
}
