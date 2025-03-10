from __future__ import annotations

import contextlib
from datetime import datetime, timezone, timedelta
from turtle import title
import dateutil.parser
import json, os, io, concurrent.futures
from PIL import Image, ImageDraw, ImageFont
import matplotlib.colors, matplotlib.font_manager as fm
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING
import uuid

import discord

import utils.config as Config
from .resources import get_item_type, tiers as tiers_resources
from ..errors import ValorantBotError
from ..locale_v2 import ValorantTranslator

VLR_locale = ValorantTranslator()

if TYPE_CHECKING:
    from bot import ValorantBot

current_season_id = '99ac9283-4dd3-5248-2e01-8baf778affb4'
current_season_end = datetime(2022, 8, 24, 17, 0, 0)

def load_file(dir: str, filename: str = "image.png") -> discord.File:
    with open(dir, "rb") as f:
        file = io.BytesIO(f.read())
    f.close()
    image = discord.File(file, filename=f"{filename}")
    return image

def is_valid_uuid(value: str) -> bool:
    """
    Checks if a string is a valid UUID.
    """
    try:
        uuid.UUID(value)
        return True
    except ValueError:
        return False


# ---------- ACT SEASON ---------- #

def get_season_by_content(content: Dict) -> Tuple[str, str]:
    """Get season id by content"""

    try:
        season_data = [season for season in content["Seasons"] if season["IsActive"] and season["Type"] == "act"]
        season_id = season_data[0]['ID']
        season_end = iso_to_time(season_data[0]['EndTime'])

    except (IndexError, KeyError, TypeError):
        season_id =  current_season_id
        season_end = current_season_end

    return {'id': season_id, 'end': season_end}


def calculate_level_xp(level: int) -> int:  # https://github.com/giorgi-o
    """Calculate XP needed to reach a level"""

    level_multiplier = 750
    if 2 <= level <= 50:
        return 2000 + (level - 2) * level_multiplier
    elif 51 <= level <= 55:
        return 36500
    else:
        return 0


# ---------- TIME UTILS ---------- #

def iso_to_time(iso: datetime) -> datetime:
    """Convert ISO time to datetime"""
    timestamp = datetime.strptime(iso, "%Y-%m-%dT%H:%M:%S%z").timestamp()
    time = datetime.utcfromtimestamp(timestamp)
    return time


def format_dt(dt: datetime, style: str = None) -> str:  # style 'R' or 'd'
    """datatime to time format"""

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    if style is None:
        return f'<t:{int(dt.timestamp())}>'
    return f'<t:{int(dt.timestamp())}:{style}>'


def format_relative(dt: datetime) -> str:
    """ datatime to relative time format """
    return format_dt(dt, 'R')

def format_timedelta(timedelta: timedelta) -> str:
    total_sec = timedelta.total_seconds()

    hours = total_sec // 3600 
    remain = total_sec - (hours * 3600)
     
    minutes = remain // 60
    seconds = remain - (minutes * 60)

    # total time
    return '{:02}:{:02}:{:02}'.format(int(hours), int(minutes), int(seconds))

# ---------- JSON LOADER ---------- #

def data_folder() -> None:
    """ Get the data folder """
    # create data folder
    current_directory = os.getcwd()
    final_directory = os.path.join(current_directory, r'data')
    if not os.path.exists(final_directory):
        os.makedirs(final_directory)


class JSON:

    def read(filename: str, force: bool = True, dir: str = "data") -> Dict:
        """Read json file"""
        try:
            with open(dir + "/" + filename + ".json", "r", encoding='utf-8') as json_file:
                data = json.load(json_file)
        except FileNotFoundError:
            from .cache import create_json
            if force:
                create_json(filename, {})
                return JSON.read(filename, False)
        return data

    def save(filename: str, data: Dict, dir: str = "data") -> None:
        """Save data to json file"""
        try:
            with open(dir + "/" + filename + ".json", 'w', encoding='utf-8') as json_file:
                json.dump(data, json_file, indent=2, ensure_ascii=False)
        except FileNotFoundError:
            from .cache import create_json
            create_json(filename, {})
            return JSON.save(filename, data)


# ---------- GET DATA ---------- #

class GetItems:

    @classmethod
    def get_item_by_type(cls, Itemtype: str, uuid: str) -> Dict[str, Any]:
        """ Get item by type """

        item_type = get_item_type(Itemtype)
        if item_type == 'Agents':
            ...
        elif item_type == 'Contracts':
            return cls.get_contract(uuid)
        elif item_type == 'Sprays':
            return cls.get_spray(uuid)
        elif item_type == 'Gun Buddies':
            return cls.get_buddie(uuid)
        elif item_type == 'Player Cards':
            return cls.get_playercard(uuid)
        elif item_type == 'Skins':
            return cls.get_skin(uuid)
        elif item_type == 'Skins chroma':
            ...
        elif item_type == 'Player titles':
            return cls.get_title(uuid)

    def get_skin(uuid: str) -> Dict[str, Any]:
        """Get Skin data"""
        try:

            skin_data = JSON.read('cache')
            skin = skin_data["skins"][uuid]
        except KeyError:
            raise ValorantBotError('Some skin data is missing, plz use `/debug cache`')
        return skin

    def get_skin_price(uuid: str) -> str:
        """Get Skin price by skin uuid"""

        data = JSON.read('cache')
        price = data["prices"]
        try:
            cost = price[uuid]
        except:
            cost = '-'
        return cost

    def get_skin_tier_icon(skin: str) -> str:
        """Get Skin skin tier image"""

        skindata = JSON.read('cache')
        tier_uuid = skindata["skins"][skin]['tier']
        tier = skindata['tiers'][tier_uuid]["icon"]
        return tier

    def get_spray(uuid: str) -> Dict[str, Any]:
        """Get Spray"""

        data = JSON.read('cache')
        spray = None
        with contextlib.suppress(Exception):
            spray = data["sprays"][uuid]
        return spray

    def get_title(uuid: str) -> Dict[str, Any]:
        """Get Title"""

        data = JSON.read('cache')
        title = None
        with contextlib.suppress(Exception):
            title = data["titles"][uuid]
        return title

    def get_playercard(uuid: str) -> Dict[str, Any]:
        """Get Player card"""

        data = JSON.read('cache')
        title = None
        with contextlib.suppress(Exception):
            title = data["playercards"][uuid]
        return title

    def get_buddie(uuid: str) -> Dict:
        """Get Buddie"""

        data = JSON.read('cache')
        title = None
        with contextlib.suppress(Exception):
            title = data["buddies"][uuid]
        return title

    def get_skin_lvl_or_name(name: str, uuid: str) -> Dict[str, Any]:
        """Get Skin uuid by name"""

        data = JSON.read('cache')
        skin = None
        with contextlib.suppress(Exception):
            skin = data["skins"][uuid]
        with contextlib.suppress(Exception):
            if skin is None:
                skin = [data["skins"][x] for x in data["skins"] if data["skins"][x]['name'] in name][0]
        return skin

    def get_tier_name(skin_uuid: str) -> Optional[str]:
        """ Get tier name by skin uuid """

        try:
            data = JSON.read('cache')
            uuid = data['skins'][skin_uuid]['tier']
            name = data['tiers'][uuid]['name']
        except KeyError:
            raise ValorantBotError('Some skin data is missing, plz use `/debug cache`')
        return name
    
    def get_title_name(title_uuid: str, locale: str, is_block: bool = False) -> Optional[str]:
        if locale == None:
            locale = str(VLR_locale)

        try:
            cache = JSON.read('cache')
            name = cache["titles"][title_uuid]["text"][locale] if cache["titles"][title_uuid]["text"]!=None else ""

            if is_block and len(name)>0:
                name = f"`{name}`"
        except KeyError:
            raise ValorantBotError('This title was not found.')
        return name

    def get_contract(uuid: str) -> Dict[str, Any]:
        """ Get contract by uuid """

        data = JSON.read('cache')
        contract = None
        with contextlib.suppress(Exception):
            contract = data["contracts"][uuid]
        return contract

    def get_bundle(uuid: str) -> Dict[str, Any]:
        """ Get bundle by uuid """

        data = JSON.read('cache')
        bundle = None
        with contextlib.suppress(Exception):
            bundle = data["bundles"][uuid]
        return bundle    
    
    def get_current_event(date: datetime = datetime.now(timezone.utc)) -> List:
        events = JSON.read("cache").get("events", {})

        ret = []
        for event in events.values():
            start, end = dateutil.parser.parse(event["start"]), dateutil.parser.parse(event["end"])

            if start <= date <= end:
                ret.append(event["uuid"])

        return ret
    
    def is_owns(entitlements: Dict, uuid: str, type_id: str) -> bool:
        for entitlement in entitlements[0].get("EntitlementsByTypes"):
            if entitlement["ItemTypeID"] == type_id:
                for item in entitlement["Entitlements"]:
                    if item["ItemID"]==uuid:
                        return True
        return False
    
    def get_title_icon() -> str:
        return "https://valorantinfo.com/images/us/team-player-title_valorant_icon_33436.webp"

    def get_act_rank_border(actrank: int = 0) -> str:
        if actrank == 0 or actrank == 1:
            return "https://static.wikia.nocookie.net/valorant/images/2/2a/ActRank_lvl1.png"
        elif actrank == 2:
            return "https://static.wikia.nocookie.net/valorant/images/9/9c/ActRank_lvl2.png"
        elif actrank == 3:
            return "https://static.wikia.nocookie.net/valorant/images/7/7b/ActRank_lvl3.png"
        elif actrank == 4:
            return "https://static.wikia.nocookie.net/valorant/images/9/9f/ActRank_lvl4.png"
        elif actrank == 5:
            return "https://static.wikia.nocookie.net/valorant/images/b/b4/ActRank_lvl5.png"

    @classmethod
    def is_skin_owns(cls, entitlements: Dict, uuid: str) -> bool:
        return cls.is_owns(entitlements, uuid, "e7c63390-eda7-46e0-bb7a-a6abdacd2433")
    
    @classmethod
    def is_skin_variant_owns(cls, entitlements: Dict, uuid: str) -> bool:
        return cls.is_owns(entitlements, uuid, "3ad1b2b2-acdb-4524-852f-954a76ddae0a")
    
    def is_agent_owns(entitlements: Dict, uuid: str) -> bool:
        type_id = "01bb38e1-da47-4e6a-9b3d-945fe4655707"
        for entitlement in entitlements.get("EntitlementsByTypes"):
            if entitlement["ItemTypeID"] == type_id:
                for item in entitlement["Entitlements"]:
                    if item["ItemID"]==uuid:
                        return True
        return False
    
    @classmethod
    def is_spray_owns(cls, entitlements: Dict, uuid: str) -> bool:
        return cls.is_owns(entitlements, uuid, "d5f120f8-ff8c-4aac-92ea-f2b5acbe9475")
    
    @classmethod
    def is_playercard_owns(cls, entitlements: Dict, uuid: str) -> bool:
        return cls.is_owns(entitlements, uuid, "3f296c07-64c3-494c-923b-fe692a4fa1bd")
    
    @classmethod
    def is_buddy_owns(cls, entitlements: Dict, uuid: str) -> bool:
        return cls.is_owns(entitlements, uuid, "dd3bf334-87f3-40bd-b043-682a57a8dc3a")
        
    @classmethod
    def is_title_owns(cls, entitlements: Dict, uuid: str) -> bool:
        return cls.is_owns(entitlements, uuid, "de7caa6b-adf7-4588-bbd1-143831e786c6")


# ---------- GET EMOJI ---------- #

class GetEmoji:

    def tier(skin_uuid: str) -> discord.Emoji:
        """ Get tier emoji """

        data = JSON.read('cache')
        emoji_list = JSON.read('emoji')
        uuid = data['skins'][skin_uuid]['tier']
        uuid = data['tiers'][uuid]['uuid']
        emoji = emoji_list.get(tiers_resources[uuid]['emoji'], "")
        return emoji

    @classmethod
    def tier_by_bot(cls, skin_uuid: str, bot: ValorantBot) -> discord.Emoji:
        """ Get tier emoji from bot """

        emoji = discord.utils.get(bot.emojis, name=GetItems.get_tier_name(skin_uuid) + 'Tier')
        if emoji is None:
            return cls.tier(skin_uuid)
        return emoji

    def point_by_bot(point: str, bot: ValorantBot) -> discord.Emoji:
        """ Get point emoji from bot"""
        emoji_list = JSON.read("emoji")

        emoji = discord.utils.get(bot.emojis, name=point)
        if emoji is None:
            return emoji_list.get(point)
        return emoji
    
    def roundresult_by_bot(result: str, win: bool, bot: ValorantBot) -> discord.Emoji:
        """ Get round result icon from bot"""
        emoji_list = JSON.read("emoji")

        if win:
            name="Won"
        else:
            name="Lost"

        if result == "Elimination":
            name = result+name
        elif result == "Defuse":
            name = result+name
        elif result == "Detonate":
            name = result+name
        elif result == "" or result=="Timeup":
            name = "Timeup"+name

        emoji = discord.utils.get(bot.emojis, name=name)
        if emoji is None:
            return emoji_list.get(name, "")
        return emoji
    
    def agent_by_bot(agent_id: str, bot: ValorantBot) -> discord.Emoji:
        """ Get agent emoji from bot"""
        agent = JSON.read("cache")["agents"]
        emoji_list = JSON.read("emoji")

        name = "Agent" + agent[agent_id]["names"]["en-US"].replace("/", "")

        emoji = discord.utils.get(bot.emojis, name=name)
        if emoji is None:
            return emoji_list.get(name)
        return emoji
    
    def role_by_bot(agent_id: str, bot: ValorantBot) -> discord.Emoji:
        """ Get agent role from bot"""
        agent = JSON.read("cache")["agents"]
        emoji_list = JSON.read("emoji")

        name = agent[agent_id]["role"]["names"]["en-US"]

        emoji = discord.utils.get(bot.emojis, name=name)
        if emoji is None:
            return emoji_list.get(name)
        return emoji
    
    def competitive_tier_by_bot(tier: int, bot: ValorantBot) -> discord.Emoji:
        """ Get agent emoji from bot"""
        rank = JSON.read("cache")["competitive_tiers"]
        emoji_list = JSON.read("emoji")

        name = "Tier" + rank[str(tier)]["names"]["en-US"].replace(" ", "").capitalize()

        emoji = discord.utils.get(bot.emojis, name=name)
        if emoji is None:
            return emoji_list.get(name)
        return emoji
    
    def get(name: str, bot: ValorantBot) -> discord.Emoji:
        emoji_list = JSON.read("emoji")
        emoji = discord.utils.get(bot.emojis, name=name)
        if emoji is None:
            return emoji_list.get(name)
        return emoji




# ---------- UTILS FOR STORE EMBED ---------- #

class GetFormat:

    def get_kdrate(kills: int, deaths: int) -> float:
        if deaths <= 0:
            deaths = 1
        return round(float(kills)/float(deaths) ,1)
    
    def get_kdarate(kills: int, deaths: int, assists: int) -> float:
        if deaths <= 0:
            deaths = 1
        return round(float(kills+assists)/float(deaths) ,1)
    
    def get_trackergg_link(match_id: str) -> str:
        return f"https://tracker.gg/valorant/match/{match_id}"

    def offer_format(data: Dict, locale: str = None) -> Dict:
        """Get skins list"""
        if locale==None:
            locale = str(VLR_locale)

        offer_list = data["SkinsPanelLayout"]["SingleItemOffers"]
        duration = data["SkinsPanelLayout"]["SingleItemOffersRemainingDurationInSeconds"]

        skin_count = 0
        skin_source = {}

        for uuid in offer_list:
            skin = GetItems.get_skin(uuid)
            name, icon = skin['names'][locale], skin['icon']
            video = skin.get('video')
            levels = skin.get('levels', {})

            price = GetItems.get_skin_price(uuid)
            tier_icon = GetItems.get_skin_tier_icon(uuid)

            if skin_count == 0:
                skin1 = dict(name=name, icon=icon, price=price, tier=tier_icon, uuid=uuid, video=video, levels=levels)
            elif skin_count == 1:
                skin2 = dict(name=name, icon=icon, price=price, tier=tier_icon, uuid=uuid, video=video, levels=levels)
            elif skin_count == 2:
                skin3 = dict(name=name, icon=icon, price=price, tier=tier_icon, uuid=uuid, video=video, levels=levels)
            elif skin_count == 3:
                skin4 = dict(name=name, icon=icon, price=price, tier=tier_icon, uuid=uuid, video=video, levels=levels)
            skin_count += 1

        skin_source = {
            'skin1': skin1,
            'skin2': skin2,
            'skin3': skin3,
            'skin4': skin4,
            'duration': duration
        }

        return skin_source

    def get_act_rank_border_level(wins: int = 0) -> int:
        if wins < 9:
            border = 0
        elif wins >= 9 and wins < 25:
            border = 1
        elif wins >= 25 and wins < 50:
            border = 2
        elif wins >= 50 and wins < 75:
            border = 3
        elif wins >= 75 and wins < 100:
            border = 4
        elif wins >= 100:
            border = 5 
            
        return border

    # ---------- UTILS FOR MATCH EMBED ---------- #

    def get_match_info(puuid: str, match_id: str, endpoint, response: Dict, locale: str = None) -> Dict:
        # cache
        import threading
        cache = JSON.read("cache")

        # match info
        match_detail = endpoint.fetch_match_details(match_id)
        if match_detail==None:
            raise ValorantBotError(response.get("NOT_FOUND"))
        match_info = {}

        # detail
        is_played = False
        players = {}
        rounds = []
        teams = {}

        if locale == None:
            locale = str(VLR_locale)

        def set_match_detail():
            info = match_detail["matchInfo"]
            start_time, duration = format_relative(datetime.fromtimestamp(info["gameStartMillis"]/1000, timezone.utc)), format_timedelta(timedelta(milliseconds=info["gameLengthMillis"]))
            mapid = GetFormat.get_mapuuid_from_mapid(info["mapId"])
            match_id, map = info["matchId"], cache["maps"][mapid]["names"][locale]
            season_id = info["seasonId"]
            
            # season
            if cache["seasons"][season_id]["parent_uuid"]!=None:
                season = cache["seasons"][cache["seasons"][season_id]["parent_uuid"]]["names"][locale] + " // "+ cache["seasons"][season_id]["names"][locale]
            else:
                season = cache["seasons"][season_id]["names"][locale]

            match_info["time"] = start_time
            match_info["duration"] = duration
            match_info["map"] = map
            match_info["map_id"] = mapid
            match_info["match_id"] = match_id
            match_info["season_id"] = season_id

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
        def set_players():    
            raw_players = match_detail.get("players", [])
            penalties = match_detail["matchInfo"].get("partyRRPenalties", {})
            for p in raw_players:
                rank_tier = p["competitiveTier"] if p["competitiveTier"]!=0 else endpoint.get_player_tier_rank(puuid=p["subject"])
                player = {
                    "puuid": p["subject"],
                    "name": "{name}#{tagline}".format(name=p["gameName"], tagline=p["tagLine"]),
                    "level": p["accountLevel"],
                    "rank": GetFormat.get_competitive_tier_name(rank_tier, locale),
                    "rank_id": rank_tier,

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
                    
                    "agent": cache["agents"][p["characterId"]]["names"][locale],
                    "role": cache["agents"][p["characterId"]]["role"]["names"][locale],

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
        def set_round():
            raw_rounds = match_detail["roundResults"]
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
                    _round["ceremony"] = cache["ceremonies"][ceremony_id]["names"][locale]

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
        def calculate_eco_rating():
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
        def set_kill_list():
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
        def set_teams():
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
        
        # points and results
        def calculate_points_and_results():
            is_played = match_info["is_played"]
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
            queue_id = match_detail["matchInfo"]["queueID"]
            if queue_id!="deathmatch":
                if is_played and point_v[0]>point_v[1]:
                    temp_result = 1
                    results = response.get("RESULT", {}).get("WIN", "")
                    color=Config.GetColor("win")
                elif is_played and point_v[1]>point_v[0]:
                    temp_result = -1
                    results = response.get("RESULT", {}).get("LOSE", "")
                    color=Config.GetColor("lose")
                elif point_v[1]==point_v[0]:
                    results = response.get("RESULT", {}).get("DRAW", "")
                    color=Config.GetColor("draw")
                elif (not is_played) and point_v[1]!=point_v[0]:
                    temp_result = 1
                    results = response.get("RESULT", {}).get("WIN", "")
                    color=Config.GetColor("win")
            else:
                if is_played and point_v[0]==40 and teams[puuid]["point"]==40:
                    temp_result = 1
                    results = response.get("RESULT", {}).get("WIN", "")
                    color=Config.GetColor("win")
                elif is_played and point_v[0]==40 and teams[puuid]["point"]<40:
                    temp_result = -1
                    results = response.get("RESULT", {}).get("LOSE", "")
                    color=Config.GetColor("lose")
                elif point_v[0]<=40:
                    results = response.get("RESULT", {}).get("DRAW", "")
                    color=Config.GetColor("draw")
                else:
                    temp_result = 1
                    results = response.get("RESULT", {}).get("WIN", "")
                    color=Config.GetColor("win")
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

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            executor.submit(set_match_detail)
            executor.submit(set_players)
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            executor.submit(set_round)
            executor.submit(set_teams)
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            executor.submit(calculate_eco_rating)
            executor.submit(calculate_points_and_results)
            executor.submit(set_kill_list)

        res = {"match_info": match_info, "players": players, "rounds": rounds, "teams": teams}
        return res

    def format_match_playerdata(format: str, players: Dict, puuid: str, match_id: str, bot: ValorantBot):
        if format==None:
            return None
        cache = JSON.read("cache")
        return format.format(
            tracker=GetFormat.get_trackergg_link(match_id),

            puuid=puuid,
            name=players[puuid]["name"],
            username=players[puuid]["name"].split("#", 1)[0],
            tagline=players[puuid]["name"].split("#", 1)[1],
            rank=players[puuid]["rank"],
            rank_emoji=GetEmoji.competitive_tier_by_bot(players[puuid]["rank_id"], bot),
            level=players[puuid]["level"],
            agent=players[puuid]["agent"],
            agent_en=cache["agents"][players[puuid]["agent_id"]]["names"]["en-US"],
            agent_en_capital=cache["agents"][players[puuid]["agent_id"]]["names"]["en-US"].upper(),
            agent_emoji=GetEmoji.agent_by_bot(players[puuid]["agent_id"], bot),
            role=players[puuid]["role"],
            role_en=cache["agents"][players[puuid]["agent_id"]]["role"]["names"]["en-US"],
            role_en_capital=cache["agents"][players[puuid]["agent_id"]]["role"]["names"]["en-US"].upper(),
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


    # ---------- UTILS FOR MISSION EMBED ---------- #

    def mission_format(data: Dict) -> Dict[str, Any]:
        """Get mission format"""

        mission = data["Missions"]

        weekly = []
        daily = []
        newplayer = []
        daily_end = ''
        try:
            weekly_end = data['MissionMetadata']['WeeklyRefillTime']
        except KeyError:
            weekly_end = ''

        def get_mission_by_id(ID) -> Optional[str]:
            data = JSON.read('cache')
            mission = data['missions'][ID]
            return mission

        for m in mission:
            mission = get_mission_by_id(m['ID'])
            *complete, = m['Objectives'].values()
            title = mission['titles'][str(VLR_locale)]
            progress = mission['progress']
            xp = mission['xp']

            format_m = f"\n{title} | **+ {xp:,} XP**\n- **`{complete[0]}/{progress}`**"

            if mission['type'] == 'EAresMissionType::Weekly':
                weekly.append(format_m)
            if mission['type'] == 'EAresMissionType::Daily':
                daily_end = m['ExpirationTime']
                daily.append(format_m)
            if mission['type'] == 'EAresMissionType::NPE':
                newplayer.append(format_m)

        misson_data = dict(daily=daily, weekly=weekly, daily_end=daily_end, weekly_end=weekly_end, newplayer=newplayer)
        return misson_data

    # ---------- UTILS FOR NIGHTMARKET EMBED ---------- #

    def nightmarket_format(offer: Dict, response: Dict) -> Dict[str, Any]:
        """Get Nightmarket offers"""

        try:
            night_offer = offer['BonusStore']['BonusStoreOffers']
        except KeyError:
            raise ValorantBotError(response.get('NIGMARKET_HAS_END', 'Nightmarket has been ended'))
        duration = offer['BonusStore']['BonusStoreRemainingDurationInSeconds']

        night_market = {}
        count = 0
        for x in night_offer:
            count += 1
            price = *x['Offer']['Cost'].values(),
            Disprice = *x['DiscountCosts'].values(),

            uuid = x['Offer']['OfferID']
            skin = GetItems.get_skin(uuid)
            name = skin['names'][str(VLR_locale)]
            icon = skin['icon']
            tier = GetItems.get_skin_tier_icon(uuid)

            night_market['skin' + f'{count}'] = {
                'uuid': uuid,
                'name': name,
                'tier': tier,
                'icon': icon,
                'price': price[0],
                'disprice': Disprice[0]
            }
        data = {
            'nightmarket': night_market,
            'duration': duration
        }
        return data

    # ---------- UTILS FOR BATTLEPASS EMBED ---------- #

    def __get_item_battlepass(type: str, uuid: str, response: Dict, locale: str = str(VLR_locale)) -> Dict[str, Any]:
        """Get item battle pass by type and uuid"""

        if type == 'Currency':
            data = JSON.read('cache')
            name = data['currencies'][uuid]['names'][locale]
            icon = data['currencies'][uuid]['icon']
            item_type = response.get('POINT', 'Point')
            return {"success": True, "data": {'type': item_type, 'name': '10 ' + name, 'icon': icon}}

        elif type == 'PlayerCard':
            data = JSON.read('cache')
            name = data['playercards'][uuid]['names'][locale]
            icon = data['playercards'][uuid]['icon']['wide']
            item_type = response.get('PLAYER_CARD', 'Player Card')
            return {"success": True, "data": {'type': item_type, 'name': name, 'icon': icon}}

        elif type == 'Title':
            data = JSON.read('cache')
            name = data['titles'][uuid]['names'][locale]
            icon = GetItems.get_title_icon()
            item_type = response.get('PLAYER_TITLE', 'Title')
            return {"success": True, "data": {'type': item_type, 'name': name, 'icon': icon}}

        elif type == 'Spray':
            data = JSON.read('cache')
            name = data['sprays'][uuid]['names'][locale]
            icon = data['sprays'][uuid]['icon']
            item_type = response.get('SPRAY', 'Spray')
            return {"success": True, "data": {'type': item_type, 'name': name, 'icon': icon}}

        elif type == 'EquippableSkinLevel':
            data = JSON.read('cache')
            name = data['skins'][uuid]['names'][locale]
            icon = data['skins'][uuid]['icon']
            item_type = response.get('SKIN', 'Skin')
            return {"success": True, "data": {'type': item_type, 'name': name, 'icon': icon}}

        elif type == 'EquippableCharmLevel':
            data = JSON.read('cache')
            name = data['buddies'][uuid]['names'][locale]
            icon = data['buddies'][uuid]['icon']
            item_type = response.get('BUDDY', 'Buddie')
            return {"success": True, "data": {'type': item_type, 'name': name, 'icon': icon}}
        
        elif type== 'Character':
            data = JSON.read('cache')
            name = data['agents'][uuid]['names'][locale]
            icon = data['agents'][uuid]['portrait']
            item_type = response.get('CHARACTER', 'Character')
            return {"success": True, "data": {'type': item_type, 'name': name, 'icon': icon}}

        return {"success": False, "error": f"Failed to get : {type}"}

    def __get_contract_tier_reward(tier: int, reward: List[Dict], max: int = 55) -> Dict[str, Any]:
        """Get tier reward"""

        data = {}
        count = 0

        for lvl in reward:
            for rw in lvl["levels"]:
                count += 1
                data[count] = rw

        next_reward = tier + 1
        if tier == max: next_reward = max
        current_reward = data[next_reward]

        return current_reward
    
    def __get_contract_tier_free_reward(tier: int, reward: List[Dict], max: int = 55) -> Dict[str, Any]:
        """Get tier reward"""

        data = {}
        count = 0

        free_rewards = []
        for lvl in reward:
            i = 0
            for rw in lvl["levels"]:
                count += 1
                i += 1

                if i==len(lvl["levels"]):
                    data[count] = lvl.get("freeRewards", [])
                else:
                    data[count] = []

        next_reward = tier + 1
        if tier == max: next_reward = max
        current_reward = data[next_reward]

        if current_reward==None:
            return []
        return current_reward

    def __get_contracts_by_season_id(contracts: Dict, data_contracts: Dict, season_id: str) -> Dict[str, Any]:
        """Get battle pass info"""

        contracts_uuid = [x for x in data_contracts['contracts'] if data_contracts['contracts'][x]['reward']['relationUuid'] == season_id]
        if contracts_uuid:
            battlepass = [x for x in contracts if x['ContractDefinitionID'] == contracts_uuid[0]]
            TIER = battlepass[0]['ProgressionLevelReached']
            XP = battlepass[0]['ProgressionTowardsNextLevel']
            REWARD = data_contracts['contracts'][contracts_uuid[0]]['reward']['chapters']
            ACT = data_contracts['contracts'][contracts_uuid[0]]['names'][str(VLR_locale)]

            return {"success": True, 'tier': TIER, 'xp': XP, 'reward': REWARD, 'act': ACT}

        return {"success": False, "error": "Failed to get battlepass info"}
    
    # ---------- UTILS FOR RANK EMBED ---------- #

    def get_competitive_tier_name(tier: int, locale: str = None) -> str:
        """Get competitive tier name"""
        ranks = JSON.read('cache')
        if locale==None:
            locale = str(VLR_locale)
        return ranks['competitive_tiers'][str(tier)]['names'][locale]
    
    def get_competitive_tier_matching(tier: int) -> List[List]:
        """Get competitive tier matching"""

        rank_tier = []
        if tier>=3 and tier<=8:
            rank_tier = [[3, 11]]
        elif tier>=6 and tier<=8:
            rank_tier = [[3, 11]]
        elif tier>=9 and tier<=11:
            rank_tier = [[3, 11], [9, 14]]
        elif tier>=12 and tier<=14:
            rank_tier = [[9, 14], [12, 17]]
        elif tier==15:
            rank_tier = [[12, 17], [15, 18]]
        elif tier==16:
            rank_tier = [[12, 17], [15, 18], [16, 19]]
        elif tier==17:
            rank_tier = [[12, 17], [15, 18], [16, 19], [17, 20]]
        elif tier==18:
            rank_tier = [[15, 18], [16, 19], [17, 20], [18, 21]]
        elif tier==19:
            rank_tier = [[16, 19], [17, 20], [18, 21], [19, 22]]
        elif tier==20:
            rank_tier = [[17, 20], [18, 21], [19, 22], [20, 23]]
        elif tier==21:
            rank_tier = [[18, 21], [19, 22], [20, 23], [21, 24]]
        elif tier==22:
            rank_tier = [[19, 22], [20, 23], [21, 24], [22, 25]]
        elif tier==23:
            rank_tier = [[20, 23], [21, 24], [22, 25], [23, 26]]
        elif tier==24:
            rank_tier = [[21, 24], [22, 25], [23, 26], [24, 27]]
        elif tier==25:
            rank_tier = [[22, 25], [23, 26], [24, 27]]
        elif tier==26:
            rank_tier = [[23, 26], [24, 27]]
        elif tier==27:
            rank_tier = [[24, 27]]
        else:
            rank_tier = []

        return rank_tier

    def get_mapuuid_from_mapid(mapid: str) -> str:
        """Get a map uuid from MapID"""
        maps = JSON.read('cache')['maps']
        
        for key,map in maps.items():
            if map['mapId'] == mapid:
                return key
    
    def get_uuid_from_ceremony_id(ceremony: str, only_ingame: bool = True) -> str:
        if ceremony=="CeremonyDefault": # default
            return ""
        elif ceremony=="CeremonyFlawless": # perfect
            return "eb651c62-421f-98fc-8008-68bee9ec942d"
        elif ceremony=="CeremonyClutch": # clutch
            return "a6100421-4ecb-bd55-7c23-e4899643f230"
        elif ceremony=="CeremonyThrifty": # thrifty
            return "bf94f35e-4794-8add-dc7d-fb90a08d3d04"
        elif ceremony=="CeremonyAce": # ace
            return "1e71c55c-476e-24ac-0687-e48b547dbb35"
        elif ceremony=="CeremonyTeamAce": # team ace
            return "87c91747-4de4-635e-a64b-6ba4faeeae78"
        elif ceremony=="CeremonyCloser": # closer
            if only_ingame:
                return ""
            else:
                return "b41f4d69-4f9d-ffa9-2be8-e2878cf7f03b"
        else: # error
            return None

    @classmethod
    def contract_format(cls, data: Dict, contract_uuid: str, response: Dict, locale: str) -> Dict[str, Any]:
        data = data['Contracts']
        cache = JSON.read("cache")

        tiers = 0
        ret = []

        for contract in data:
            if contract.get("ContractDefinitionID")==contract_uuid:
                tier = contract.get("ProgressionLevelReached", 0)
                xp = contract.get("ProgressionTowardsNextLevel", 0)
                reward = cache["contracts"][contract_uuid]["reward"]["chapters"]

                i = 0
                max_xp = 0
                for r in cache["contracts"][contract_uuid]["reward"]["chapters"]:
                    tiers += len(r["levels"])

                    for level in r["levels"]:
                        if i==tier:
                            max_xp = level["xp"]
                        i += 1
                
                items = []
                item_reward = cls.__get_contract_tier_reward(tier, reward, tiers)
                item = cls.__get_item_battlepass(item_reward["reward"]['type'], item_reward["reward"]['uuid'], response, locale)
                item["original_type"]=item_reward["reward"]['type']
                items.append(item)

                for item in items:
                    item_name = item['data']['name']
                    item_type = item['data']['type']
                    item_icon = item['data']['icon']
                    if item_reward.get("isPurchasableWithVP", False):
                        cost = item_reward.get("vpCost", 0)
                    else:
                        cost = "-"
                    
                    dict_data = dict(data=dict(tier=tier, tiers=tiers, xp=xp, max_xp=max_xp, reward=item_name, type=item_type, icon=item_icon, original_type=item["original_type"], cost = cost))
                    ret.append(dict_data)

                return ret
            
        raise ValorantBotError(f"Failed to get contracts info")


    @classmethod
    def battlepass_format(cls, data: Dict, season: str, response: Dict, locale: str) -> List[Dict[str, Any]]:
        """ Get battle pass format """

        data = data['Contracts']
        contracts = JSON.read('cache')
        # data_contracts['contracts'].pop('version')

        season_id = season['id']
        season_end = season['end']
        tiers = 0

        ret = []
        btp = cls.__get_contracts_by_season_id(data, contracts, season_id)
        if btp['success']:
            for r in btp["reward"]:
                tiers += len(r["levels"])

            tier, act, xp, reward = btp['tier'], btp['act'], btp['xp'], btp['reward']

            items = []
            item_reward = cls.__get_contract_tier_reward(tier, reward, tiers)
            free_rewards = cls.__get_contract_tier_free_reward(tier, reward, tiers)

            item = cls.__get_item_battlepass(item_reward["reward"]['type'], item_reward["reward"]['uuid'], response, locale)
            item["original_type"]=item_reward["reward"]['type']
            items.append(item)

            for free_reward in free_rewards:
                item = cls.__get_item_battlepass(free_reward['type'], free_reward['uuid'], response, locale)
                item["original_type"]=free_reward['type']
                items.append(item)

            for item in items:
                item_name = item['data']['name']
                item_type = item['data']['type']
                item_icon = item['data']['icon']
                if item_reward.get("isPurchasableWithVP", False):
                    cost = item_reward.get("vpCost", 0)
                else:
                    cost = "-"
                
                dict_data = dict(data=dict(tier=tier, tiers=tiers, act=act, xp=xp, reward=item_name, type=item_type, icon=item_icon, end=season_end, original_type=item["original_type"], cost = cost))
                ret.append(dict_data)

            return ret

        raise ValorantBotError(f"Failed to get battlepass info")
    
    @classmethod
    def battlepass_event_format(cls, data: Dict, event: str, response: Dict, locale: str) -> Dict[str, Any]:
        """ Get battle pass format """

        data = data['Contracts']
        contracts = JSON.read('cache')
        # data_contracts['contracts'].pop('version')

        tiers = 0

        btp = cls.__get_contracts_by_season_id(data, contracts, event)
        if btp['success']:
            for r in btp["reward"]:
                tiers += len(r["levels"])

            tier, act, xp, reward = btp['tier'], btp['act'], btp['xp'], btp['reward']

            item_reward = cls.__get_contract_tier_reward(tier, reward, tiers)
            item = cls.__get_item_battlepass(item_reward["reward"]['type'], item_reward["reward"]['uuid'], response, locale)

            item_name = item['data']['name']
            item_type = item['data']['type']
            item_icon = item['data']['icon']
            if item_reward.get("isPurchasableWithVP", False):
                cost = item_reward.get("vpCost", 0)
            else:
                cost = "-"

            event_end = contracts["events"][event]["end"]

            return dict(data=dict(tier=tier, tiers=tiers, act=act, xp=xp, reward=item_name, type=item_type, icon=item_icon, end=event_end, original_type=item_reward["reward"]['type'], cost = cost))

        raise ValorantBotError(f"Failed to get battlepass info")

class GetImage:
    def paste_centered(dest: Image, source: Image, coordinate: tuple) -> Image:
        img = dest
        img.paste(source, (int(dest.width/2-source.width/2+coordinate[0]), int(dest.height/2-source.height/2+coordinate[1])), source)
        return img

    def convert_color(color: int) -> tuple:
        n = hex(color)[2:]
        if len(n)<6:
            n = "0" * (6 -len(n)) + n
        return tuple(int(c*255) for c in matplotlib.colors.to_rgb("#" + n.upper()))
    
    def convert_hex(color: int) -> str:
        n = hex(color)[2:]
        if len(n)<6:
            n = "0" * (6 -len(n)) + n
        return n
    
    def draw_text(img: Image, text: str, coordinate: Tuple, font, color: str = "#000000") -> Image:
        draw = ImageDraw.Draw(img)
        draw.text((int(img.width/2 + coordinate[0]), int(img.height/2 + coordinate[1])), text, color, font=font, anchor='mm')
    
    def load_font():
        print(f"[{datetime.now()}] Loading fonts data.")
        fonts = fm.findSystemFonts()
        fonts_additional = fm.findSystemFonts(f"resources/font/")
        fonts.extend(fonts_additional)
        _all_fonts = set()
        _dejav = set()

        list = {}

        for font in fonts:
            for i in range(10):
                try:
                    ttf = ImageFont.truetype(font=font, index=i)
                except IOError as e:
                    break
                    
                dn, _, bn = font.rpartition(os.sep)
        
                if (bn.upper(), i) in _dejav:
                    continue
                _dejav.add((bn.upper(), i))
                family, style = ttf.getname()

                if list.get(family, None) == None:
                    list[family] = {}
                
                list[family][style] = {"family": family, "style": style, "path": font}
        
        JSON.save("fonts", list)

    def find_font(family: str, style: str = "Regular") -> str:
        fonts = JSON.read("fonts")
        return fonts.get(family, {}).get(style, {}).get("path", None)

