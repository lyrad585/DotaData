OPENDOTA_ACCOUNT_PROFILE_SYNC = {

    "api_urls" : [ "https://api.opendota.com/api/players/{account_id}" ]

    ,"merge_account_sql" : (
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
        "    ); "
    )

    ,"merge_account_params" : (
        "int(account_id), "
        "data.get('tracked_until'), data.get('solo_competitive_rank'), data.get('competitive_rank'), data.get('rank_tier'), data.get('leaderboard_rank'), "
        "data.get('computed_mmr'), data.get('computed_mmr_turbo'), profile.get('personaname'), profile.get('name'), profile.get('plus'), "
        "profile.get('cheese'), profile.get('steamid'), profile.get('avatar'), profile.get('avatarmedium'), profile.get('avatarfull'), "
        "profile.get('profileurl'), last_login, profile.get('loccountrycode'), profile.get('is_contributor'), profile.get('is_subscriber') "
    )

    ,"insert_alias_sql" : (
        "IF NOT EXISTS ( "
        "    SELECT 1 "
        "    FROM OpenDota.Account_Aliases "
        "    WHERE account_id = ? "
        "    AND name_since = ? "
        ") "
        "INSERT INTO OpenDota.Account_Aliases (account_id, alias_name, name_since) "
        "VALUES (?, ?, ?); "
    )

    ,"insert_alias_params" : (
        "int(account_id), "
        "name_since, "
        "int(account_id), str(alias_name), name_since "
    )

}



OPENDOTA_ACCOUNT_MATCHES_SYNC = {

    "api_urls" : [ 
        "https://api.opendota.com/api/players/{account_id}/matches",
        "https://api.opendota.com/api/players/{account_id}/recentmatches"
    ]

    ,"get_existing_matches_sql" : (
        "SELECT am.match_id "
        "FROM OpenDota.Account_Matches am "
        "WHERE am.account_id = ? "
        "ORDER BY am.match_id "
    )

    ,"get_existing_matches_params" : (
        "int(account_id) "
    )

    ,"insert_account_match_sql" : (
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
    )

    ,"insert_account_match_params" : (
        "int(match_id), int(account_id), m.get('player_slot'), m.get('radiant_win'), m.get('duration'), "
        "m.get('game_mode'), m.get('lobby_type'), m.get('hero_id'), m.get('hero_variant'), m.get('start_time'), "
        "m.get('version'), m.get('kills'), m.get('deaths'), m.get('assists'), m.get('skill'), "
        "m.get('average_rank'), m.get('leaver_status'), m.get('party_size'), m.get('xp_per_min'), m.get('gold_per_min'), "
        "m.get('hero_damage'), m.get('tower_damage'), m.get('hero_healing'), m.get('last_hits'), m.get('lane'), "
        "m.get('lane_role'),m.get('is_roaming'), m.get('cluster') "
    )

}



OPENDOTA_MATCH_DETAILS_SYNC = {

    "insert_match_details_sql" : (
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
    )

    ,"insert_match_details_params" : (
        "match_id, m.get('barracks_status_dire'), m.get('barracks_status_radiant'), m.get('cluster'), m.get('dire_score'), "
        "m.get('duration'), m.get('engine'), m.get('first_blood_time'), m.get('game_mode'), m.get('human_players'), "
        "m.get('leagueid'), m.get('lobby_type'), m.get('match_seq_num'), m.get('negative_votes'), m.get('positive_votes'), "
        "m.get('radiant_score'), m.get('radiant_win'), m.get('skill'), m.get('start_time'), m.get('tower_status_dire'), "
        "m.get('tower_status_radiant'), m.get('version'), m.get('replay_salt'), m.get('series_id'), m.get('series_type'), "
        "m.get('patch'), m.get('region'), m.get('throw'), m.get('comeback'), m.get('loss'), "
        "m.get('win'), m.get('replay_url') "
    )

    ,"insert_match_player_sql" : (
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
    )

    ,"insert_match_player_params" : (
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
