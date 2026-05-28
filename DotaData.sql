-- Create the logical schema container
CREATE SCHEMA OpenDota;
GO

-- 1. Master Profile Table
CREATE TABLE OpenDota.Players (
    account_id BIGINT CONSTRAINT PK_OpenDota_Players PRIMARY KEY,
    tracked_until BIGINT,
    solo_competitive_rank INT,
    competitive_rank INT,
    rank_tier INT,
    leaderboard_rank INT,
    personaname NVARCHAR(255),
    name NVARCHAR(255),
    plus_status BIT,
    cheese INT,
    steamid BIGINT,
    avatar VARCHAR(500),
    avatarmedium VARCHAR(500),
    avatarfull VARCHAR(500),
    profileurl VARCHAR(500),
    last_login DATETIME,
    loccountrycode VARCHAR(10),
    is_contributor BIT,
    is_subscriber BIT,
    last_updated_at DATETIME CONSTRAINT DF_OpenDota_Players_last_updated DEFAULT GETDATE()
);

-- 2. One-to-Many Profile Aliases Table
CREATE TABLE OpenDota.Player_Aliases (
    alias_id INT IDENTITY(1,1) CONSTRAINT PK_OpenDota_Player_Aliases PRIMARY KEY,
    account_id BIGINT,
    alias_name NVARCHAR(255) NOT NULL,
    name_since DATETIME,
    CONSTRAINT FK_OpenDota_Player_Aliases_Players FOREIGN KEY (account_id) 
        REFERENCES OpenDota.Players(account_id),
    CONSTRAINT UQ_OpenDota_Player_Aliases UNIQUE (alias_name, name_since)
);

-- 3. Composite History Matches Table
CREATE TABLE OpenDota.Player_Matches (
    match_id BIGINT NOT NULL,
    account_id BIGINT NOT NULL,
    player_slot INT NULL,
    radiant_win BIT NULL,
    duration INT NULL,
    game_mode INT NULL,
    lobby_type INT NULL,
    hero_id INT NULL,
    hero_variant INT NULL,
    start_time BIGINT NULL,
    version INT NULL,
    kills INT NULL,
    deaths INT NULL,
    assists INT NULL,
    skill INT NULL,
    average_rank INT NULL,
    leaver_status INT NULL,
    party_size INT NULL,
    last_synced_at DATETIME CONSTRAINT DF_OpenDota_Player_Matches_last_synced DEFAULT GETDATE(),
    CONSTRAINT PK_OpenDota_Player_Matches PRIMARY KEY CLUSTERED (match_id, account_id),
    CONSTRAINT FK_OpenDota_Player_Matches_Players FOREIGN KEY (account_id) 
        REFERENCES OpenDota.Players(account_id)
);

-- 4. Deep Match Overview Configurations Header Table
CREATE TABLE OpenDota.Match_Details (
    match_id BIGINT CONSTRAINT PK_OpenDota_Match_Details PRIMARY KEY,
    barracks_status_dire INT NULL,
    barracks_status_radiant INT NULL,
    cluster INT NULL,
    dire_score INT NULL,
    duration INT NULL,
    engine INT NULL,
    first_blood_time INT NULL,
    game_mode INT NULL,
    human_players INT NULL,
    match_seq_num BIGINT NULL,
    radiant_score INT NULL,
    radiant_win BIT NULL,
    skill INT NULL,
    start_time BIGINT NULL,
    tower_status_dire INT NULL,
    tower_status_radiant INT NULL,
    version INT NULL,
    patch INT NULL,
    region INT NULL,
    last_updated_at DATETIME CONSTRAINT DF_OpenDota_Match_Details_last_updated DEFAULT GETDATE()
);

-- 5. Deep Match Granular Performance Table
CREATE TABLE OpenDota.Match_Player_Performances (
    match_id BIGINT NOT NULL,
    player_slot INT NOT NULL,
    account_id BIGINT NULL,
    kills INT NULL,
    deaths INT NULL,
    assists INT NULL,
    gold INT NULL,
    gold_per_min INT NULL,
    gold_spent INT NULL,
    net_worth INT NULL,
    total_gold INT NULL,
    xp_per_min INT NULL,
    total_xp INT NULL,
    level INT NULL,
    hero_id INT NULL,
    hero_variant INT NULL,
    hero_damage INT NULL,
    hero_healing INT NULL,
    tower_damage INT NULL,
    last_hits INT NULL,
    denies INT NULL,
    kda DECIMAL(6,2) NULL,
    teamfight_participation DECIMAL(5,4) NULL,
    stuns DECIMAL(8,4) NULL,
    win BIT NULL,
    lose BIT NULL,
    last_updated_at DATETIME DEFAULT GETDATE(),
    CONSTRAINT PK_OpenDota_Match_Player_Performances PRIMARY KEY CLUSTERED (match_id, player_slot),
    CONSTRAINT FK_OpenDota_Match_Player_Performances_Details FOREIGN KEY (match_id) 
        REFERENCES OpenDota.Match_Details(match_id) ON DELETE CASCADE
);
GO


-- Create the logical schema container
CREATE SCHEMA Stratz;
GO

-- 1. Master Profile Table
CREATE TABLE Stratz.Players (
    steam_account_id BIGINT CONSTRAINT PK_Stratz_Players PRIMARY KEY,
    match_count INT NULL,
    win_count INT NULL,
    imp INT NULL,
    first_match_date BIGINT NULL,
    last_match_date BIGINT NULL,
    last_match_region_id INT NULL,
    behavior_score INT NULL,
    is_followed BIT NULL,
    last_updated_at DATETIME CONSTRAINT DF_Stratz_Players_last_updated DEFAULT GETDATE()
);

-- 2. One-to-Many Profile Aliases Table
CREATE TABLE Stratz.Player_Aliases (
    alias_id INT IDENTITY(1,1) CONSTRAINT PK_Stratz_Player_Aliases PRIMARY KEY,
    steam_account_id BIGINT,
    alias_name NVARCHAR(255) NOT NULL,
    last_seen_date_time BIGINT NULL,
    CONSTRAINT FK_Stratz_Player_Aliases_Players FOREIGN KEY (steam_account_id) 
        REFERENCES Stratz.Players(steam_account_id)
);

-- 3. Deep Match Overview Configuration Header Table
CREATE TABLE Stratz.Match_Details (
    match_id BIGINT CONSTRAINT PK_Stratz_Match_Details PRIMARY KEY,
    did_radiant_win BIT NULL,
    duration_seconds INT NULL,
    start_date_time BIGINT NULL,
    end_date_time BIGINT NULL,
    tower_status_radiant INT NULL,
    tower_status_dire INT NULL,
    barracks_status_radiant INT NULL,
    barracks_status_dire INT NULL,
    cluster_id INT NULL,
    first_blood_time INT NULL,
    lobby_type NVARCHAR(25) NULL,
    num_human_players INT NULL,
    game_mode NVARCHAR(25) NULL,
    is_stats BIT NULL,
    tournament_id INT NULL,
    tournament_round INT NULL,
    actual_rank INT NULL,
    average_rank INT NULL,
    average_imp INT NULL,
    game_version_id INT NULL,
    region_id INT NULL,
    sequence_num BIGINT NULL,
    player_rank INT NULL,
    bracket INT NULL,
    analysis_outcome NVARCHAR(25) NULL,
    predicted_outcome_weight INT NULL,
    bottom_lane_outcome NVARCHAR(25) NULL,
    mid_lane_outcome NVARCHAR(25) NULL,
    top_lane_outcome NVARCHAR(25) NULL,
    last_updated_at DATETIME CONSTRAINT DF_Stratz_Match_Details_last_updated DEFAULT GETDATE()
);

-- 4. Deep Match Granular Performance Table
CREATE TABLE Stratz.Match_Player_Performances (
    match_id BIGINT NOT NULL,
    player_slot INT NOT NULL,
    steam_account_id BIGINT NULL,
    is_radiant BIT NULL,
    is_victory BIT NULL,
    hero_id INT NULL,
    game_version_id INT NULL,
    kills INT NULL,
    deaths INT NULL,
    assists INT NULL,
    leaver_status NVARCHAR(25) NULL,
    num_last_hits INT NULL,
    num_denies INT NULL,
    gold_per_minute INT NULL,
    networth INT NULL,
    experience_per_minute INT NULL,
    level INT NULL,
    gold INT NULL,
    gold_spent INT NULL,
    hero_damage INT NULL,
    tower_damage INT NULL,
    hero_healing INT NULL,
    party_id BIGINT NULL,
    is_random BIT NULL,
    lane NVARCHAR(25) NULL,
    position NVARCHAR(25) NULL,
    streak_prediction INT NULL,
    intentional_feeding BIT NULL,
    role NVARCHAR(25) NULL,
    role_basic NVARCHAR(25) NULL,
    imp INT NULL,
    award NVARCHAR(25) NULL,
    behavior INT NULL,
    invisible_seconds INT NULL,
    dota_plus_hero_xp INT NULL,
    variant INT NULL,
    last_updated_at DATETIME CONSTRAINT DF_Stratz_Match_Player_Performances_last_updated DEFAULT GETDATE(),
    CONSTRAINT PK_Stratz_Match_Player_Performances PRIMARY KEY CLUSTERED (match_id, player_slot),
    CONSTRAINT FK_Stratz_Match_Player_Performances_Details FOREIGN KEY (match_id) 
        REFERENCES Stratz.Match_Details(match_id)
);
GO

