from __future__ import annotations

from io import BytesIO
from typing import Optional, TYPE_CHECKING

import os
import json
import discord
import requests
import glob

import utils.config as Config
from typing import Any, Dict, List
from .local import LocalErrorResponse
from ..errors import ValorantBotError

if TYPE_CHECKING:
    from bot import ValorantBot

# ------------------- #
# credit https://github.com/colinhartigan/

base_endpoint = "https://pd.{shard}.a.pvp.net"
base_endpoint_glz = "https://glz-{region}-1.{shard}.a.pvp.net"
base_endpoint_shared = "https://shared.{shard}.a.pvp.net"
base_endpoint_henrik = "https://api.henrikdev.xyz"

regions: list = ["na", "eu", "latam", "br", "ap", "kr", "pbe"]
region_shard_override = {
    "latam": "na",
    "br": "na",
}
shard_region_override = {
    "pbe": "na"
}

# ------------------- #


# EMOJI

emoji_server = 1007498215978979328

emoji_icon_assests = {
    'DeluxeTier': 'https://media.valorant-api.com/contenttiers/0cebb8be-46d7-c12a-d306-e9907bfc5a25/displayicon.png',
    'ExclusiveTier': 'https://media.valorant-api.com/contenttiers/e046854e-406c-37f4-6607-19a9ba8426fc/displayicon.png',
    'PremiumTier': 'https://media.valorant-api.com/contenttiers/60bca009-4182-7998-dee7-b8a2558dc369/displayicon.png',
    'SelectTier': 'https://media.valorant-api.com/contenttiers/12683d76-48d7-84a3-4e09-6985794f0445/displayicon.png',
    'UltraTier': 'https://media.valorant-api.com/contenttiers/411e4a55-4e59-7757-41f0-86a53f101bb5/displayicon.png',
    'ValorantPointIcon': 'https://media.valorant-api.com/currencies/85ad13f7-3d1b-5128-9eb2-7cd8ee0b5741/largeicon.png',
    'RadianitePointIcon': 'https://media.valorant-api.com/currencies/e59aa87c-4cbf-517a-5983-6e81511be9b7/displayicon.png',
    
    'EliminationLost': "https://trackercdn.com/cdn/tracker.gg/valorant/icons/eliminationloss1.png",
    "EliminationWon": "https://trackercdn.com/cdn/tracker.gg/valorant/icons/eliminationwin1.png",
    "DefuseLost": "https://trackercdn.com/cdn/tracker.gg/valorant/icons/diffuseloss1.png",
    "DefuseWon": "https://trackercdn.com/cdn/tracker.gg/valorant/icons/diffusewin1.png",
    "TimeupLost": "https://trackercdn.com/cdn/tracker.gg/valorant/icons/timeloss1.png",
    "TimeupWon": "https://trackercdn.com/cdn/tracker.gg/valorant/icons/timewin1.png",
    "DetonateLost": "https://trackercdn.com/cdn/tracker.gg/valorant/icons/explosionloss1.png",
    "DetonateWon": "https://trackercdn.com/cdn/tracker.gg/valorant/icons/explosionwin1.png",

    "Credits": "https://static.wikia.nocookie.net/valorant/images/8/81/Credits_icon.png",
    "WallPenetration": "https://static.wikia.nocookie.net/valorant/images/9/93/WallPenetration.png",
    "FireMode": "https://static.wikia.nocookie.net/valorant/images/2/29/Firemode.png"
}

tiers = {
    '0cebb8be-46d7-c12a-d306-e9907bfc5a25': {'name': 'DeluxeTier', 'emoji': 'DeluxeTier', 'color': 0x009587},
    'e046854e-406c-37f4-6607-19a9ba8426fc': {'name': 'ExclusiveTier', 'emoji': 'ExclusiveTier', 'color': 0xf1b82d},
    '60bca009-4182-7998-dee7-b8a2558dc369': {'name': 'PremiumTier', 'emoji': 'PremiumTier', 'color': 0xd1548d},
    '12683d76-48d7-84a3-4e09-6985794f0445': {'name': 'SelectTier', 'emoji': 'SelectTier', 'color': 0x5a9fe2},
    '411e4a55-4e59-7757-41f0-86a53f101bb5': {'name': 'UltraTier', 'emoji': 'UltraTier', 'color': 0xefeb65}
}


def get_item_type(uuid: str) -> Optional[str]:
    """Get item type"""
    item_type = {
        '01bb38e1-da47-4e6a-9b3d-945fe4655707': 'Agents',
        'f85cb6f7-33e5-4dc8-b609-ec7212301948': 'Contracts',
        'd5f120f8-ff8c-4aac-92ea-f2b5acbe9475': 'Sprays',
        'dd3bf334-87f3-40bd-b043-682a57a8dc3a': 'Gun Buddies',
        '3f296c07-64c3-494c-923b-fe692a4fa1bd': 'Player Cards',
        'e7c63390-eda7-46e0-bb7a-a6abdacd2433': 'Skins',
        '3ad1b2b2-acdb-4524-852f-954a76ddae0a': 'Skins chroma',
        'de7caa6b-adf7-4588-bbd1-143831e786c6': 'Player titles'
    }
    return item_type.get(uuid, None)


def __url_to_image(url) -> Optional[bytes]:
    session = requests.session()
    
    r = session.get(url)
    image = BytesIO(r.content)
    image_value = image.getvalue()
    if r.status_code in range(200, 299):
        return image_value

# FROM useful.py
def json_save(filename: str, data: Dict) -> None:
        """Save data to json file"""
        try:
            with open("data/" + filename + ".json", 'w', encoding='utf-8') as json_file:
                json.dump(data, json_file, indent=2, ensure_ascii=False)
        except FileNotFoundError:
            from .cache import create_json
            create_json(filename, {})
            return json_save(filename, data)

def json_read(filename: str, force: bool = True) -> Dict:
        """Read json file"""
        try:
            with open("data/" + filename + ".json", "r", encoding='utf-8') as json_file:
                data = json.load(json_file)
        except FileNotFoundError:
            from .cache import create_json
            if force:
                create_json(filename, {})
                return json_read(filename, False)
        return data


async def setup_emoji(bot: ValorantBot, guild: discord.Guild, local_code: str, force: bool = False, reset: bool = False) -> str:
    response = LocalErrorResponse('SETUP_EMOJI', local_code)
    cache = json_read('cache')
    main_server_id = Config.LoadConfig().get("emoji-server-id")
    
    reg_emojis = []

    # default emojis
    for key,value in emoji_icon_assests.items():
        reg_emojis.append({"name": key, "url": value, "animated": False})
    
    # agent emojis
    for agent in cache["agents"].values():
        name = "Agent" + agent["name"]["en-US"].replace("/", "") # for kay/o
        reg_emojis.append({"name": name, "url": agent["icon"], "animated": False})

        name = agent["role"]["name"]["en-US"]
        if next((x for x in reg_emojis if x["name"]==name), None)==None:
            reg_emojis.append({"name": name, "url": agent["role"]["icon"], "animated": False})

    # tiers emojis
    """
    for rank in cache["competitive_tiers"].values():
        name = "Tier" + rank["name"]["en-US"].replace(" ", "").capitalize()
        if rank["icon"]!=None:
            reg_emojis.append({"name": name, "url": rank["icon"], "animated": False})
    """

    # Remove Emoji
    if reset:
        print("------ REMOVE EMOJI ------")
        emojis = await guild.fetch_emojis()
        for emoji in emojis:
            if bot.user==emoji.user:
                try:
                    await emoji.delete(reason="auto deletion")
                    print(f"Removed emoji \"{emoji.name}\", {emoji.id}.")
                except discord.Forbidden:
                    if force:
                        raise ValorantBotError(response.get('MISSING_PERM'))
                    continue
                except discord.HTTPException:
                    print(response.get('FAILED_MANAGE_EMOJI'))
                    pass

    # Setup emoji
    print("------ CREATE EMOJI ------")
    ret_message = ""
    emoji_list = {}

    for e in reg_emojis:
        name = e["name"]
        url = e["url"]

        emoji = discord.utils.get(bot.emojis, name=name)

        if not emoji:
            try:
                if int(str(guild.id)) == main_server_id:
                    emoji = await guild.create_custom_emoji(name=name, image=__url_to_image(url), reason="auto creation")
                    
                    emoji_list[e["name"]] = f"<:{name}:{emoji.id}>"
                    ret_message += f"<:{name}:{emoji.id}> "
                    print(f"Created emoji \"{name}\" from \"{url}\".")
                else:
                    raise ValorantBotError(response.get('NOT_MAINSERVER'))
            except discord.Forbidden:
                if force:
                    raise ValorantBotError(response.get('MISSING_PERM'))
                continue
            except discord.HTTPException:
                print(response.get('FAILED_MANAGE_EMOJI'))
                pass
        else:
            emoji_list[name] = f"<:{name}:{emoji.id}>"
            ret_message += f"<:{name}:{emoji.id}> "

    json_save("emoji", emoji_list)
    return ret_message
