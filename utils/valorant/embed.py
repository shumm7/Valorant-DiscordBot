from __future__ import annotations
from operator import itemgetter

import re
import io, os, asyncio, concurrent.futures
import json
from pathlib import Path
import numpy as np
import math, random
import contextlib
import requests
from bs4 import BeautifulSoup
from matplotlib import font_manager as fm
from PIL import Image, ImageFont, ImageDraw, ImageFilter
from datetime import datetime, timedelta, timezone
from urllib import request
import dateutil.parser
from tracemalloc import start
from typing import Any, Dict, List, TYPE_CHECKING, Union
from unittest import result

from utils.errors import (
    ValorantBotError
)

import discord
from discord.utils import MISSING
from discord import app_commands, Interaction, ui, File
import matplotlib.pyplot as plt

from .endpoint import API_ENDPOINT

import utils.config as Config
from utils.valorant import view as View
from .useful import (calculate_level_xp, format_relative, GetEmoji, GetFormat, GetImage, iso_to_time, format_timedelta, JSON)
from ..locale_v2 import ValorantTranslator

VLR_locale = ValorantTranslator()

if TYPE_CHECKING:
    from bot import ValorantBot


class Embed(discord.Embed):  # Custom Embed
    def __init__(self, description: str = None, color: Union[discord.Color, int] = Config.GetColor("default"), **kwargs: Any) -> None:
        super().__init__(description=description, color=color, **kwargs)


class GetEmbed:

    def update_embed(version: str, bot: ValorantBot, general: bool = True) -> List[discord.Embed]:
        embeds = []

        update = JSON.read("update", dir="config")
        if version==None:
            version = bot.bot_version
        
        def get_embed(data: Dict) -> discord.Embed:
            embed = Embed(title=data.get("TITLE", "").format(name=bot.user.name), description=data.get("RESPONSE", "").format(name=bot.user.name))
            for i in range(10):
                field = f"FIELD{i+1}"
                if data.get(field):
                    embed.add_field(
                        name=data.get(field, {}).get("TITLE", "None"),
                        value=data.get(field, {}).get("RESPONSE", "None"),
                        inline=data.get(field, {}).get("INLINE", True)
                    )
                else:
                    break
            
            embed.set_image(url=data.get("IMAGE"))
            embed.set_thumbnail(url=data.get("THUMBNAIL", bot.user.avatar))
            embed.set_footer(text=data.get("FOOTER", ""))
            embed.set_author(name=data.get("HEADER", ""))
            return embed

        if general:
            general_data = update.get("general")
            if general_data:
                embeds.append(get_embed(general_data))

        ver_data = update.get(version)
        if ver_data:
            embeds.append(get_embed(ver_data))
        
        return embeds
    
    def __giorgio_embed(skin: Dict, bot: ValorantBot, response: Dict) -> discord.Embed:
        """EMBED DESIGN Giorgio"""
        
        uuid, name, price, icon, video_url, levels = skin['uuid'], skin['name'], skin['price'], skin['icon'], skin.get('video'), skin["levels"]
        emoji = GetEmoji.tier_by_bot(uuid, bot)

        i = 1
        response.get("VIDEO", "")
        video_text, video = "", ""
        is_video = False
        for level in levels.values():
            video_url = level.get("video")
            if len(video_text)>0:
                video_text += " "

            if video_url!=None:
                video_url = f"[[{str(i)}]]({video_url})"
                is_video = True
            else:
                video_url = f"[{str(i)}]"
            video_text += video_url
            i += 1
        video_text = response.get("VIDEO", "") + video_text

        if is_video:
            video = video_text
        else:
            video = ""
        
        vp_emoji = GetEmoji.point_by_bot('ValorantPointIcon', bot)
        
        embed = Embed(response.get("SKIN", "").format(emoji=emoji, name=name, vp_emoji=vp_emoji, price=price, video=video), color=Config.GetColor("items"))
        embed.set_thumbnail(url=icon)
        return embed
    
    def article_embed(article: Dict, response: Dict) -> discord.Embed:
        body = ""
        lines = Config.LoadConfig().get("article", {}).get("description", 150)

        try:
            html = requests.get(article.get("url")).content
            soup = BeautifulSoup(html, 'html.parser')

            elems = soup.find_all(["p", "li"])
            for elem in elems:
                body += elem.get_text().replace("\n", "") + " "
                if len(body)>lines:
                    body = body[:lines] + " ..."
                    break
        except:
            pass

        embed = discord.Embed(
            title = article.get("title"),
            description=body,
            url = article.get("external_link") or article.get("url"),
            timestamp = dateutil.parser.parse(article["date"])
        )
        embed.set_image(url = article.get("banner_url"))
        embed.set_author(name = response.get("CATEGORY", {}).get(article.get("category", "")))
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
            embed.color = Config.GetColor("success")
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

    # ---------- MATCH DETAILS EMBED ---------- #
    class MatchEmbed():
        def __init__(self, interaction: Interaction, match_id: str, response: Dict, endpoint: API_ENDPOINT, filename: List[str], is_private_message: bool) -> None:
            self.interaction: Interaction = interaction
            self.player: str = endpoint.player
            self.puuid: str = endpoint.puuid
            self.match_id: str = match_id
            self.language: str = str(VLR_locale)
            self.response: Dict = response
            self.endpoint: API_ENDPOINT = endpoint
            self.bot: ValorantBot = getattr(interaction, "client", interaction._state._get_client())
            self.cache = JSON.read('cache')
            self.color: str
            self.is_private_message: bool = is_private_message
            self.match_info: Dict

            self.files: List[List[discord.File]] = []
            self.filename = filename
            self.temp_embeds: Dict = {}
            self.temp_files: Dict = {}
            self.embeds: List[List[discord.Embed]] = []

        def build_graph(self, filename: str) -> discord.File:
            rounds = self.match_info["rounds"]
            teamA = self.match_info["match_info"]["teamA"]
            teamB = self.match_info["match_info"]["teamB"]

            f = Config.LoadConfig().get("commands", {}).get("match", {}).get("font", {}).get("graph-regular")
            font_regular = GetImage.find_font(f[0], f[1])

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
            

            # ticks
            plt.xticks(x)
            plt.yticks(y)
            prop = fm.FontProperties(fname=font_regular)
            for label in ax.get_xticklabels():
                label.set_fontproperties(prop)

            for label in ax.get_yticklabels():
                label.set_fontproperties(prop)
            
            plt.savefig(f"resources/temp/{filename}", bbox_inches='tight', transparent=True)
            plt.close()

            with open(f"resources/temp/{filename}", "rb") as f:
                file = io.BytesIO(f.read())
            image = discord.File(file, filename=filename)

            self.temp_files["graph"] = image

        def build_heatmap(self, filename: str) -> discord.File:
            players = self.match_info["players"]
            teams = self.match_info["teams"]
            teamA = self.match_info["match_info"]["teamA"]
            teamB = self.match_info["match_info"]["teamB"]

            f = Config.LoadConfig().get("commands", {}).get("match", {}).get("font", {}).get("heatmap-bold")
            font_bold = GetImage.find_font(f[0], f[1])
            f = Config.LoadConfig().get("commands", {}).get("match", {}).get("font", {}).get("heatmap-regular")
            font_regular = GetImage.find_font(f[0], f[1])

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
                        font=Path(font_bold)
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
                        font=Path(font_regular)
                    )
            
            # ticks
            cache = JSON.read("cache")

            ls = []
            for player in teams[teamA]["players"]:
                n = players[player]["name"].split("#")
                agent = players[player]["agent"]
                ls.append(f"{n[0]}\n#{n[1]}\n({agent})")
            plt.yticks(range(5), ls, font=Path(font_regular), fontsize=8)

            ls = []
            for player in teams[teamB]["players"]:
                n = players[player]["name"].split("#")
                agent = players[player]["agent"]
                ls.append(f"{n[0]}\n#{n[1]}\n({agent})")
            plt.xticks(range(5), ls, font=Path(font_regular), fontsize=8, rotation=45, horizontalalignment="right")

            # save image
            plt.savefig(f"resources/temp/{filename}", bbox_inches='tight', transparent=True)
            plt.close()

            with open(f"resources/temp/{filename}", "rb") as f:
                file = io.BytesIO(f.read())
            image = discord.File(file, filename=filename)

            self.temp_files["heatmap"] = image

        def build_stats(self, team_color: str, filename: str) -> discord.File:
            teams = self.match_info["teams"]
            players = self.match_info["players"]
            team = self.match_info["match_info"][team_color]

            size = (1920, 1080)
            cache = self.cache
            config = Config.LoadConfig()
            colors = config.get("commands", {}).get("match", {}).get("color", {})

            layer = [None, None]

            f = config.get("commands", {}).get("match", {}).get("font", {}).get("stats-title")
            font_impact = GetImage.find_font(f[0], f[1])
            f = config.get("commands", {}).get("match", {}).get("font", {}).get("stats-regular")
            font_regular = GetImage.find_font(f[0], f[1])
            f = config.get("commands", {}).get("match", {}).get("font", {}).get("stats-bold")
            font_bold = GetImage.find_font(f[0], f[1])
            f = config.get("commands", {}).get("match", {}).get("font", {}).get("stats-player")
            font_player = GetImage.find_font(f[0], f[1])

            def make_gradient(img: Image) -> Image:
                gradient = Image.new('L', (1, 256))
                for i in range(256):
                    gradient.putpixel((0, 255 - i), 256 - i)

                img.putalpha(gradient.resize(img.size))
                return img

            # result
            res: bool = False
            enemy_team: str
            for t in teams.values():
                res = res or t["win"]
                if t["id"]!=team:
                    enemy_team = t["id"]
            
            if res:
                score_color = ["#" + GetImage.convert_hex(colors.get("victory-text")), "#" + GetImage.convert_hex(colors.get("defeat-text"))]
                if teams[team]["win"]:
                    result_str = self.response.get("TEAM_STATS", {}).get("VICTORY")
                    result_color = "#" + GetImage.convert_hex(colors.get("victory-text"))
                    winner_score = teams[team]["point"]
                    loser_score = teams[enemy_team]["point"]
                else:
                    result_str = self.response.get("TEAM_STATS", {}).get("DEFEAT")
                    result_color = "#" + GetImage.convert_hex(colors.get("defeat-text"))
                    winner_score = teams[enemy_team]["point"]
                    loser_score = teams[team]["point"]
            else:
                score_color = ["#" + GetImage.convert_hex(colors.get("draw-text")), "#" + GetImage.convert_hex(colors.get("draw-text"))]
                result_str = self.response.get("TEAM_STATS", {}).get("DRAW")
                result_color = "#" + GetImage.convert_hex(colors.get("draw-text"))
                winner_score = teams[team]["point"]
                loser_score = teams[enemy_team]["point"]

            def make_base():
                # background
                base = Image.open("resources/stats_backscreen.png")

                # result text
                font = ImageFont.truetype(font_impact, 520)
                
                text_canvas = Image.new("RGB", size, result_color)
                text_canvas.putalpha(0)
                GetImage.draw_text(text_canvas, result_str, (0, -300), font, result_color)
                text_canvas = text_canvas.filter(ImageFilter.GaussianBlur(12))
                base.paste(text_canvas, (0,0), text_canvas)

                GetImage.draw_text(base, result_str, (0, -300), font, result_color)

                # score text
                font = ImageFont.truetype(font_impact, 120)
                GetImage.draw_text(base, str(winner_score), (-750, -433), font, score_color[0])
                GetImage.draw_text(base, str(loser_score), (750, -433), font, score_color[1])
                layer[0] = base

            def make_player_stats():
                base = Image.new("RGBA", size, (0,0,0,0))

                # players
                coordinate = [{"x": -600, "y": 0, "scale": 0.35}, {"x": 600, "y": 0, "scale": 0.35}, {"x": -300, "y": 0, "scale": 0.45}, {"x": 300, "y": 0, "scale": 0.45}, {"x": 0, "y": -70, "scale": 0.5}]
                coordinate_stats = [{"x": -620, "y": 80}, {"x": 620, "y": 80}, {"x": -310, "y": 80}, {"x": 310, "y": 80}, {"x": 0, "y": 80}]
                i: int = 0

                for puuid in reversed(teams[team]["players"]):
                    player = players[puuid]

                    # portrait
                    agent = cache["agents"][player["agent_id"]]
                    self.endpoint.download(agent['portrait'], f"resources/temp/{team_color}_agent_portrait.png")
                    portrait = Image.open(f"resources/temp/{team_color}_agent_portrait.png")
                    portrait = portrait.resize((int(portrait.width * coordinate[i]["scale"]), int(portrait.height * coordinate[i]["scale"])))
                    base = GetImage.paste_centered(base, portrait, (coordinate[i]["x"], coordinate[i]["y"]))

                    # stats base
                    stats_base = Image.new('RGB', (300, 270), GetImage.convert_color(colors.get("base")))
                    stats_base.putalpha(int(255 * 0.8))
                    base = GetImage.paste_centered(base, stats_base, (coordinate_stats[i]["x"], coordinate_stats[i]["y"]))

                    stats_lux = Image.new('RGB', (300, 1), GetImage.convert_color(colors.get("text")))
                    stats_lux.putalpha(int(255 * 0.8))
                    base = GetImage.paste_centered(base, stats_lux, (coordinate_stats[i]["x"], coordinate_stats[i]["y"]-135))

                    stats_lux = Image.new('RGB', (8, 8), GetImage.convert_color(colors.get("text")))
                    stats_lux.putalpha(255)
                    stats_lux = stats_lux.rotate(45, expand=True)
                    base = GetImage.paste_centered(base, stats_lux, (coordinate_stats[i]["x"], coordinate_stats[i]["y"]-135))

                    if i==len(teams[team]["players"])-1:
                        stats_base = Image.new('RGB', (300, 135), GetImage.convert_color(colors.get("point")))
                        stats_base = make_gradient(stats_base)
                        base = GetImage.paste_centered(base, stats_base, (coordinate_stats[i]["x"], coordinate_stats[i]["y"] + stats_base.height/2))

                        # mvp square
                        stats_base = Image.new('RGB', (160, 60), GetImage.convert_color(colors.get("text")))
                        stats_base.putalpha(255)
                        base = GetImage.paste_centered(base, stats_base, (coordinate_stats[i]["x"], coordinate_stats[i]["y"] - 145))

                        font = ImageFont.truetype(font_impact, 50)
                        GetImage.draw_text(base, self.response.get("TEAM_STATS", {}).get("MVP"), (coordinate_stats[i]["x"], coordinate_stats[i]["y"] - 145), font, "#" + GetImage.convert_hex(colors.get("base")))

                    # agent name
                    font = ImageFont.truetype(font_regular, 20)
                    GetImage.draw_text(base, GetFormat.format_match_playerdata(self.response.get("TEAM_STATS", {}).get("AGENT"), players, puuid, self.match_id, self.bot), (coordinate_stats[i]["x"], coordinate_stats[i]["y"] - 96), font, "#" + GetImage.convert_hex(colors.get("text-base")))

                    # rank icon
                    self.endpoint.download(cache["competitive_tiers"][str(player["rank_id"])]["icon"], f"resources/temp/{team_color}_rank_icon.png")
                    rank = Image.open(f"resources/temp/{team_color}_rank_icon.png")
                    rank = rank.crop(rank.getbbox())
                    rank = rank.resize((int(rank.width * 30 / rank.height), int(rank.height * 30 / rank.height)))
                    base = GetImage.paste_centered(base, rank, (coordinate_stats[i]["x"] - 120, coordinate_stats[i]["y"] - 110))

                    # player name
                    font = ImageFont.truetype(font_player, 34)
                    draw = ImageDraw.Draw(base)
                    txw, txh = draw.textsize(GetFormat.format_match_playerdata(self.response.get("TEAM_STATS", {}).get("NAME"), players, puuid, self.match_id, self.bot), font=font)
                    if txw > 300 - 20:
                        font = ImageFont.truetype(font_player, int(34 * (300 - 20) / txw))
                    GetImage.draw_text(base, GetFormat.format_match_playerdata(self.response.get("TEAM_STATS", {}).get("NAME"), players, puuid, self.match_id, self.bot), (coordinate_stats[i]["x"], coordinate_stats[i]["y"] - 60), font, "#" + GetImage.convert_hex(colors.get("text")))
                    
                    # line
                    stats_lux = Image.new('RGB', (300 - 40, 1), GetImage.convert_color(colors.get("text")))
                    stats_lux.putalpha(int(255 * 0.8))
                    base = GetImage.paste_centered(base, stats_lux, (coordinate_stats[i]["x"], coordinate_stats[i]["y"]-20))

                    # stats 1
                    font = ImageFont.truetype(font_bold, 30)
                    GetImage.draw_text(base, GetFormat.format_match_playerdata(self.response.get("TEAM_STATS", {}).get("RESPONSE_1"), players, puuid, self.match_id, self.bot), (coordinate_stats[i]["x"], coordinate_stats[i]["y"] +15), font, "#" + GetImage.convert_hex(colors.get("text")))
                    GetImage.draw_text(base, GetFormat.format_match_playerdata(self.response.get("TEAM_STATS", {}).get("RESPONSE_2"), players, puuid, self.match_id, self.bot), (coordinate_stats[i]["x"], coordinate_stats[i]["y"] +80), font, "#" + GetImage.convert_hex(colors.get("text")))
                    
                    font = ImageFont.truetype(font_regular, 20)
                    GetImage.draw_text(base, GetFormat.format_match_playerdata(self.response.get("TEAM_STATS", {}).get("TITLE_1"), players, puuid, self.match_id, self.bot), (coordinate_stats[i]["x"], coordinate_stats[i]["y"] +45), font, "#" + GetImage.convert_hex(colors.get("text-base")))
                    GetImage.draw_text(base, GetFormat.format_match_playerdata(self.response.get("TEAM_STATS", {}).get("TITLE_2"), players, puuid, self.match_id, self.bot), (coordinate_stats[i]["x"], coordinate_stats[i]["y"] +110), font, "#" + GetImage.convert_hex(colors.get("text-base")))
                    
                    i += 1
                    n = player["name"]
                layer[1] = base
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                executor.submit(make_base)
                executor.submit(make_player_stats)

            base = GetImage.paste_centered(layer[0], layer[1], (0,0))
            base.save(f"resources/temp/{filename}")

            with open(f"resources/temp/{filename}", "rb") as f:
                file = io.BytesIO(f.read())
            image = discord.File(file, filename=filename)

            if os.path.isfile(f"resources/temp/{team_color}_rank_icon.png"): os.remove(f"resources/temp/{team_color}_rank_icon.png")
            if os.path.isfile(f"resources/temp/{team_color}_agent_portrait.png"): os.remove(f"resources/temp/{team_color}_agent_portrait.png")

            self.temp_files["stats_" + team_color] = image

        def embed_main(self) -> None:
            cache = self.cache
            match_info = self.match_info
            response = self.response
            puuid = self.puuid
            match_id = self.match_id
            bot = self.bot

            # first embed post
            description = ""
            if match_info["match_info"]["is_played"]:
                description = GetFormat.format_match_playerdata(response.get("RESPONSE"), match_info["players"], puuid, match_id, bot)
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

            self.temp_embeds["main"] = embed_main

        def embed_players(self, filename: str) -> None:
            teams = self.match_info["teams"]
            players = self.match_info["players"]
            teamA = self.match_info["match_info"]["teamA"]
            teamB = self.match_info["match_info"]["teamB"]

            # player result post
            response = self.response
            embed_players = Embed(title=response.get("PLAYER", {}).get("TITLE"), color=self.color)

            def make_team_msg(team_name: str, title_format: str, message_format: str, team: str) -> List:
                message = ""
                for p in teams[team_name]["players"]:
                    if len(message)!=0:
                        message+="\n"
                    message += GetFormat.format_match_playerdata(message_format, players, p, self.match_id, self.bot)
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
                embed_players.set_image(url=f"attachment://{filename}")
                
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
                    if len(message)!=0:
                        message+="\n"
                    message += GetFormat.format_match_playerdata(response.get("PLAYERS", {}).get("DETAIL_DEATHMATCH"), players, t_puuid, self.match_id, self.bot)
                embed_players.description = message

            self.temp_embeds["players"] = embed_players

        def embed_team(self, title: str, team_color: str, filename: str = None) -> discord.Embed:
            embed_team = Embed(title=title, color=self.color)
            teams = self.match_info["teams"]
            players = self.match_info["players"]
            team = self.match_info["match_info"][team_color]

            for p in teams[team]["players"]:
                n = GetFormat.format_match_playerdata(self.response.get("STATS",{}).get("TITLE"), players, p, self.match_id, self.bot)
                v = GetFormat.format_match_playerdata(self.response.get("STATS",{}).get("RESPONSE"), players, p, self.match_id, self.bot)
                embed_team.add_field(name=n, value=v)
            
            if filename!=None:
                embed_team.set_image(url=f"attachment://{filename}")
            
            self.temp_embeds["team_" + team_color] = embed_team

        def embed_economy(self, filename: str) -> List[discord.Embed]:
            rounds = self.match_info["rounds"]
            teamA = self.match_info["match_info"]["teamA"]
            teamB = self.match_info["match_info"]["teamB"]

            response = self.response
            bot = self.bot

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

            embed_economy = Embed(title=response.get("ECONOMY", {}).get("TITLE"), description=description, color=self.color)
            embed_economy_team = Embed(description=description_team, color=self.color).set_image(url=f"attachment://{filename}")
            self.temp_embeds["economy"] = [embed_economy, embed_economy_team]
        

        def build_embeds(self):
            """Embed Match"""
            cache = self.cache
            puuid = self.puuid
            match_id = self.match_id
            response = self.response
            endpoint = self.endpoint
            filename = self.filename
            bot = self.bot

            # match info
            self.match_info = GetFormat.get_match_info(puuid, match_id, endpoint, response, self.language)
            endpoint._debug_output_json(self.match_info)
            match_info = self.match_info
            self.color = match_info["match_info"]["color"]

            # embed
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                    executor.submit(self.embed_main)
                    executor.submit(self.embed_players, filename[1])

            if len(match_info["teams"])==2: # default

                with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                    executor.submit(self.build_stats, "teamA", "teamA_" + filename[2])
                    executor.submit(self.build_stats, "teamB", "teamB_" + filename[2])
                    executor.submit(self.embed_team, response.get("TEAM_A"), "teamA", "teamA_" + filename[2])
                    executor.submit(self.embed_team, response.get("TEAM_B"), "teamB", "teamB_" + filename[2])
                    executor.submit(self.embed_economy, filename[0])

                
                self.build_graph(filename[0])
                self.build_heatmap(filename[1])
                self.embeds = [[self.temp_embeds["main"], self.temp_embeds["players"]], [self.temp_embeds["team_teamA"], self.temp_embeds["team_teamB"]], self.temp_embeds["economy"]]
                self.files = [[self.temp_files["heatmap"]], [self.temp_files["stats_teamA"], self.temp_files["stats_teamB"]], [self.temp_files["graph"]]]
            else:
                self.embeds = [[self.temp_embeds["main"], self.temp_embeds["players"]]]
                self.files = [[]]

        async def start(self):      
            self.build_embeds()

            embeds = self.embeds
            for i in range(len(embeds)):
                await self.interaction.followup.send(embeds=embeds[i], files=self.files[i], view=View.share_button(self.interaction, embeds[i]) if self.is_private_message else MISSING)
            
            for filename in self.filename:
                if os.path.isfile(f"resources/temp/" + filename): os.remove("resources/temp/" + filename)
            
            if os.path.isfile(f"resources/temp/" + "teamA_" + self.filename[2]): os.remove("resources/temp/" + "teamA_" + self.filename[2])
            if os.path.isfile(f"resources/temp/" + "teamB_" + self.filename[2]): os.remove("resources/temp/" + "teamB_" + self.filename[2])

    # ---------- MATCH HISTORY EMBED ---------- #
    
    def __career_embed(cls, match_id: str, match_data: Dict, response: Dict, endpoint, puuid: str, locale: str, bot: ValorantBot) -> discord.Embed:
        """Generate Embed Career"""
        cache = JSON.read('cache')
        
        # earned rank rating info
        earned_rr = match_data.get("RankedRatingEarned", 0)
        before_rr = match_data.get("RankedRatingBeforeUpdate", 0)
        after_rr = match_data.get("RankedRatingAfterUpdate", 0)
        before_rank = match_data.get("TierBeforeUpdate", 0)
        after_rank = match_data.get("TierAfterUpdate", 0)

        # data
        match_detail = GetFormat.get_match_info(puuid, match_id, endpoint, response, )

        def match_format(format: str):
            players = match_detail["players"]
            info = match_detail["match_info"]
            return format.format(
                tracker=GetFormat.get_trackergg_link(match_id),

                puuid=puuid,
                name=players[puuid]["name"],
                rank=players[puuid]["rank"],
                rank_emoji=GetEmoji.competitive_tier_by_bot(players[puuid]["rank_id"], bot),
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

                eco_rating=players[puuid].get("eco_rating", 0),
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
                after_rank = GetFormat.get_competitive_tier_name(after_rank),
                before_rank_emoji = GetEmoji.competitive_tier_by_bot(before_rank, bot),
                after_rank_emoji = GetEmoji.competitive_tier_by_bot(after_rank, bot)
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
        locale = str(VLR_locale)
        
        # data
        if history==None:
            history = {}
        matches = history.get("Matches", {})
        
        # embed
        all_match_stats = []
        embeds = []
        i = 0
        for match in matches:
            ret = cls.__career_embed(cls, match["MatchID"], matches[i], response, endpoint, puuid, locale, bot)
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
                    before_rank_emoji = GetEmoji.competitive_tier_by_bot(match_stats["before_raw_rank"], bot),
                    after_rank_emoji = GetEmoji.competitive_tier_by_bot(match_stats["after_raw_rank"], bot),
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
        
        embed = Embed(f"{GetEmoji.tier(uuid)} **{name}**\n{vp_emoji} {dpice} ~~{price}~~", color=Config.GetColor("items"))
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
    
    def battlepass(bot: ValorantBot, player: str, data: Dict, season: Dict, response: Dict) -> discord.Embed:
        """Embed Battle-pass"""
        
        # language
        MSG_RESPONSE = response.get("BATTLEPASS", {}).get('RESPONSE')
        MSG_COMPLETE = response.get("BATTLEPASS", {}).get('COMPLETE')
        MSG_TITLE = response.get("BATTLEPASS", {}).get('TITLE')
        MSG_HEADER = response.get("BATTLEPASS", {}).get('HEADER')
        MSG_FOOTER = response.get("BATTLEPASS", {}).get('FOOTER')
        
        embeds = []

        BTPs = GetFormat.battlepass_format(data, season, response, str(VLR_locale))
        
        for btp in BTPs:
            item = btp['data']
            reward = item['reward']
            xp = item['xp']
            act = item['act']
            tier = item['tier']
            tiers = item['tiers']
            icon = item['icon']
            cost = item['cost']
            season_end = item['end']
            item_type = item['type']
            original_type = item['original_type']
            
            def battlepass_format(format: str):
                return format.format(
                    player = player,
                    name = act,
                    reward = reward,
                    type = item_type,
                    vp_emoji = GetEmoji.get("ValorantPointIcon", bot),
                    cost = cost,
                    xp = f'{xp:,}',
                    max_xp = f'{calculate_level_xp(tier + 1):,}',
                    end=format_relative(season_end),
                    tier=tier,
                    max_tier=tiers
                )
            
            embed = Embed(battlepass_format(MSG_RESPONSE), title=battlepass_format(MSG_TITLE), color=Config.GetColor("items"))
            embed.set_footer(text=battlepass_format(MSG_FOOTER))
            embed.set_author(name=battlepass_format(MSG_HEADER))
            
            if icon:
                embed.set_thumbnail(url=icon)
            
            if tier >= 50:
                embed.color = Config.GetColor("premium")
            
            if tier == tiers:
                embed.description = battlepass_format(MSG_COMPLETE)
            embeds.append(embed)
        
        return embeds
    
    def battlepass_event(bot: ValorantBot, player: str, data: Dict, event: str, response: Dict) -> discord.Embed:
        """Embed Event-pass"""
        
        # language
        MSG_RESPONSE = response.get("EVENTPASS", {}).get('RESPONSE')
        MSG_COMPLETE = response.get("EVENTPASS", {}).get('COMPLETE')
        MSG_TITLE = response.get("EVENTPASS", {}).get('TITLE')
        MSG_HEADER = response.get("EVENTPASS", {}).get('HEADER')
        MSG_FOOTER = response.get("EVENTPASS", {}).get('FOOTER')

        event_data = JSON.read("cache")["events"].get(event)
        if event_data == None:
            return None
        
        BTP = GetFormat.battlepass_event_format(data, event, response, str(VLR_locale))
        
        item = BTP['data']
        reward = item['reward']
        xp = item['xp']
        act = item['act']
        tier = item['tier']
        tiers = item['tiers']
        icon = item['icon']
        cost = item['cost']
        season_end = item['end']
        item_type = item['type']
        original_type = item['original_type']
        
        def battlepass_format(format: str):
            return format.format(
                player = player,
                name = event_data["title"][str(VLR_locale)],
                reward = reward,
                type = item_type,
                cost = cost,
                vp_emoji = GetEmoji.get("ValorantPointIcon", bot),
                xp = f'{xp:,}',
                max_xp = f'{calculate_level_xp(tier + 1):,}',
                end=format_relative(dateutil.parser.parse(season_end)),
                tier=tier,
                max_tier=tiers
            )

        embed = Embed(battlepass_format(MSG_RESPONSE), title=battlepass_format(MSG_TITLE), color=Config.GetColor("items"))
        embed.set_footer(text=battlepass_format(MSG_FOOTER))
        embed.set_author(name=battlepass_format(MSG_HEADER))
        
        if icon:
            if original_type in ['PlayerCard', 'EquippableSkinLevel']:
                embed.set_image(url=icon)
            else:
                embed.set_thumbnail(url=icon)
        
        if tier == tiers:
            embed.description = battlepass_format(MSG_COMPLETE)
            embed.color = Config.GetColor("premium")
        
        return embed
    

    # ---------- PARTY EMBED ---------- #
    
    def member_party(player: str, puuid: str, data: Dict, endpoint: API_ENDPOINT, response: Dict, bot: ValorantBot) -> discord.Embed:
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
            current_season = mmr.get("QueueSkills", {}).get('competitive', {}).get('SeasonalInfoBySeasonID', {})
            if current_season==None: current_season = {}

            name_data = endpoint.fetch_name_by_puuid(p_puuid)

            # set data to dict
            players[p_puuid] = {
                "name": name_data[0]["GameName"] + "#" + name_data[0]["TagLine"],
                "puuid": p_puuid,
                "player_card": p["PlayerIdentity"]["PlayerCardID"],
                "player_title": p["PlayerIdentity"]["PlayerTitleID"],
                "level": p["PlayerIdentity"]["AccountLevel"],
                "rank": current_season.get(season_id, {}).get('CompetitiveTier', 0),
                "rr": current_season.get(season_id, {}).get('RankedRating', 0),
                "leaderboard": current_season[season_id]["LeaderboardRank"] if current_season.get(season_id, {}).get("LeaderboardRank", 0)>0 else "-",
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
                rank_emoji = GetEmoji.competitive_tier_by_bot(players[p_puuid]["rank"], bot),
                rr = players[p_puuid]["rr"],
                leaderboard = players[p_puuid]["leaderboard"],
                ready = players[p_puuid]["ready"],
                owner = players[p_puuid]["owner"],
                playercard = cache["playercards"][players[p_puuid]["player_card"]]["names"][str(VLR_locale)],
                title = "`" + cache["titles"][players[p_puuid]["player_title"]]["text"].get(str(VLR_locale)) + "`" if cache["titles"][players[p_puuid]["player_title"]]["text"]!=None else cache["titles"][players[p_puuid]["player_title"]].get("names", {}).get(str(VLR_locale)) or "",
                membership = players[p_puuid]["membership"]
            )

        if is_custom_game:
            def make_embed(p_puuid: str, membership: str, color: int = Config.GetColor("items")):
                players[p_puuid]["membership"] = membership
                embed_player = Embed(
                    title=format_player_info(response.get("CUSTOM", {}).get("TITLE"), p_puuid),
                    description=format_player_info(response.get("CUSTOM", {}).get("RESPONSE"), p_puuid),
                    color = color
                )
                embed_player.set_thumbnail(url=cache["playercards"][players[p_puuid]["player_card"]]["icon"]["small"])
                embed_player.set_author(
                    name=format_player_info(response.get("CUSTOM", {}).get("HEADER"), p_puuid)
                )
                embed_player.set_footer(text=format_player_info(response.get("CUSTOM", {}).get("FOOTER"), p_puuid))
                return embed_player

            for p in data["CustomGameData"]["Membership"].get("teamOne", []):
                embeds.append(make_embed(p["Subject"], response.get("MEMBERSHIP", {}).get("TEAM_B"), Config.GetColor("win")))
            for p in data["CustomGameData"]["Membership"].get("teamTwo", []):
                embeds.append(make_embed(p["Subject"], response.get("MEMBERSHIP", {}).get("TEAM_A"), Config.GetColor("lose")))
            for p in data["CustomGameData"]["Membership"].get("teamOneCoaches", []):
                embeds.append(make_embed(p["Subject"], response.get("MEMBERSHIP", {}).get("COACH_B"), Config.GetColor("win")))
            for p in data["CustomGameData"]["Membership"].get("teamTwoCoaches", []):
                embeds.append(make_embed(p["Subject"], response.get("MEMBERSHIP", {}).get("COACH_A"), Config.GetColor("lose")))
            for p in data["CustomGameData"]["Membership"].get("teamSpectate", []):
                embeds.append(make_embed(p["Subject"], response.get("MEMBERSHIP", {}).get("SPECTATE"), Config.GetColor("draw")))
                
        else:
            for p in players.values():
                p_puuid = p["puuid"]
                embed_player = Embed(
                    title=format_player_info(response.get("PLAYER", {}).get("TITLE"), p_puuid),
                    description=format_player_info(response.get("PLAYER", {}).get("RESPONSE"), p_puuid),
                    color = Config.GetColor("items")
                )
                embed_player.set_thumbnail(url=cache["playercards"][players[p_puuid]["player_card"]]["icon"]["small"])
                embed_player.set_author(
                    name=format_player_info(response.get("PLAYER", {}).get("HEADER"), p_puuid),
                    icon_url=cache["competitive_tiers"][str(players[p_puuid]["rank"])]["icon"]
                )
                embed_player.set_footer(text=format_player_info(response.get("PLAYER", {}).get("FOOTER"), p_puuid))
                embeds.append(embed_player)

        return [embed_main, embeds]

    # ---------- MEMBER EMBED ---------- #

    def member_pregame(bot: ValorantBot, player: str, data: Dict, endpoint: API_ENDPOINT, response: Dict) -> List[discord.Embed]:
        cache = JSON.read("cache")
        embeds = []

        embeds.append(Embed(description=response.get("PREGAME").get("TITLE").format(player=player)))

        for team in data.get("Teams", []):
            for player in team.get("Players"):

                def format_player(format: str) -> str:
                    rank = player.get("CompetitiveTier") if player.get("CompetitiveTier")!=0 else endpoint.get_player_tier_rank(puuid=player.get("Subject"))
                    fetch_name = endpoint.fetch_name_by_puuid(player.get("Subject"))[0]

                    return format.format(
                        puuid = player.get("Subject"),
                        name = fetch_name["GameName"] + "#" + fetch_name["TagLine"],
                        agent = cache["agents"].get(player.get("CharacterID").lower(), {}).get("names", {}).get(str(VLR_locale), response.get("PREGAME").get("NONE")),
                        agent_emoji = GetEmoji.agent_by_bot(player.get("CharacterID"), bot) if len(player.get("CharacterID"))>0 else "",
                        select = response.get("PREGAME").get("SELECTION_STATE").get(player.get("CharacterSelectionState")) if response.get("PREGAME").get("SELECTION_STATE").get(player.get("CharacterSelectionState"))!=None else response.get("PREGAME").get("SELECTION_STATE").get("None"),
                        rank = GetFormat.get_competitive_tier_name(rank),
                        rank_emoji = GetEmoji.competitive_tier_by_bot(rank, bot),
                        level = player.get("PlayerIdentity", {}).get("AccountLevel", 0),
                        title = "`" + cache["titles"].get(player.get("PlayerIdentity", {}).get("PlayerTitleID", ""), {}).get("text", {}).get(str(VLR_locale)) + "`" if cache["titles"].get(player.get("PlayerIdentity", {}).get("PlayerTitleID", ""), {}).get("text")!=None else ""
                    )
                
                embed = Embed(
                    title=format_player(response.get("PREGAME").get("PLAYER").get("TITLE")),
                    description=format_player(response.get("PREGAME").get("PLAYER").get("RESPONSE")),
                    color = Config.GetColor("items")
                )
                embed.set_thumbnail(url=cache["playercards"].get(player.get("PlayerIdentity", {}).get("PlayerCardID", ""), {}).get("icon", {}).get("small", ""))
                embeds.append(embed)
        return embeds
    
    def member_coregame(bot: ValorantBot, player: str, puuid: str, data: Dict, endpoint: API_ENDPOINT, response: Dict) -> List[discord.Embed]:
        map_id = GetFormat.get_mapuuid_from_mapid(data.get("MapID"))
        cache = JSON.read("cache")

        # teams
        teams = {}
        main_team = ""
        for playerdata in data.get("Players", []):
            if not(playerdata.get("IsCoach")):
                team = playerdata.get("TeamID")

                if teams.get(team)==None:
                    teams[team] = {}
                
                if puuid == playerdata.get("Subject"):
                    main_team = team
                
                rank = endpoint.get_player_tier_rank(puuid=playerdata.get("Subject"))
                fetch_name = endpoint.fetch_name_by_puuid(playerdata.get("Subject"))[0]

                teams[team][playerdata.get("Subject")] = {
                    "puuid": playerdata.get("Subject"),
                    "name": fetch_name["GameName"] + "#" + fetch_name["TagLine"],
                    "agent": cache["agents"].get(playerdata.get("CharacterID").lower(), {}).get("names", {}).get(str(VLR_locale), response.get("COREGAME", {}).get("UNKNOWN", "")),
                    "agent_emoji": GetEmoji.agent_by_bot(playerdata.get("CharacterID").lower(), bot) if len(playerdata.get("CharacterID"))>0 else "",
                    "rank": GetFormat.get_competitive_tier_name(rank),
                    "rank_emoji": GetEmoji.competitive_tier_by_bot(rank, bot),
                    "level": playerdata.get("PlayerIdentity", {}).get("AccountLevel", 0),
                    "title": cache["titles"].get(playerdata.get("PlayerIdentity", {}).get("PlayerTitleID", ""), {}).get("text", {}).get(str(VLR_locale)) if cache["titles"].get(playerdata.get("PlayerIdentity", {}).get("PlayerTitleID", ""), {}).get("text")!=None else "",
                    "playercard": cache["playercards"].get(playerdata.get("PlayerIdentity", {}).get("PlayerCardID", ""), {}).get("icon", {}).get("small", "")
                }

        # embed
        embeds = []

        embed = Embed(description=response.get("COREGAME").get("TITLE").format(player=player, map=cache["maps"][map_id]["names"][str(VLR_locale)]))
        embed.set_thumbnail(url=cache["maps"][map_id]["icon"])
        embed.set_image(url=cache["maps"][map_id]["listview_icon"])
        embeds.append(embed)

        for team_name,team in teams.items():
            member_text = ""

            for player in team.values():
                if member_text!="":
                    member_text += "\n"
                
                def format_player(format: str) -> str:
                    return format.format(
                        puuid = player["puuid"],
                        name = player["name"],
                        agent = player["agent"],
                        agent_emoji = player["agent_emoji"],
                        rank = player["rank"],
                        rank_emoji = player["rank_emoji"],
                        level = player["level"],
                        title = "`" + player["title"] + "`"
                    )
                
                member_text += format_player(response.get("COREGAME").get("RESPONSE"))
            
            if team_name==main_team:
                embeds.insert(1, Embed(description=member_text))
            else:
                embeds.append(Embed(description=member_text))
        return embeds

    # ---------- CUSTOM EMBED ---------- #
    @classmethod
    def custom(cls, puuid: str, data: Dict, endpoint: API_ENDPOINT, response: Dict, bot: ValorantBot, mode_rand: bool = False) -> discord.Embed:
        cache = JSON.read("cache")
        embeds = []
        
        # Select Maps
        maps_c = cache["maps"]
        del maps_c["ee613ee9-28b7-4beb-9666-08db13bb2244"]
        maps = []

        for m in maps_c.values():
            maps.append(m)
        
        r = random.randint(0, len(maps)-1)
        description = response.get("MAP", "").format(
            name = maps[r]["names"][str(VLR_locale)],
            coordinate = maps[r]["coordinates"][str(VLR_locale)],
        )
        embed_map = Embed(title=response.get("TITLE", {}).get("MAP"), description=description)
        embed_map.set_thumbnail(url=maps[r]["icon"])
        embed_map.set_image(url=maps[r]["listview_icon"])
        embeds.append(embed_map)
        

        # Select Team Member
        if data!=None:
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
                current_season = mmr.get("QueueSkills", {}).get('competitive', {}).get('SeasonalInfoBySeasonID', {})
                if current_season==None: current_season = {}

                # set data to dict
                player = {
                    "name": "",
                    "user": "",
                    "puuid": p_puuid,
                    "rank": current_season.get(season_id, {}).get('CompetitiveTier', 0),
                    "rr": current_season.get(season_id, {}).get('RankedRating', 0),
                    "leaderboard": current_season[season_id]["LeaderboardRank"] if current_season.get(season_id, {}).get("LeaderboardRank", 0)>0 else "-",
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
                    fetch_name = endpoint.fetch_name_by_puuid(p_puuid)[0]
                    player["name"] = fetch_name["GameName"] + "#" + fetch_name["TagLine"]
                else:
                    for d in data:
                        match_id = d["MatchID"]

                        match_info = GetFormat.get_match_info(p_puuid, match_id, endpoint, response)

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
                    rank_emoji = GetEmoji.competitive_tier_by_bot(player_data["rank"], bot),
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
            embeds.append(embed_team)
        else:
            embeds.append(Embed(title=response.get("TITLE", {}).get("TEAM"), description=response.get("FAILED")))

        return embeds



    # ---------- NOTIFY EMBED ---------- #
    
    def notify_specified_send(uuid: str) -> discord.Embed:
        ...
    
    @classmethod
    def notify_all_send(cls, player: str, offer: Dict, response: Dict, locale: str, bot: ValorantBot) -> discord.Embed:
        
        description_format = response.get('RESPONSE_ALL')
        
        data = GetFormat.offer_format(offer, locale)
        
        duration = data.pop('duration')
        
        description = description_format.format(username=player, duration=format_relative(datetime.utcnow() + timedelta(seconds=duration)))
        embed = Embed(description)
        embeds = [embed]
        [embeds.append(cls.__giorgio_embed(data[skin], bot, response)) for skin in data]
        
        return embeds
