
api_urls = [ "https://api.stratz.com/graphql" ]
api_headers = "'Authorization' : 'Bearer {stratz_token}', 'Content-Type' : 'application/json'"



STRATZ_ACCOUNT_PROFILE_SYNC = {

    "api_account_cmd" : (
        "query GetPlayerMatchIds { "
        "    player(steamAccountId: %d) { "
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
    )

    ,"merge_account_sql" : (
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
        "    ); "
    )

    ,"merge_account_params" : (
        "int(account_id), "
        "player_data.get('matchCount'), player_data.get('winCount'), player_data.get('imp'), player_data.get('firstMatchDate'), player_data.get('lastMatchDate'), "
        "player_data.get('lastMatchRegionId'), player_data.get('behaviorScore'), player_data.get('isFollowed') "
    )

    ,"insert_alias_sql" : (
        "IF NOT EXISTS ( "
        "    SELECT 1 "
        "    FROM Stratz.Account_Aliases "
        "    WHERE steam_account_id = ? "
        "    AND last_seen_date_time = ? "
        ") "
        "INSERT INTO Stratz.Account_Aliases (steam_account_id, alias_name, last_seen_date_time) "
        "VALUES (?, ?, ?); "
    )

    ,"insert_alias_params" : (
        "int(account_id), "
        "n.get('lastSeenDateTime'), "
        "int(account_id), str(alias_name), n.get('lastSeenDateTime') "
    )

}



STRATZ_MATCH_DETAILS_SYNC = {

    "api_cmd" : (
        "query GetPlayerMatchDetails { "
        "    player(steamAccountId: %d) { "
        "        matches(request: { skip: %d, take: %d }) { "
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
    )

    ,"get_existing_matches_sql" : (
        "SELECT md.match_id "
        "FROM Stratz.Match_Details md "
        "ORDER BY md.match_id "
    )

    ,"insert_match_details_sql" : (
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
    )

    ,"insert_match_details_params" : (
        "match_id, m.get('didRadiantWin'), m.get('durationSeconds'), m.get('startDateTime'), m.get('endDateTime'), "
        "m.get('towerStatusRadiant'), m.get('towerStatusDire'), m.get('barracksStatusRadiant'), m.get('barracksStatusDire'), m.get('clusterId'), "
        "m.get('firstBloodTime'), m.get('lobbyType'), m.get('numHumanPlayers'), m.get('gameMode'), m.get('isStats'), "
        "m.get('tournamentId'), m.get('tournamentRound'), m.get('actualRank'), m.get('averageRank'), m.get('averageImp'), "
        "m.get('gameVersionId'), m.get('regionId'), m.get('sequenceNum'), m.get('rank'), m.get('bracket'), "
        "m.get('analysisOutcome'), m.get('predictedOutcomeWeight'), m.get('bottomLaneOutcome'), m.get('midLaneOutcome'), m.get('topLaneOutcome') "
    )

    ,"insert_match_player_sql" : (
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
    )

    ,"insert_match_player_params" : (
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