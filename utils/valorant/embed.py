from __future__ import annotations
from operator import itemgetter

import re
import io
import json
import math, random
import contextlib
from datetime import datetime, timedelta, timezone
import dateutil.parser
from tracemalloc import start
from typing import Any, Dict, List, TYPE_CHECKING, Union
from unittest import result

from utils.errors import (
    ValorantBotError
)

import discord
import matplotlib.pyplot as plt

from .endpoint import API_ENDPOINT

from .useful import (calculate_level_xp, format_relative, GetEmoji, GetFormat, GetItems, iso_to_time, format_timedelta, JSON)
from ..locale_v2 import ValorantTranslator

VLR_locale = ValorantTranslator()

if TYPE_CHECKING:
    from bot import ValorantBot


class Embed(discord.Embed):  # Custom Embed
    def __init__(self, description: str = None, color: Union[discord.Color, int] = 0xfd4554, **kwargs: Any) -> None:
        super().__init__(description=description, color=color, **kwargs)


class GetEmbed:
    
    def __giorgio_embed(skin: Dict, bot: ValorantBot, response: Dict) -> discord.Embed:
        """EMBED DESIGN Giorgio"""
        
        uuid, name, price, icon, video_url = skin['uuid'], skin['name'], skin['price'], skin['icon'], skin.get('video')
        emoji = GetEmoji.tier_by_bot(uuid, bot)

        if video_url!=None:
            video_text = response.get("VIDEO", "")
            video = f"[{video_text}]({video_url})"
        else:
            video = ""
        
        vp_emoji = GetEmoji.point_by_bot('ValorantPointIcon', bot)
        
        embed = Embed(response.get("SKIN", "").format(emoji=emoji, name=name, vp_emoji=vp_emoji, price=price, video=video), color=0x0F1923)
        embed.set_thumbnail(url=icon)
        return embed
    
    @classmethod
    def store(cls, player: str, offer: Dict, response: Dict, bot: ValorantBot) -> List[discord.Embed]:
        """Embed Store"""
        
        store_response = response.get('RESPONSE')
        
        data = GetFormat.offer_format(offer)
        
        duration = data.pop('duration')
        
        description = store_response.format(username=player, duration=format_relative(datetime.utcnow() + timedelta(seconds=duration)))
        
        embed = Embed(description)
        embeds = [embed]
        [embeds.append(cls.__giorgio_embed(data[skin], bot, response)) for skin in data]
        
        return embeds
    
    # ---------- MISSION EMBED ---------- #
    
    def mission(player: str, mission: Dict, response: Dict) -> discord.Embed:
        """Embed Mission"""
        
        # language
        title_mission = response.get('TITLE')
        title_daily = response.get('DAILY')
        title_weekly = response.get('WEEKLY')
        title_new_player = response.get('NEWPLAYER')
        clear_all_mission = response.get('NO_MISSION')
        reset_in = response.get('DAILY_RESET')
        refill_in = response.get('REFILLS')
        
        # mission format
        data = GetFormat.mission_format(mission)
        
        daily_format = data['daily']
        daily_end = data['daily_end']
        weekly_format = data['weekly']
        weekly_end = data['weekly_end']
        new_player_format = data['newplayer']
        
        daily = ''.join(daily_format)
        weekly = ''.join(weekly_format)
        new_player = ''.join(new_player_format)
        
        weekly_end_time = ''
        with contextlib.suppress(Exception):
            weekly_end_time = f"{refill_in.format(duration=format_relative(iso_to_time(weekly_end)))}"
        
        embed = Embed(title=f"**{title_mission}**")
        embed.set_footer(text=player)
        if len(daily) != 0:
            embed.add_field(
                name=f"**{title_daily}**",
                value=f"{daily}\n{reset_in.format(duration=format_relative(iso_to_time(daily_end)))}",
                inline=False
            )
        if len(weekly) != 0:
            embed.add_field(
                name=f"**{title_weekly}**",
                value=f"{weekly}\n\n{weekly_end_time}",
                inline=False
            )
        if len(new_player) != 0:
            embed.add_field(
                name=f"**{title_new_player}**",
                value=f"{new_player}",
                inline=False
            )
        if len(embed.fields) == 0:
            embed.color = 0x77dd77
            embed.description = clear_all_mission
        
        return embed
    
    # ---------- POINT EMBED ---------- #
    
    def point(player: str, wallet: Dict, response: Dict, bot: ValorantBot) -> discord.Embed:
        """Embed Point"""
        
        # language
        title_point = response.get('POINT')
        
        cache = JSON.read('cache')
        point = cache['currencies']
        
        vp_uuid = '85ad13f7-3d1b-5128-9eb2-7cd8ee0b5741'
        rad_uuid = 'e59aa87c-4cbf-517a-5983-6e81511be9b7'
        
        valorant_point = wallet['Balances'][vp_uuid]
        radiant_point = wallet['Balances'][rad_uuid]
        
        rad = point[rad_uuid]['names'][str(VLR_locale)]
        vp = point[vp_uuid]['names'][str(VLR_locale)]
        if vp == 'VP': vp = 'Valorant Points'
        
        embed = Embed(title=f"{title_point}:")
        
        vp_emoji = GetEmoji.point_by_bot('ValorantPointIcon', bot)
        rad_emoji = GetEmoji.point_by_bot('RadianitePointIcon', bot)
        
        embed.add_field(name=vp, value=f"{vp_emoji} {valorant_point}")
        embed.add_field(name=rad, value=f"{rad_emoji} {radiant_point}")
        embed.set_footer(text=player)
        
        return embed
    
    # ---------- RANK EMBED ---------- #

    def rank(player: str, mmr: Dict, response: Dict, endpoint: Dict, bot: ValorantBot) -> discord.Embed:
        """Embed Rank"""
        cache = JSON.read('cache')

        # language
        title_rank = response.get('TITLE')
        title_rr_response = response.get('RESPONSE')
        title_current_tier = response.get('CURRENT_RANK')
        title_tier_matchmaking = response.get('TIER_MATCHMAKING')
        title_rankrating = response.get('CURRENT_RR')
        title_wins = response.get('WINS')
        title_leaderboard = response.get('LEADERBOARD')

        # competitive tier
        season_id = mmr['LatestCompetitiveUpdate']['SeasonID']
        if season_id==None:
            season_id = ""
        if len(season_id) == 0:
            season_id = endpoint.__get_live_season()

        current_season = mmr["QueueSkills"]['competitive']['SeasonalInfoBySeasonID']
        tier = current_season[season_id]['CompetitiveTier']
        rank_name = GetFormat.get_competitive_tier_name(tier)

        
        # other value
        rankrating = current_season[season_id]["RankedRating"] # rank rating 
        wins = current_season[season_id]["NumberOfWinsWithPlacements"] # number of wins
        games = current_season[season_id]["NumberOfGames"] #number of games
        leaderboard = current_season[season_id]["LeaderboardRank"]
        if leaderboard==0: leaderboard="-"

        # win rate
        n_games = games
        if games==0:
            n_games = 1
        win_rate = round(float(wins)/float(n_games)* 100) 


        # matchmaking
        rank_tierlist = GetFormat.get_competitive_tier_matching(tier)
        rank_tiermsg = ""
        for val in rank_tierlist:
            if len(rank_tiermsg)!=0:
                rank_tiermsg += "\n"
            rank_tiermsg += title_tier_matchmaking['RESPONSE'].format(rank1=GetFormat.get_competitive_tier_name(val[0]), rank2=GetFormat.get_competitive_tier_name(val[1]))

        # embed
        embed = Embed(title=f"{title_rank}:")
        embed.add_field(name=title_current_tier, value=f"{rank_name}")
        embed.add_field(name=title_rankrating, value=title_rr_response.format(rankrating=rankrating))
        embed.add_field(name=title_tier_matchmaking['TITLE'], value=rank_tiermsg, inline=False)
        embed.add_field(name=title_wins["TITLE"], value=title_wins["RESPONSE"].format(wins=wins, games=games, win_rate=win_rate))
        embed.add_field(name=title_leaderboard["TITLE"], value=title_leaderboard["RESPONSE"].format(leaderboard=leaderboard))

        embed.set_thumbnail(url=cache["competitive_tiers"][str(tier)]["icon"])
        embed.set_footer(text=player)
        
        return embed
    
    # ---------- MATCH DATA UTILS ----------- #
    def get_match_info(puuid: str, match_id: str, endpoint, response: Dict) -> Dict:
        # cache
        cache = JSON.read("cache")

        # match info
        match_detail = endpoint.fetch_match_details(match_id)
        if match_detail==None:
            raise ValorantBotError("マッチが見つかりませんでした")

        info = match_detail["matchInfo"]
        start_time, duration = format_relative(datetime.fromtimestamp(info["gameStartMillis"]/1000, timezone.utc)), format_timedelta(timedelta(milliseconds=info["gameLengthMillis"]))
        mapid = GetFormat.get_mapuuid_from_mapid(info["mapId"])
        match_id, map = info["matchId"], cache["maps"][mapid]["name"][str(VLR_locale)]
        season_id = info["seasonId"]
        penalties = info.get("partyRRPenalties", {})
        is_played = False

        match_info = {
            "time": start_time,
            "duration": duration,
            "map_id": mapid,
            "map": map,

            "match_id": match_id,
            "season_id": season_id
        }

        # queue
        queue = ""
        gamemode_icon = ""
        queue_id = info["queueID"]
        if queue_id in ["unrated", "competitive", "deathmatch", "ggteam", "onefa", "custom", "newmap", "snowball", "spikerush"]:
            queue = response["QUEUE"][queue_id]
            if queue_id=="deathmatch":
                gamemode_icon = cache["gamemodes"]["a8790ec5-4237-f2f0-e93b-08a8e89865b2"]["icon"]
            elif queue_id=="ggteam":
                gamemode_icon = cache["gamemodes"]["a4ed6518-4741-6dcb-35bd-f884aecdc859"]["icon"]
            elif queue_id=="onefa":
                gamemode_icon = cache["gamemodes"]["4744698a-4513-dc96-9c22-a9aa437e4a58"]["icon"]
            elif queue_id=="spikerush":
                gamemode_icon = cache["gamemodes"]["e921d1e6-416b-c31f-1291-74930c330b7b"]["icon"]
            elif queue_id=="snowball":
                gamemode_icon = cache["gamemodes"]["57038d6d-49b1-3a74-c5ef-3395d9f23a97"]["icon"]
            else:
                gamemode_icon = cache["gamemodes"]["96bd3920-4f36-d026-2b28-c683eb0bcac5"]["icon"]

        else:
            queue_id = "unknown"
            queue = response["QUEUE"]["unknown"]
            gamemode_icon = cache["gamemodes"]["96bd3920-4f36-d026-2b28-c683eb0bcac5"]["icon"]
        
        match_info["queue"] = queue_id
        match_info["queue"] = queue
        match_info["gamemode_icon"] = gamemode_icon
        
        # player
        raw_players = match_detail.get("players", [])
        players = {}
        for p in raw_players:
            player = {
                "puuid": p["subject"],
                "name": "{name}#{tagline}".format(name=p["gameName"], tagline=p["tagLine"]),
                "level": p["accountLevel"],
                "rank": GetFormat.get_competitive_tier_name(p["competitiveTier"]),
                "rank_id": p["competitiveTier"],

                "kills": p["stats"]["kills"],
                "deaths": p["stats"]["deaths"],
                "assists": p["stats"]["assists"],
                "played_round": p["stats"]["roundsPlayed"],
                "score": p["stats"]["score"],

                "kd": GetFormat.get_kdrate(p["stats"]["kills"], p["stats"]["deaths"]),
                "kda": GetFormat.get_kdarate(p["stats"]["kills"], p["stats"]["deaths"], p["stats"]["assists"]),
                "acs": round(float(p["stats"]["score"])/20.0),

                "team": p["teamId"],
                "party": p["partyId"],
                "agent_id": p["characterId"],
                "player_card": p["playerCard"],
                "player_title": p["playerTitle"],
                
                "agent": cache["agents"][p["characterId"]]["name"][str(VLR_locale)],
                "role": cache["agents"][p["characterId"]]["role"]["name"][str(VLR_locale)],

                "firstblood": 0,
                "firstdeath": 0,
                "multikills": 0,

                "deathmatch": 0
            }

            if p["subject"]==puuid:
                is_played = True
            
            # penalty
            player["penalty"] = penalties.get(p["partyId"], 0)

            # abilities
            if p["stats"].get("abilityCasts", None)!=None:
                ability = p["stats"]["abilityCasts"]
                player["ability"] = [ability["ability1Casts"], ability["ability2Casts"], ability["grenadeCasts"], ability["ultimateCasts"]],
            
            # damage
            if p.get("roundDamage")!=None:
                for d in p.get("roundDamage"):
                    if player.get("damage", None)==None:
                        player["damage"] = {}
                    if player["damage"].get(str(d["round"]), None)==None:
                        player["damage"][str(d["round"])] = 0
                    player["damage"][str(d["round"])] += d["damage"]
            else:
                if player.get("damage")==None:
                    player["damage"] = {}
                for i in range(len(match_detail["roundResults"])):
                    player["damage"][str(i)] = 0

            players[p["subject"]] = player

        match_info["is_played"] = is_played

        # round
        raw_rounds = match_detail["roundResults"]
        rounds = []
        for r in raw_rounds:
            _round = {
                "planter": r.get("bombPlanter", ""),
                "defuser": r.get("bombDefuser", ""),
                "plant_time": round(float(r["plantRoundTime"])/1000.0, 1),
                "defuse_time": round(float(r["defuseRoundTime"])/1000.0, 1),
                "plant_site": r["plantSite"],

                "result": r["roundResultCode"],
                "number": r["roundNum"] + 1,
                "win": r["winningTeam"],
                "economy": {}
            }

            ceremony_id = GetFormat.get_uuid_from_ceremony_id(r["roundCeremony"])
            if ceremony_id==None or len(ceremony_id)==0:
                _round["ceremony"] = ""
            else:
                _round["ceremony"] = cache["ceremonies"][ceremony_id]["name"][str(VLR_locale)]

            # economy
            if r.get("playerEconomies")!=None:
                for e in r.get("playerEconomies"):
                    if _round.get("economy").get("players", None)==None:
                        _round["economy"]["players"] = {}
                    _round["economy"]["players"][e["subject"]] = {
                        "loadout": e["loadoutValue"],
                        "remain": e["remaining"],
                        "spent": e["spent"],
                        "weapon": e["weapon"],
                        "armor": e["armor"]
                    }

            # stats
            for stats in r.get("playerStats", []):
                teamid = players[stats["subject"]]["team"]

                # economy
                if _round["economy"].get(teamid, None)==None:
                    _round["economy"][teamid] = {
                        "loadout": stats["economy"]["loadoutValue"],
                        "remain": stats["economy"]["remaining"],
                        "spent": stats["economy"]["spent"]
                    }
                else:
                    _round["economy"][teamid]["loadout"] += stats["economy"]["loadoutValue"]
                    _round["economy"][teamid]["remain"] += stats["economy"]["remaining"]
                    _round["economy"][teamid]["spent"] += stats["economy"]["spent"]
                
                # stats
                if _round.get("stats", None)==None:
                    _round["stats"] = {}
                _round["stats"][stats["subject"]] = {
                    "kills": len(stats["kills"]),
                    "score": stats["score"],
                    "headshots": 0,
                    "legshots": 0,
                    "bodyshots": 0,
                    "damage": 0
                }

                for d in stats.get("damage", []):
                    _round["stats"][stats["subject"]]["headshots"] += d.get("headshots", 0)
                    _round["stats"][stats["subject"]]["bodyshots"] += d.get("bodyshots", 0)
                    _round["stats"][stats["subject"]]["legshots"] += d.get("legshots", 0)
                    _round["stats"][stats["subject"]]["damage"] += d.get("damage", 0)
                
                # multikills (3kills+)
                if len(stats["kills"])>=3:
                    players[stats["subject"]]["multikills"] += 1

            rounds.append(_round)
        
        # eco rating
        for t_puuid,p in players.items():
            damage = 0
            spent = 0
            headshots = 0
            bodyshots = 0
            legshots = 0
            eco_rating = 0

            for i in range(len(rounds)):
                if rounds[i]["economy"].get("players")!=None:
                    if rounds[i]["economy"]["players"].get(t_puuid, {}).get("spent", None)==None:
                        spent += 0
                    else:
                        spent += rounds[i]["economy"]["players"][t_puuid]["spent"]

                    damage += rounds[i]["stats"][t_puuid]["damage"]
                    headshots += rounds[i]["stats"][t_puuid]["headshots"]
                    bodyshots += rounds[i]["stats"][t_puuid]["bodyshots"]
                    legshots += rounds[i]["stats"][t_puuid]["legshots"]

                    if spent == 0:
                        eco_rating = round(damage*1000/1)
                    else:
                        eco_rating = round(damage*1000/spent)

                players[t_puuid]["eco_rating"] = eco_rating
                players[t_puuid]["total_damage"] = damage
                players[t_puuid]["adr"] = round(damage / len(rounds), 1)
                players[t_puuid]["headshots"] = headshots
                players[t_puuid]["bodyshots"] = bodyshots
                players[t_puuid]["legshots"] = legshots
                players[t_puuid]["shots"] = headshots + bodyshots + legshots
                if (headshots + bodyshots + legshots)==0:
                    players[t_puuid]["hsrate"] = 0.0
                    players[t_puuid]["bsrate"] = 0.0
                    players[t_puuid]["lsrate"] = 0.0
                else:
                    players[t_puuid]["hsrate"] = round(headshots / (headshots + bodyshots + legshots) * 100, 1)
                    players[t_puuid]["bsrate"] = round(bodyshots / (headshots + bodyshots + legshots) * 100, 1)
                    players[t_puuid]["lsrate"] = round(legshots / (headshots + bodyshots + legshots) * 100, 1)
        
        # kills
        raw_killlist = match_detail["kills"]
        roundtemp = -1
        for k in raw_killlist:
            if players[k["killer"]].get("kill_list", None) == None:
                players[k["killer"]]["kill_list"] = {}
            if players[k["victim"]].get("killed_list", None) == None:
                players[k["victim"]]["killed_list"] = {}
            
            # kill
            if players[k["killer"]]["kill_list"].get(k["victim"], None)==None:
                players[k["killer"]]["kill_list"][k["victim"]] = 1
            else:
                players[k["killer"]]["kill_list"][k["victim"]] += 1
            
            # killed by
            if players[k["victim"]]["killed_list"].get(k["killer"], None)==None:
                players[k["victim"]]["killed_list"][k["killer"]] = 1
            else:
                players[k["victim"]]["killed_list"][k["killer"]] += 1
            
            # assist to
            for a in k["assistants"]:
                if players[a].get("assist_list", None)==None:
                    players[a]["assist_list"] = {}
                
                if players[a]["assist_list"].get(k["victim"], None)==None:
                    players[a]["assist_list"][k["victim"]] = 1
                else:
                    players[a]["assist_list"][k["victim"]] += 1
            
            # firstblood / firstdeath
            if roundtemp!=k["round"]:
                players[k["victim"]]["firstdeath"] += 1
                players[k["killer"]]["firstblood"] += 1
                roundtemp=k["round"]


        # teams
        teams = {}
        for t in match_detail["teams"]:
            teams[t["teamId"]] = {
                "win": t["won"],
                "id": t["teamId"],
                "point": t["numPoints"],
                "rounds": t["roundsPlayed"]
            }
        
        for p in players.values():
            if teams.get(p["team"]).get("players", None)==None:
                teams[p["team"]]["players"] = []
            
            teams[p["team"]]["players"].append(p["puuid"])
        
        for key in teams.keys():
            temp_list = {}
            for p in teams[key]["players"]:
                temp_list[p] = players[p]["score"]
            temp_list2 = sorted(temp_list.items(), key=lambda i: i[1], reverse=True)

            teams[key]["players"] = []
            for value in temp_list2:
                teams[key]["players"].append(value[0])
        
        # points
        point_v = [0,0]
        teamA, teamB = "", ""
        if len(teams)==2:
            if is_played:
                for t in teams.values():
                    if t["id"]==teams[players[puuid]["team"]]["id"]:
                        point_v[0] = t["point"]
                        teamA = t["id"]
                    else:
                        point_v[1] = t["point"]
                        teamB = t["id"]
            else:
                count = 0
                for t in teams.values():
                    if count==0: teamA = t["id"]
                    else: teamB = t["id"]

                    point_v[count] = t["point"]
                    count += 1
        else:
            if is_played:
                pp = ["", ""]
                for t in teams.values():
                    if t["point"]>point_v[0]:
                        pp[1] = pp[0]
                        point_v[1] = point_v[0]

                        pp[0] = t["id"]
                        point_v[0] = t["point"]
                
                if pp[0]!=puuid:
                    point_v[1] = teams[puuid]["point"]
            else:
                for t in teams.values():
                    if t["point"]>point_v[0]:
                        point_v[1] = point_v[0]
                        point_v[0] = t["point"]
                

        point = f"{point_v[0]}-{point_v[1]}"
        match_info["point"] = point
        match_info["teamA"] = teamA
        match_info["teamB"] = teamB

        # results
        temp_result = 0
        if queue_id!="deathmatch":
            if is_played and point_v[0]>point_v[1]:
                temp_result = 1
                results = response.get("RESULT", {}).get("WIN", "")
                color=0x3cb371
            elif is_played and point_v[1]>point_v[0]:
                temp_result = -1
                results = response.get("RESULT", {}).get("LOSE", "")
                color=0xff0000
            elif point_v[1]==point_v[0]:
                results = response.get("RESULT", {}).get("DRAW", "")
                color=0x4169e1
            elif (not is_played) and point_v[1]!=point_v[0]:
                temp_result = 1
                results = response.get("RESULT", {}).get("WIN", "")
                color=0x3cb371
        else:
            if is_played and point_v[0]==40 and teams[puuid]["point"]==40:
                temp_result = 1
                results = response.get("RESULT", {}).get("WIN", "")
                color=0x3cb371
            elif is_played and point_v[0]==40 and teams[puuid]["point"]<40:
                temp_result = -1
                results = response.get("RESULT", {}).get("LOSE", "")
                color=0xff0000
            elif point_v[0]<=40:
                results = response.get("RESULT", {}).get("DRAW", "")
                color=0x4169e1
            else:
                temp_result = 1
                results = response.get("RESULT", {}).get("WIN", "")
                color=0x3cb371
        match_info["color"] = color
        match_info["results"] = results

        # player result
        for t in teams.values():
            for p in t["players"]:
                if len(teams)==2:
                    if t["win"]:
                        players[p]["results"] = response.get("RESULT", {}).get("WIN", "")
                        players[p]["results_num"] = 1
                    else:
                        players[p]["results"] = response.get("RESULT", {}).get("LOSE", "")
                        players[p]["results_num"] = -1
                else:
                    if temp_result==0:
                        players[p]["results"] = response.get("RESULT", {}).get("DRAW", "")
                        players[p]["results_num"] = 0
                    else:
                        if t["win"]:
                            players[p]["results"] = response.get("RESULT", {}).get("WIN", "")
                            players[p]["results_num"] = 1
                        else:
                            players[p]["results"] = response.get("RESULT", {}).get("LOSE", "")
                            players[p]["results_num"] = -1

        # deathmatch prize
        temp_list = {}
        for key in players.keys():
            temp_list[key] = players[key]["kills"]

        temp_list2 = sorted(temp_list.items(), key=lambda i: i[1], reverse=True)

        sorted_players = []
        for value in temp_list2:
            sorted_players.append(value[0])
            
        message = ""
        i = 1
        prev_player = ""
        for t_puuid in sorted_players:
            if i!=1:
                if players[t_puuid]["kills"]==players[prev_player]["kills"]:
                    players[t_puuid]["deathmatch"] = players[prev_player]["deathmatch"]
                else:
                    players[t_puuid]["deathmatch"] = i
            else:
                players[t_puuid]["deathmatch"] = i

            prev_player = t_puuid
            i = i + 1

        return {"match_info": match_info, "players": players, "rounds": rounds, "teams": teams}

    def format_match_playerdata(format: str, players: Dict, puuid: str, match_id: str, bot: ValorantBot):
        if format==None:
            return None
        return format.format(
            tracker=GetFormat.get_trackergg_link(match_id),

            puuid=puuid,
            name=players[puuid]["name"],
            rank=players[puuid]["rank"],
            level=players[puuid]["level"],
            agent=players[puuid]["agent"],
            agent_emoji=GetEmoji.agent_by_bot(players[puuid]["agent_id"], bot),
            role=players[puuid]["role"],
            role_emoji=GetEmoji.role_by_bot(players[puuid]["agent_id"], bot),
            kills=players[puuid]["kills"],
            deaths=players[puuid]["deaths"],
            assists=players[puuid]["assists"],
            kd=players[puuid]["kd"],
            kda=players[puuid]["kda"],
            acs=players[puuid]["acs"],

            eco_rating=players[puuid]["eco_rating"],
            damage=players[puuid]["damage"],
            adr=players[puuid]["adr"],
            
            headshots=players[puuid]["headshots"],
            bodyshots=players[puuid]["bodyshots"],
            legshots=players[puuid]["legshots"],
            hsrate=players[puuid]["hsrate"],
            bsrate=players[puuid]["bsrate"],
            lsrate=players[puuid]["lsrate"],

            firstblood=players[puuid]["firstblood"],
            firstdeath=players[puuid]["firstdeath"],
            multikills=players[puuid]["multikills"],
            deathmatch=players[puuid]["deathmatch"]
        )

    # ---------- MATCH DETAILS EMBED ---------- #
    def __match_graph(rounds: Dict, teamA: str, teamB: str) -> discord.File:

        # create graph
        plt.figure(figsize=(15, 3), dpi=300)
        plt.style.use("dark_background")
        ax = plt.axes()

        # add a lines
        y = [-30000, -20000, -10000, 0, 10000, 20000, 30000]
        x, y_m = [], []
        for r in rounds:
            x.append(r["number"])
            money = (r["economy"][teamA]["remain"]-r["economy"][teamB]["remain"]) + (r["economy"][teamA]["loadout"]-r["economy"][teamB]["loadout"])
            y_m.append(money)

            if r["win"]==teamA:
                ax.axvspan(r["number"]-0.5, r["number"]+0.5, color="#3cb371", alpha=0.1)
            else:
                ax.axvspan(r["number"]-0.5, r["number"]+0.5, color="#ff0000", alpha=0.1)
        
        # grid
        ax.grid(which = "major", axis = "y", alpha = 0.3, linestyle = "--", linewidth = 1)
        ax.grid(which = "major", axis = "y", alpha = 0.3, linestyle = "--", linewidth = 1)
        ax.axhline(y=0, color='white',linestyle='-', alpha=0.5, linewidth = 1)

        # draw point and line
        plt.plot(x, y_m, label="Economy", color="white")

        for i in range(len(x)):
            if y_m[i] >= 0:
                plt.plot(x[i], y_m[i], marker='.', markersize=15, color="#3cb371")
            else:
                plt.plot(x[i], y_m[i], marker='.', markersize=15, color="#ff0000")
        

        plt.xticks(x)
        plt.yticks(y)
        plt.savefig("temp/graph.png", bbox_inches='tight', transparent=True)
        plt.close()

        with open("temp/graph.png", "rb") as f:
            file = io.BytesIO(f.read())
        image = discord.File(file, filename="graph.png")

        return image

    def __match_heatmap(players: Dict, teams: Dict, teamA: str, teamB: str) -> discord.File:
        # create graph
        plt.figure(figsize=(15, 15), dpi=300)
        plt.style.use("dark_background")
        
        # get value
        array_detail = [[{"a": 0, "b": 0} for i in range(5)] for j in range(5)]
        array_data = [[0]*5  for i in range(5)]

        y = 0
        for kp in teams[teamA]["players"]:
            for name,times in players[kp].get("kill_list", {}).items():
                if name in teams[teamB]["players"]:
                    x = teams[teamB]["players"].index(name)
                    array_data[y][x] += times
                    array_detail[y][x]["a"] = times

            for name,times in players[kp].get("killed_list", {}).items():
                if name in teams[teamB]["players"]:
                    x = teams[teamB]["players"].index(name)
                    array_data[y][x] -= times
                    array_detail[y][x]["b"] = times
            y = y + 1

        # draw heatmap
        fig, ax = plt.subplots()
        im = ax.imshow(array_data, aspect='equal', cmap='RdYlGn', vmin=-10, vmax=10)
        # fig.colorbar(im, ax=ax)

        # add text
        x,y=0,0
        for x in range(5):
            for y in range(5):
                ax.text(
                    x,
                    y,
                    "{value}".format(value=array_data[y][x]),
                    verticalalignment="center",
                    horizontalalignment="center",
                    color="Black",
                    fontsize=13,
                    alpha=0.5,
                    fontname="Noto Sans CJK JP"
                )
                ax.text(
                    x,
                    y+0.2,
                    "{a} - {b}".format(a=array_detail[y][x]["a"], b=array_detail[y][x]["b"]),
                    verticalalignment="center",
                    horizontalalignment="center",
                    color="Black",
                    fontsize=8,
                    alpha=0.5,
                    fontname="Noto Sans CJK JP",
                )
        
        # ticks
        cache = JSON.read("cache")

        ls = []
        for player in teams[teamA]["players"]:
            n = players[player]["name"].split("#")
            agent = players[player]["agent"]
            ls.append(f"{n[0]}\n#{n[1]}\n({agent})")
        plt.yticks(range(5), ls, fontname="Noto Sans CJK JP", fontsize=8)

        ls = []
        for player in teams[teamB]["players"]:
            n = players[player]["name"].split("#")
            agent = players[player]["agent"]
            ls.append(f"{n[0]}\n#{n[1]}\n({agent})")
        plt.xticks(range(5), ls, fontname="Noto Sans CJK JP", fontsize=8, rotation=45, horizontalalignment="right")

        # save image
        plt.savefig("temp/heatmap.png", bbox_inches='tight', transparent=True)
        plt.close()

        with open("temp/heatmap.png", "rb") as f:
            file = io.BytesIO(f.read())
        image = discord.File(file, filename="heatmap.png")

        return image


    def __match_embed_players(cls, cache: Dict, response: Dict, teams: Dict, players: Dict, teamA: Dict, teamB: Dict, color: str, match_id, bot: ValorantBot) -> discord.Embed:
        # player result post
        embed_players = Embed(title=response.get("PLAYER", {}).get("TITLE"), color=color)

        def make_team_msg(team_name: str, title_format: str, message_format: str, team: str) -> List:
            message = ""
            for p in teams[team_name]["players"]:
                if len(message)!=0:
                    message+="\n"
                message += cls.format_match_playerdata(message_format, players, p, match_id, bot)
                if teams[team_name]["win"]:
                    _result = response["RESULT"]["WIN"]
                else:
                    _result = response["RESULT"]["LOSE"]
            title = title_format.format(
                result=_result,
                point=teams[team_name]["point"],
                team = team
            )
            return [title, message]
        
        
        if len(teams)==2: # default
            ret = make_team_msg(teamA, response.get("PLAYERS", {}).get("RESPONSE"), response.get("PLAYERS", {}).get("DETAIL"), response.get("TEAM_A"))
            embed_players.add_field(name=ret[0], value=ret[1], inline=False)

            ret = make_team_msg(teamB, response.get("PLAYERS", {}).get("RESPONSE"), response.get("PLAYERS", {}).get("DETAIL"), response.get("TEAM_B"))
            embed_players.add_field(name=ret[0], value=ret[1], inline=False)
            embed_players.set_image(url=f"attachment://heatmap.png")

            graph = cls.__match_heatmap(players, teams, teamA, teamB)
            return [embed_players, graph]
            
        else: # deathmatch 
            temp_list = {}
            for key in players.keys():
                temp_list[key] = players[key]["kills"]

            temp_list2 = sorted(temp_list.items(), key=lambda i: i[1], reverse=True)

            sorted_players = []
            for value in temp_list2:
                sorted_players.append(value[0])
                
            message = ""
            for t_puuid in sorted_players:
                p = players[t_puuid]
                if len(message)!=0:
                    message+="\n"
                message += cls.format_match_playerdata(response.get("PLAYERS", {}).get("DETAIL_DEATHMATCH"), players, t_puuid, match_id, bot)
            embed_players.add_field(name=response.get("PLAYERS", {}).get("DEATHMATCH"), value=message)
            return [embed_players, None]

    def __match_embed_team_stats(cls, title: str, cache: Dict, response: Dict, teams: Dict, players: Dict, team: str, color: str, match_id: str, bot: ValorantBot) -> discord.Embed:
        embed_team = Embed(title=title, color=color)

        for p in teams[team]["players"]:
            n = cls.format_match_playerdata(response.get("STATS",{}).get("TITLE"), players, p, match_id, bot)
            v = cls.format_match_playerdata(response.get("STATS",{}).get("RESPONSE"), players, p, match_id, bot)
            embed_team.add_field(name=n, value=v)
        
        return embed_team

    def __match_embed_economy(cls, cache: Dict, response: Dict, teams: Dict, rounds: Dict, teamA: str, teamB: dict, color: str, bot: ValorantBot) -> List:
        graph = cls.__match_graph(rounds, teamA, teamB)

        message_format = response.get("ECONOMY", {}).get("RESPONSE")
        message_team_format = response.get("ECONOMY", {}).get("RESPONSE_TEAM")

        message = ""
        message_teamA = ""
        message_teamB = ""
        for r in rounds:
            if len(message)!=0:
                message+="\n"
            if len(message_teamA)!=0:
                message_teamA+="\n"
            if len(message_teamB)!=0:
                message_teamB+="\n"
            
            if r["win"]==teamA:
                result_teamA = response["RESULT"]["WIN"]
                result_teamB = response["RESULT"]["LOSE"]
                result_emoji_teamA = GetEmoji.roundresult_by_bot(r["result"], r["win"]==teamA, bot)
                result_emoji_teamB = GetEmoji.roundresult_by_bot(r["result"], r["win"]==teamB, bot)
                result_emoji = GetEmoji.roundresult_by_bot(r["result"], r["win"]==teamA, bot)
            else:
                result_teamA = response["RESULT"]["LOSE"]
                result_teamB = response["RESULT"]["WIN"]
                result_emoji_teamA = GetEmoji.roundresult_by_bot(r["result"], r["win"]==teamA, bot)
                result_emoji_teamB = GetEmoji.roundresult_by_bot(r["result"], r["win"]==teamB, bot)
                result_emoji = GetEmoji.roundresult_by_bot(r["result"], r["win"]==teamA, bot)

            start_teamA = r["economy"][teamA]["spent"] + r["economy"][teamA]["remain"]
            start_teamB = r["economy"][teamB]["spent"] + r["economy"][teamB]["remain"]
            start = start_teamA - start_teamB

            loadout = r["economy"][teamA]["loadout"] - r["economy"][teamB]["loadout"]
            spent = r["economy"][teamA]["spent"] - r["economy"][teamB]["spent"]
            remain = r["economy"][teamA]["remain"] - r["economy"][teamB]["remain"]

            total_teamA = r["economy"][teamA]["loadout"] + r["economy"][teamA]["remain"]
            total_teamB = r["economy"][teamB]["loadout"] + r["economy"][teamB]["remain"]
            total = loadout + remain

            message += message_format.format(
                number=r["number"], align_number=str(r["number"]).ljust(2),
                ceremony=r["ceremony"],
                result_emoji=result_emoji,
                loadout=loadout, align_loadout=str(loadout).rjust(6),
                start=start, align_start=str(start).rjust(6),
                spent=spent, align_spent=str(spent).rjust(6),
                remain=remain, align_remain=str(remain).rjust(6),
                total=total, align_total=str(total).rjust(6)
            )
            message_teamA += message_team_format.format(
                number=r["number"], align_number=str(r["number"]).ljust(2),
                ceremony=r["ceremony"],
                result=result_teamA, result_emoji=result_emoji_teamA,
                loadout=r["economy"][teamA]["loadout"], align_loadout=str(r["economy"][teamA]["loadout"]).rjust(6),
                start=start_teamA, align_start=str(start_teamA).rjust(6),
                spent=r["economy"][teamA]["spent"], align_spent=str(r["economy"][teamA]["spent"]).rjust(6),
                remain=r["economy"][teamA]["remain"], align_remain=str(r["economy"][teamA]["remain"]).rjust(6),
                total=total_teamA, align_total=str(total_teamA).rjust(6)
            )
            message_teamB += message_team_format.format(
                number=r["number"], align_number=str(r["number"]).ljust(2),
                ceremony=r["ceremony"],
                result=result_teamB, result_emoji=result_emoji_teamB,
                loadout=r["economy"][teamB]["loadout"], align_loadout=str(r["economy"][teamB]["loadout"]).rjust(6),
                start=start_teamB, align_start=str(start_teamB).rjust(6),
                spent=r["economy"][teamB]["spent"], align_spent=str(r["economy"][teamB]["spent"]).rjust(6),
                remain=r["economy"][teamB]["remain"], align_remain=str(r["economy"][teamB]["remain"]).rjust(6),
                total=total_teamB, align_total=str(total_teamB).rjust(6)
            )

        description = response.get("ECONOMY", {}).get("TITLE_TEAM_DIFF") + f"\n{message}"
        description_team = response.get("ECONOMY", {}).get("TITLE_TEAM_A") + f"\n{message_teamA}" + "\n\n" + response.get("ECONOMY", {}).get("TITLE_TEAM_B") + f"\n{message_teamB}"

        embed_economy = Embed(title=response.get("ECONOMY", {}).get("TITLE"), description=description, color=color)
        embed_economy_team = Embed(description=description_team, color=color).set_image(url=f"attachment://graph.png")
        return [[embed_economy, embed_economy_team], graph]
    
    @classmethod
    def match(cls, player: str, puuid: str, match_id: str, response: Dict, endpoint, bot: ValorantBot):
        """Embed Match"""
        cache = JSON.read('cache')

        # match info
        match_info = cls.get_match_info(puuid, match_id, endpoint, response)

        # embed
        # first embed post
        description = ""
        if match_info["match_info"]["is_played"]:
            description = cls.format_match_playerdata(response.get("RESPONSE"), match_info["players"], puuid, match_id, bot)
        else:
            description = ""

        title = response.get("TITLE", "").format(
            match_id=match_info["match_info"]["match_id"],
            map=match_info["match_info"]["map"],
            time=match_info["match_info"]["time"],
            point=match_info["match_info"]["point"],
            result=match_info["match_info"]["results"],
            tracker=GetFormat.get_trackergg_link(match_info["match_info"]["match_id"]),
            queue=match_info["match_info"]["queue"],
            duration=match_info["match_info"]["duration"]
        )
        header = response.get("HEADER").format(
            match_id=match_info["match_info"]["match_id"],
            map=match_info["match_info"]["map"],
            time=match_info["match_info"]["time"],
            point=match_info["match_info"]["point"],
            result=match_info["match_info"]["results"],
            tracker=GetFormat.get_trackergg_link(match_info["match_info"]["match_id"]),
            queue=match_info["match_info"]["queue"],
            duration=match_info["match_info"]["duration"]
        )
        footer=response.get("FOOTER").format(
            match_id=match_info["match_info"]["match_id"],
            map=match_info["match_info"]["map"],
            time=match_info["match_info"]["time"],
            point=match_info["match_info"]["point"],
            result=match_info["match_info"]["results"],
            tracker=GetFormat.get_trackergg_link(match_info["match_info"]["match_id"]),
            queue=match_info["match_info"]["queue"],
            duration=match_info["match_info"]["duration"]
        )

        embed_main = Embed(title=title, description=description, color=match_info["match_info"]["color"])
        embed_main.set_author(name=header, icon_url=match_info["match_info"]["gamemode_icon"])
        embed_main.set_footer(text=footer)
        embed_main.set_thumbnail(url=cache["maps"][match_info["match_info"]["map_id"]]["icon"])
        embed_main.set_image(url=cache["maps"][match_info["match_info"]["map_id"]]["listview_icon"])
        
        embed_players = cls.__match_embed_players(cls, cache, response, match_info["teams"], match_info["players"], match_info["match_info"]["teamA"], match_info["match_info"]["teamB"], match_info["match_info"]["color"], match_info["match_info"]["match_id"], bot)
        if len(match_info["teams"])==2: # default
            embed_teamA = cls.__match_embed_team_stats(cls, response.get("TEAM_A"), cache, response, match_info["teams"], match_info["players"], match_info["match_info"]["teamA"], match_info["match_info"]["color"], match_id, bot)
            embed_teamB = cls.__match_embed_team_stats(cls, response.get("TEAM_B"), cache, response, match_info["teams"], match_info["players"], match_info["match_info"]["teamB"], match_info["match_info"]["color"], match_id, bot)
            embed_economy = cls.__match_embed_economy(cls, cache, response, match_info["teams"], match_info["rounds"], match_info["match_info"]["teamA"], match_info["match_info"]["teamB"], match_info["match_info"]["color"], bot)

            cls.__match_heatmap(match_info["players"], match_info["teams"], match_info["match_info"]["teamA"], match_info["match_info"]["teamB"])
            return [[embed_main, embed_players[0], embed_teamA, embed_teamB, embed_economy[0][0], embed_economy[0][1]], [embed_players[1], embed_economy[1]]]
        else:
            return [[embed_main, embed_players[0]], None]

    # ---------- MATCH HISTORY EMBED ---------- #
    
    def __career_embed(cls, match_id: str, match_data: Dict, response: Dict, endpoint, puuid: str, bot: ValorantBot) -> discord.Embed:
        """Generate Embed Career"""
        cache = JSON.read('cache')
        
        # earned rank rating info
        earned_rr = match_data.get("RankedRatingEarned", 0)
        before_rr = match_data.get("RankedRatingBeforeUpdate", 0)
        after_rr = match_data.get("RankedRatingAfterUpdate", 0)
        before_rank = match_data.get("TierBeforeUpdate", 0)
        after_rank = match_data.get("TierAfterUpdate", 0)

        # data
        match_detail = cls.get_match_info(puuid, match_id, endpoint, response)

        def match_format(format: str):
            players = match_detail["players"]
            info = match_detail["match_info"]
            return format.format(
                tracker=GetFormat.get_trackergg_link(match_id),

                puuid=puuid,
                name=players[puuid]["name"],
                rank=players[puuid]["rank"],
                level=players[puuid]["level"],
                agent=players[puuid]["agent"],
                agent_emoji=GetEmoji.agent_by_bot(players[puuid]["agent_id"], bot),
                role=players[puuid]["role"],
                role_emoji=GetEmoji.role_by_bot(players[puuid]["agent_id"], bot),
                kills=players[puuid]["kills"],
                deaths=players[puuid]["deaths"],
                assists=players[puuid]["assists"],
                kd=players[puuid]["kd"],
                kda=players[puuid]["kda"],
                acs=players[puuid]["acs"],

                eco_rating=players[puuid]["eco_rating"],
                damage=players[puuid]["damage"],
                adr=players[puuid]["adr"],
                
                headshots=players[puuid]["headshots"],
                bodyshots=players[puuid]["bodyshots"],
                legshots=players[puuid]["legshots"],
                hsrate=players[puuid]["hsrate"],
                bsrate=players[puuid]["bsrate"],
                lsrate=players[puuid]["lsrate"],

                firstblood=players[puuid]["firstblood"],
                firstdeath=players[puuid]["firstdeath"],
                multikills=players[puuid]["multikills"],
                deathmatch=players[puuid]["deathmatch"],

                map = info["map"],
                match_id = info["match_id"],
                queue = info["queue"],
                point = info["point"],
                time = info["time"],
                duration = info["duration"],
                result = info["results"],

                earned_rr = earned_rr,
                before_rr = before_rr,
                after_rr = after_rr,
                before_rank = GetFormat.get_competitive_tier_name(before_rank),
                after_rank = GetFormat.get_competitive_tier_name(after_rank)
            )

        if match_detail!=None:
            # embed
            embed = Embed(title=match_format(response.get('TITLE')), color=match_detail["match_info"]["color"])
            if len(match_detail["teams"])==2:
                embed.add_field(name=match_format(response.get('RANK')["TITLE"]), value=match_format(response.get('RANK')["RESPONSE"]), inline=False)
                embed.add_field(name=match_format(response.get("RESULT")["TITLE"]), value=match_format(response.get("RESULT")["RESPONSE"]))
            else:
                embed.add_field(name=match_format(response.get("RESULT")["TITLE"]), value=match_format(response.get("RESULT")["DEATHMATCH"]))
            embed.set_author(name=match_format(response.get("HEADER")), icon_url=match_detail["match_info"]["gamemode_icon"])
            embed.set_footer(text=match_format(response.get("FOOTER")))

            embed.set_thumbnail(url=cache["maps"][match_detail["match_info"]["map_id"]]["icon"])
            embed.set_image(url=cache["maps"][match_detail["match_info"]["map_id"]]["listview_icon"])

            # return stats
            ret_stats = {
                "kills": match_detail["players"][puuid]["kills"],
                "deaths": match_detail["players"][puuid]["deaths"],
                "assists": match_detail["players"][puuid]["assists"],
                "win": 1 if match_detail["match_info"]["results"]==response.get("RESULT", {}).get("WIN") else 0,
                "lose": 1 if match_detail["match_info"]["results"]==response.get("RESULT", {}).get("LOSE") else 0,
                "draw": 1 if match_detail["match_info"]["results"]==response.get("RESULT", {}).get("DRAW") else 0,
                "acs": match_detail["players"][puuid]["acs"],
                "earned_rr": earned_rr,
                "rr": [before_rr, after_rr],
                "rank": [before_rank, after_rank]
            }

            return [embed, ret_stats]
        else:
            return None
    
    @classmethod
    def career(cls, player: str, puuid: str, history: Dict, response: Dict, endpoint, queue: str, bot: ValorantBot) -> discord.Embed:
        """Embed Match"""
        
        # language
        msg_response = response.get('STATS')
        
        # data
        if history==None:
            history = {}
        matches = history.get("Matches", {})
        
        # embed
        all_match_stats = []
        embeds = []
        i = 0
        for match in matches:
            ret = cls.__career_embed(cls, match["MatchID"], matches[i], response, endpoint, puuid, bot)
            if ret!=None:
                embeds.append(ret[0])
                all_match_stats.append(ret[1])
            i += 1

        # stats of all matches 
        all_matches = len(embeds)
        if all_matches>0:
            match_stats = {
                "kills": 0,
                "deaths": 0,
                "assists": 0,
                "acs": 0,
                "win": 0,
                "lose": 0,
                "draw": 0,
                "earned_rr": 0
            }
            for stats in all_match_stats:
                match_stats["kills"] += stats["kills"]
                match_stats["deaths"] += stats["deaths"]
                match_stats["assists"] += stats["assists"]
                match_stats["acs"] += stats["acs"]
                match_stats["earned_rr"] += stats["earned_rr"]
                match_stats["win"] += stats["win"]
                match_stats["lose"] += stats["lose"]
                match_stats["draw"] += stats["draw"]

            match_stats["acs"] = round(match_stats["acs"] / all_matches)
            match_stats["before_rank"] = GetFormat.get_competitive_tier_name(all_match_stats[all_matches-1]["rank"][0])
            match_stats["after_rank"] = GetFormat.get_competitive_tier_name(all_match_stats[0]["rank"][1])
            match_stats["before_raw_rank"] = all_match_stats[all_matches-1]["rank"][0]
            match_stats["after_raw_rank"] = all_match_stats[0]["rank"][1]
            match_stats["before_rr"] = all_match_stats[all_matches-1]["rr"][0]
            match_stats["after_rr"] = all_match_stats[0]["rr"][1]

            if match_stats["before_raw_rank"]>=3:
                rr = match_stats["after_rr"] + (100 * (match_stats["after_raw_rank"] - match_stats["before_raw_rank"])) - match_stats["before_rr"]
            else: # unranked
                rr = match_stats["earned_rr"]

            if match_stats["earned_rr"]>=0:
                match_stats["earned_rr"] = "+" + str(match_stats["earned_rr"])
            else:
                match_stats["earned_rr"] = str(match_stats["earned_rr"])

            if rr>=0:
                rr = "+" + str(rr)
            else:
                rr = str(rr)

        
            # make embed post
            def format_main(format: str) -> str:
                return format.format(
                    name=player,
                    matches = all_matches,

                    win = match_stats["win"],
                    lose = match_stats["lose"],
                    draw = match_stats["draw"],
                    win_rate = round((float(match_stats["win"]) / float(all_matches)) * 100.0),

                    acs = match_stats["acs"],
                    kills = match_stats["kills"],
                    deaths = match_stats["deaths"],
                    assists = match_stats["assists"],
                    kd = GetFormat.get_kdrate(match_stats["kills"], match_stats["deaths"]),
                    kda = GetFormat.get_kdarate(match_stats["kills"], match_stats["deaths"], match_stats["assists"]),

                    before_rank = match_stats["before_rank"],
                    after_rank = match_stats["after_rank"],
                    before_rr = match_stats["before_rr"],
                    after_rr = match_stats["after_rr"],
                    earned_rr = match_stats["earned_rr"],
                    rr = rr
                )

            embed = Embed(title=format_main(response.get("STATS", {}).get('TITLE')), description=format_main(response.get("STATS", {}).get('RESPONSE')))
            embed.set_author(name=response.get("STATS", {}).get('HEADER'))
            embed.set_footer(text=response.get("STATS", {}).get('FOOTER'))
        else:
            def format_main(format: str) -> str:
                return format.format(
                    name=player,
                )

            embed = Embed(title=format_main(response.get("STATS", {}).get('TITLE')), description=response.get("STATS", {}).get('NO_MATCH'))
            embed.set_author(name=response.get("STATS", {}).get('HEADER'))
            embed.set_footer(text=response.get("STATS", {}).get('FOOTER'))
        embeds.insert(0, embed)

        return embeds

    # ---------- NIGHT MARKET EMBED ---------- #
    
    def __nightmarket_embed(skins: Dict, bot: ValorantBot) -> discord.Embed:
        """Generate Embed Night Market"""
        
        uuid, name, icon, price, dpice = skins['uuid'], skins['name'], skins['icon'], skins['price'], skins['disprice']
        
        vp_emoji = GetEmoji.point_by_bot('ValorantPointIcon', bot)
        
        embed = Embed(f"{GetEmoji.tier(uuid)} **{name}**\n{vp_emoji} {dpice} ~~{price}~~", color=0x0F1923)
        embed.set_thumbnail(url=icon)
        return embed
    
    @classmethod
    def nightmarket(cls, player: str, offer: Dict, bot: ValorantBot, response: Dict) -> discord.Embed:
        """Embed Night Market"""
        
        # language
        msg_response = response.get('RESPONSE')
        
        night_mk = GetFormat.nightmarket_format(offer, response)
        skins = night_mk['nightmarket']
        duration = night_mk['duration']
        
        description = msg_response.format(username=player, duration=format_relative(datetime.utcnow() + timedelta(seconds=duration)))
        
        embed = Embed(description)
        
        embeds = [embed]
        [embeds.append(cls.__nightmarket_embed(skins[skin], bot)) for skin in skins]
        
        return embeds
    
    # ---------- BATTLEPASS EMBED ---------- #
    
    def battlepass(player: str, data: Dict, season: Dict, response: Dict) -> discord.Embed:
        """Embed Battle-pass"""
        
        # language
        MSG_RESPONSE = response.get('RESPONSE')
        MSG_TIER = response.get('TIER')
        
        BTP = GetFormat.battlepass_format(data, season, response)
        
        item = BTP['data']
        reward = item['reward']
        xp = item['xp']
        act = item['act']
        tier = item['tier']
        icon = item['icon']
        season_end = item['end']
        item_type = item['type']
        original_type = item['original_type']
        
        description = MSG_RESPONSE.format(next=f'`{reward}`', type=f'`{item_type}`', xp=f'`{xp:,}/{calculate_level_xp(tier + 1):,}`', end=format_relative(season_end))
        
        embed = Embed(description, title=f"BATTLEPASS")
        
        if icon:
            if original_type in ['PlayerCard', 'EquippableSkinLevel']:
                embed.set_image(url=icon)
            else:
                embed.set_thumbnail(url=icon)
        
        if tier >= 50:
            embed.color = 0xf1b82d
        
        if tier == 55:
            embed.description = str(reward)
        
        embed.set_footer(text=f"{MSG_TIER} {tier} | {act}\n{player}")
        
        return embed
    
    # ---------- PARTY EMBED ---------- #
    
    def party(player: str, puuid: str, data: Dict, endpoint: API_ENDPOINT, response: Dict) -> discord.Embed:
        cache = JSON.read("cache")

        # values
        # is this custome game ?
        is_custom_game = False
        if data["State"]=="CUSTOM_GAME_SETUP" or data["State"]=="CUSTOM_GAME_STARTING":
            is_custom_game = True

        # player data
        owner = {}
        players = {}
        for p in data["Members"]:
            # fetch mmr
            p_puuid = p["Subject"]
            mmr = endpoint.fetch_player_mmr(p_puuid)

            season_id = mmr['LatestCompetitiveUpdate']['SeasonID']
            if season_id==None:
                season_id = ""
            if len(season_id) == 0:
                season_id = endpoint.__get_live_season()

            # player data
            current_season = mmr["QueueSkills"]['competitive']['SeasonalInfoBySeasonID']
            name_data = endpoint.fetch_name_by_puuid(p_puuid)

            # set data to dict
            players[p_puuid] = {
                "name": name_data[0]["GameName"] + "#" + name_data[0]["TagLine"],
                "puuid": p_puuid,
                "player_card": p["PlayerIdentity"]["PlayerCardID"],
                "player_title": p["PlayerIdentity"]["PlayerTitleID"],
                "level": p["PlayerIdentity"]["AccountLevel"],
                "rank": current_season[season_id]['CompetitiveTier'],
                "rr": current_season[season_id]['RankedRating'],
                "leaderboard": current_season[season_id]["LeaderboardRank"] if current_season[season_id]["LeaderboardRank"]>0 else "-",
                "ready": response.get("READY") if p["IsReady"] else response.get("NO_READY"),
                "owner": response.get("OWNER") if p.get("IsOwner", False) else "",
                "membership": response.get("MEMBERSHIP", {}).get("DEFAULT")
            }


        # embeds
        embeds = []

        # main embed
        def format_party_info(format: str) -> str:
            return format.format(
                name = player,
                puuid = puuid,
                access = response.get("ACCESS", {}).get(data["Accessibility"]),
                party_id = data["ID"],

                queue_id = data["MatchmakingData"]["QueueID"] if not is_custom_game else "custom",
                queue = response.get("QUEUE", {}).get(data["MatchmakingData"]["QueueID"])if not is_custom_game else response.get("QUEUE", {}).get("custom"),
                members = len(data["Members"]),
                in_queue = format_relative(dateutil.parser.parse(data["QueueEntryTime"])) if data["QueueEntryTime"]!="0001-01-01T00:00:00Z" else "",
                owner_icon = response.get("OWNER")
            )
        embed_main = Embed(
            title = format_party_info(response.get("TITLE", "")),
            description = format_party_info(response.get("RESPONSE", ""))
        )

        # player embed
        def format_player_info(format: str, p_puuid: str, name: str = response.get("")) -> str:
            return format.format(
                name = players[p_puuid]["name"],
                level = players[p_puuid]["level"],
                rank = GetFormat.get_competitive_tier_name(players[p_puuid]["rank"]),
                rr = players[p_puuid]["rr"],
                leaderboard = players[p_puuid]["leaderboard"],
                ready = players[p_puuid]["ready"],
                owner = players[p_puuid]["owner"],
                playercard = cache["playercards"][players[p_puuid]["player_card"]]["names"][str(VLR_locale)],
                title = cache["titles"][players[p_puuid]["player_title"]]["text"][str(VLR_locale)],
                membership = players[p_puuid]["membership"]
            )

        if is_custom_game:
            def make_embed(p_puuid: str, membership: str, color: int = 0x0F1923):
                players[p_puuid]["membership"] = membership
                embed_player = Embed(
                    title=format_player_info(response.get("CUSTOM", {}).get("TITLE"), p_puuid),
                    description=format_player_info(response.get("CUSTOM", {}).get("RESPONSE"), p_puuid),
                    color = color
                )
                embed_player.set_thumbnail(url=cache["playercards"][players[p_puuid]["player_card"]]["icon"]["small"])
                embed_player.set_author(
                    name=format_player_info(response.get("CUSTOM", {}).get("HEADER"), p_puuid),
                    icon_url=cache["competitive_tiers"][str(players[p_puuid]["rank"])]["icon"]
                )
                embed_player.set_footer(text=format_player_info(response.get("CUSTOM", {}).get("FOOTER"), p_puuid))
                return embed_player

            for p in data["CustomGameData"]["Membership"].get("teamOne", []):
                embeds.append(make_embed(p["Subject"], response.get("MEMBERSHIP", {}).get("TEAM_B"), 0x3cb371))
            for p in data["CustomGameData"]["Membership"].get("teamTwo", []):
                embeds.append(make_embed(p["Subject"], response.get("MEMBERSHIP", {}).get("TEAM_A"), 0xff0000))
            for p in data["CustomGameData"]["Membership"].get("teamOneCoaches", []):
                embeds.append(make_embed(p["Subject"], response.get("MEMBERSHIP", {}).get("COACH_B"), 0x3cb371))
            for p in data["CustomGameData"]["Membership"].get("teamTwoCoaches", []):
                embeds.append(make_embed(p["Subject"], response.get("MEMBERSHIP", {}).get("COACH_A"), 0xff0000))
            for p in data["CustomGameData"]["Membership"].get("teamSpectate", []):
                embeds.append(make_embed(p["Subject"], response.get("MEMBERSHIP", {}).get("SPECTATE"), 0x4169e1))
                
        else:
            for p in players.values():
                p_puuid = p["puuid"]
                embed_player = Embed(
                    title=format_player_info(response.get("PLAYER", {}).get("TITLE"), p_puuid),
                    description=format_player_info(response.get("PLAYER", {}).get("RESPONSE"), p_puuid),
                    color = 0x0F1923
                )
                embed_player.set_thumbnail(url=cache["playercards"][players[p_puuid]["player_card"]]["icon"]["small"])
                embed_player.set_author(
                    name=format_player_info(response.get("PLAYER", {}).get("HEADER"), p_puuid),
                    icon_url=cache["competitive_tiers"][str(players[p_puuid]["rank"])]["icon"]
                )
                embed_player.set_footer(text=format_player_info(response.get("PLAYER", {}).get("FOOTER"), p_puuid))
                embeds.append(embed_player)

        return [embed_main, embeds]


    # ---------- CUSTOM EMBED ---------- #
    @classmethod
    def custom(cls, puuid: str, data: Dict, endpoint: API_ENDPOINT, response: Dict, mode_rand: bool = False) -> discord.Embed:
        cache = JSON.read("cache")
        
        # Select Maps
        maps_c = cache["maps"]
        maps = []

        for m in maps_c.values():
            maps.append(m)
        

        # Select Team Member
        teamA_members = data.get("CustomGameData", {}).get("Membership", {}).get("teamOne", [])
        teamB_members = data.get("CustomGameData", {}).get("Membership", {}).get("teamTwo", [])

        if teamA_members==None:
            teamA_members = []
        if teamB_members==None:
            teamB_members = []

        #if len(teamA_members)+len(teamB_members)<=0:
        #    raise ValorantBotError(response.get("NOT_CUSTOM_MODE"))

        # player data
        players = {}
        players_data_list = []
        for p in (teamA_members + teamB_members):
            # fetch mmr
            p_puuid = p["Subject"]
            mmr = endpoint.fetch_player_mmr(p_puuid)

            season_id = mmr['LatestCompetitiveUpdate']['SeasonID']
            if season_id==None:
                season_id = ""
            if len(season_id) == 0:
                season_id = endpoint.__get_live_season()

            # player data
            current_season = mmr["QueueSkills"]['competitive']['SeasonalInfoBySeasonID']

            # set data to dict
            player = {
                "name": "",
                "user": "",
                "puuid": p_puuid,
                "rank": current_season[season_id]['CompetitiveTier'],
                "rr": current_season[season_id]['RankedRating'],
                "leaderboard": current_season[season_id]["LeaderboardRank"] if current_season[season_id]["LeaderboardRank"]>0 else "-",
                "membership": response.get("MEMBERSHIP", {}).get("DEFAULT"),

                "kda": 0,
                "acs": 0,
                "eco_rating": 0,
                "adr": 0,
                "custom_rating": 0
            }

            rank_weight = [
                50, 50, 50, # Unrated & Unused
                0.3, 1.5, 6.6, # Iron
                11.6, 19.8, 27.0, # Bronze
                37.5, 45.6, 53.3, # Silver
                60.7, 67.4, 73.5, # Gold
                79.1, 83.7, 87.9, # Platinum
                91.6, 94.2, 96.0, # Diamond
                97.4, 98.3, 98.8, # Ascendant
                99.1, 99.2, 99.3, # Immortal
                100 # Radiant
            ]

            data = endpoint.fetch_match_history(index=5, puuid=p_puuid, not_found_error=False, queue="competitive")["Matches"]
            size = 0
            if len(data)<1:
                player["custom_rating"] = -1
            else:
                for d in data:
                    match_id = d["MatchID"]

                    match_info = cls.get_match_info(p_puuid, match_id, endpoint, response)

                    player_data = match_info["players"].get(p_puuid)
                    if player_data==None:
                        continue
                    
                    player["name"] = player_data["name"]
                    player["kda"] += player_data["kda"]
                    player["acs"] += player_data["acs"]
                    player["eco_rating"] += player_data["eco_rating"]
                    player["adr"] += player_data["adr"]
                    size += 1

                player["kda"] /= size
                player["acs"] /= size
                player["eco_rating"] /= size
                player["adr"] /= size
            
            rating = (player["kda"]*0.3) * (player["acs"] / 200 * 0.4) * (player["eco_rating"]/50 * 0.2) * (player["adr"] / 150 * 0.2) * (rank_weight[player["rank"]]/100* 0.8) * 1000
            player["custom_rating"] = rating
            players_data_list.append(player)

            user_id = endpoint.get_discord_userid_from_puuid(p_puuid)
            if len(user_id)>0:
                player["user"] = f"<@{user_id}>"



        sorted_players = sorted(players_data_list, key=lambda x: x.get('custom_rating', 0), reverse=True)
        
        def format_team_description(format: str, player_data: Dict):
            return format.format(
                name = player_data["name"],
                puuid = player_data["puuid"],
                rank = GetFormat.get_competitive_tier_name(player_data["rank"]),
                rating = round(player_data["custom_rating"], 1),
                user = player_data["user"]
            )

        members = len(sorted_players)
        member = [0, 0, 0, 0]

        if members%2==1:
            member[2] = math.floor(members / 2) + 1
            member[3] = math.floor(members / 2)
        else:
            member[2] = math.floor(members / 2)
            member[3] = math.floor(members / 2)

        teamA_description, teamB_description = "", ""
        if mode_rand:
            i = 0
            for p in sorted_players:
                r = random.random()

                if (r<=0.3 and member[0]<member[2]) or (i%2==0 and member[0]<member[2]):
                    if len(teamA_description)!=0:
                        teamA_description += "\n"
                    teamA_description += format_team_description(response.get("MEMBER"), p)
                    member[0] += 1
                else:
                    if len(teamB_description)!=0:
                        teamB_description += "\n"
                    teamB_description += format_team_description(response.get("MEMBER"), p)
                    member[1] += 1
                i += 1
        else:
            i = 0
            for p in sorted_players:
                r = random.random()

                if i%2==0:
                    if len(teamA_description)!=0:
                        teamA_description += "\n"
                    teamA_description += format_team_description(response.get("MEMBER"), p)
                    member[0] += 1
                else:
                    if len(teamB_description)!=0:
                        teamB_description += "\n"
                    teamB_description += format_team_description(response.get("MEMBER"), p)
                    member[1] += 1

                i += 1
        
        if len(teamA_description)==0:
            teamA_description = response.get("NO_MEMBER")
        if len(teamB_description)==0:
            teamB_description = response.get("NO_MEMBER")

        # Embed
        embed_team = Embed(title=response.get("TITLE", {}).get("TEAM"))
        embed_team.add_field(name=response.get("TEAM_A"), value=teamA_description, inline=False)
        embed_team.add_field(name=response.get("TEAM_B"), value=teamB_description, inline=False)
        
        r = random.randint(0, len(maps)-1)
        description = response.get("MAP", "").format(
            name = maps[r]["name"][str(VLR_locale)],
            coordinate = maps[r]["coordinates"][str(VLR_locale)],
        )

        embed_map = Embed(title=response.get("TITLE", {}).get("MAP"), description=description)
        embed_map.set_thumbnail(url=maps[r]["icon"])
        embed_map.set_image(url=maps[r]["listview_icon"])

        return [embed_map, embed_team]



    # ---------- NOTIFY EMBED ---------- #
    
    def notify_specified_send(uuid: str) -> discord.Embed:
        ...
    
    @classmethod
    def notify_all_send(cls, player: str, offer: Dict, response: Dict, bot: ValorantBot) -> discord.Embed:
        
        description_format = response.get('RESPONSE_ALL')
        
        data = GetFormat.offer_format(offer)
        
        duration = data.pop('duration')
        
        description = description_format.format(username=player, duration=format_relative(datetime.utcnow() + timedelta(seconds=duration)))
        embed = Embed(description)
        embeds = [embed]
        [embeds.append(cls.__giorgio_embed(data[skin], bot, response)) for skin in data]
        
        return embeds
