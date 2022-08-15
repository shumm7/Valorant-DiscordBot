from __future__ import annotations

import contextlib
import datetime
from typing import Literal, TYPE_CHECKING  # noqa: F401

from discord import app_commands, Interaction, ui
from discord.ext import commands, tasks
from discord.utils import MISSING

from utils.checks import owner_only
from utils.errors import (
    ValorantBotError
)
from utils.valorant import cache as Cache, useful, view as View
from utils.valorant.db import DATABASE
from utils.valorant.embed import Embed, GetEmbed
from utils.valorant.endpoint import API_ENDPOINT
from utils.valorant.local import ResponseLanguage
from utils.valorant.resources import setup_emoji
from utils.locale_v2 import ValorantTranslator

VLR_locale = ValorantTranslator()

if TYPE_CHECKING:
    from bot import ValorantBot


class ValorantCog(commands.Cog, name='Valorant'):
    """Valorant API Commands"""
    
    def __init__(self, bot: ValorantBot) -> None:
        self.bot: ValorantBot = bot
        self.endpoint: API_ENDPOINT = None
        self.db: DATABASE = None
        self.reload_cache.start()
    
    def cog_unload(self) -> None:
        self.reload_cache.cancel()
    
    def funtion_reload_cache(self, force=False) -> None:
        """ Reload the cache """
        with contextlib.suppress(Exception):
            cache = self.db.read_cache()
            valorant_version = Cache.get_valorant_version()
            if valorant_version != cache['valorant_version'] or force:
                Cache.get_cache()
                cache = self.db.read_cache()
                cache['valorant_version'] = valorant_version
                self.db.insert_cache(cache)
                print('Updated cache')
    
    @tasks.loop(minutes=30)
    async def reload_cache(self) -> None:
        """ Reload the cache every 30 minutes """
        self.funtion_reload_cache()
    
    @reload_cache.before_loop
    async def before_reload_cache(self) -> None:
        """ Wait for the bot to be ready before reloading the cache """
        await self.bot.wait_until_ready()
    
    @commands.Cog.listener()
    async def on_ready(self) -> None:
        """ When the bot is ready """
        self.db = DATABASE()
        self.endpoint = API_ENDPOINT()
    
    async def get_endpoint(self, user_id: int, locale_code: str = None, username: str = None, password: str = None) -> API_ENDPOINT:
        """ Get the endpoint for the user """
        if username is not None and password is not None:
            auth = self.db.auth
            auth.locale_code = locale_code
            data = await auth.temp_auth(username, password)
        elif username or password:
            raise ValorantBotError(f"Please provide both username and password!")
        else:
            data = await self.db.is_data(user_id, locale_code)
        data['locale_code'] = locale_code
        endpoint = self.endpoint
        endpoint.activate(data)
        return endpoint
    
    @app_commands.command(description='あなたのRiotアカウントにログインします')
    @app_commands.describe(username='ユーザーネーム', password='パスワード')
    # @dynamic_cooldown(cooldown_5s)
    async def login(self, interaction: Interaction, username: str, password: str) -> None:
        print(f"[{datetime.datetime.now()}] {interaction.user.name} issued a command /{interaction.command.name}.")

        response = ResponseLanguage(interaction.command.name, interaction.locale)
        
        user_id = interaction.user.id
        auth = self.db.auth
        auth.locale_code = interaction.locale
        authenticate = await auth.authenticate(username, password)
        
        if authenticate['auth'] == 'response':
            await interaction.response.defer(ephemeral=True)
            login = await self.db.login(user_id, authenticate, interaction.locale)
            
            if login['auth']:
                embed = Embed(f"{response.get('SUCCESS')} **{login['player']}!**")
                return await interaction.followup.send(embed=embed, ephemeral=True)
            
            raise ValorantBotError(f"{response.get('FAILED')}")
        
        elif authenticate['auth'] == '2fa':
            cookies = authenticate['cookie']
            message = authenticate['message']
            label = authenticate['label']
            modal = View.TwoFA_UI(interaction, self.db, cookies, message, label, response)
            await interaction.response.send_modal(modal)
    
    @app_commands.command(description='あなたのアカウントからログアウトします')
    # @dynamic_cooldown(cooldown_5s)
    async def logout(self, interaction: Interaction) -> None:
        print(f"[{datetime.datetime.now()}] {interaction.user.name} issued a command /{interaction.command.name}.")
        
        await interaction.response.defer(ephemeral=True)
        
        response = ResponseLanguage(interaction.command.name, interaction.locale)
        
        user_id = interaction.user.id
        if logout := self.db.logout(user_id, interaction.locale):
            if logout:
                embed = Embed(response.get('SUCCESS'))
                return await interaction.followup.send(embed=embed, ephemeral=True)
            raise ValorantBotError(response.get('FAILED'))
    
    @app_commands.command(description="あなたのアカウントのストアを表示します")
    @app_commands.describe(username='ユーザーネーム (任意)', password='パスワード (任意)')
    # @app_commands.guild_only()
    # @dynamic_cooldown(cooldown_5s)
    async def store(self, interaction: Interaction, username: str = None, password: str = None) -> None:
        print(f"[{datetime.datetime.now()}] {interaction.user.name} issued a command /{interaction.command.name}.")

        # language
        response = ResponseLanguage(interaction.command.name, interaction.locale)
        
        # check if user is logged in
        is_private_message = True if username is not None or password is not None else False
        
        await interaction.response.defer(ephemeral=is_private_message)
        
        # get endpoint
        endpoint = await self.get_endpoint(interaction.user.id, interaction.locale, username, password)
        
        # fetch skin price
        skin_price = endpoint.store_fetch_offers()
        self.db.insert_skin_price(skin_price)
        
        # data
        data = endpoint.store_fetch_storefront()
        embeds = GetEmbed.store(endpoint.player, data, response, self.bot)
        await interaction.followup.send(embeds=embeds, view=View.share_button(interaction, embeds) if is_private_message else MISSING)
    
    @app_commands.command(description='あなたのアカウントのVP/RPを表示します')
    @app_commands.describe(username='ユーザーネーム (任意)', password='パスワード (任意)')
    @app_commands.guild_only()
    # @dynamic_cooldown(cooldown_5s)
    async def point(self, interaction: Interaction, username: str = None, password: str = None) -> None:
        print(f"[{datetime.datetime.now()}] {interaction.user.name} issued a command /{interaction.command.name}.")

        # check if user is logged in
        is_private_message = True if username is not None or password is not None else False
        
        await interaction.response.defer(ephemeral=is_private_message)
        
        response = ResponseLanguage(interaction.command.name, interaction.locale)
        
        # endpoint
        endpoint = await self.get_endpoint(interaction.user.id, interaction.locale, username, password)
        
        # data
        data = endpoint.store_fetch_wallet()
        embed = GetEmbed.point(endpoint.player, data, response, self.bot)
        
        await interaction.followup.send(embed=embed, view=View.share_button(interaction, [embed]) if is_private_message else MISSING)


    @app_commands.command(description='あなたのアカウントのランク/RRを表示します')
    @app_commands.describe(username='ユーザーネーム (任意)', password='パスワード (任意)')
    @app_commands.guild_only()
    # @dynamic_cooldown(cooldown_5s)
    async def rank(self, interaction: Interaction, username: str = None, password: str = None) -> None:
        print(f"[{datetime.datetime.now()}] {interaction.user.name} issued a command /{interaction.command.name}.")

        # check if user is logged in
        is_private_message = True if username is not None or password is not None else False
        
        await interaction.response.defer(ephemeral=is_private_message)
        
        response = ResponseLanguage(interaction.command.name, interaction.locale)
        
        # endpoint
        endpoint = await self.get_endpoint(interaction.user.id, interaction.locale, username, password)
        
        # data
        data = endpoint.fetch_player_mmr()
        embed = GetEmbed.rank(endpoint.player, data, response, endpoint, self.bot)
        
        await interaction.followup.send(embed=embed, view=View.share_button(interaction, [embed]) if is_private_message else MISSING)
    

    @app_commands.command(description='過去の対戦結果を表示します')
    @app_commands.describe(username='ユーザーネーム (任意)', password='パスワード (任意)', matches='読み込むマッチ数 (1～8)', queue='読み込むマッチキュー')
    # @dynamic_cooldown(cooldown_5s)
    async def career(self, interaction: Interaction, matches: int = 1, queue: Literal['All', 'Competitive', 'Unrated', 'Deathmatch', 'Escalation', 'Replication', 'Spike Rush', 'Custom', 'Snowball Fight', 'New Map']="Competitive", username: str = None, password: str = None) -> None:
        print(f"[{datetime.datetime.now()}] {interaction.user.name} issued a command /{interaction.command.name}.")

        # limit of argument "matches"
        match_limit = 8
        
        # check if user is logged in
        is_private_message = True if username is not None or password is not None else False
        
        await interaction.response.defer(ephemeral=is_private_message)
        
        response = ResponseLanguage(interaction.command.name, interaction.locale)
        
        # endpoint
        endpoint = await self.get_endpoint(interaction.user.id, interaction.locale, username, password)

        # queue
        if queue == "All":
            queue = ""
        elif queue=="Competitive":
            queue="competitive"
        elif queue=="Unrated":
            queue="unrated"
        elif queue=="Deathmatch":
            queue="deathmatch"
        elif queue=="Escalation":
            queue="ggteam"
        elif queue=="Replication":
            queue="onefa"
        elif queue=="Spike Rush":
            queue="spikerush"
        elif queue=="Custom":
            queue="custom"
        elif queue=="Snowball Fight":
            queue="snowball"
        elif queue=="newmap":
            queue="newmap"
        
        # data
        if matches<=0 or matches>match_limit:
            raise ValorantBotError(response.get('FAILED').format(limit=match_limit))
        data = endpoint.fetch_match_history(index=20, queue=queue, not_found_error=False)
        endpoint._debug_output_json(data, "data.json")
        if len(data.get("Matches", [])) > matches:
            data["Matches"] = data["Matches"][:matches]
        
        embeds = GetEmbed.career(endpoint.player, endpoint.puuid, data, response, endpoint, queue, self.bot)
        
        await interaction.followup.send(embeds=embeds, view=View.share_button(interaction, embeds) if is_private_message else MISSING)

    @app_commands.command(description='対戦結果の詳細を表示します')
    @app_commands.describe(username='ユーザーネーム (任意)', password='パスワード (任意)', match_id='マッチのID (任意)')
    # @dynamic_cooldown(cooldown_5s)
    async def match(self, interaction: Interaction, match_id: str = "", username: str = None, password: str = None) -> None:
        print(f"[{datetime.datetime.now()}] {interaction.user.name} issued a command /{interaction.command.name}.")

        # check if user is logged in
        is_private_message = True if username is not None or password is not None else False
        
        await interaction.response.defer(ephemeral=is_private_message)
        
        response = ResponseLanguage("match", interaction.locale)
        
        # endpoint
        endpoint = await self.get_endpoint(interaction.user.id, interaction.locale, username, password)
        
        # data
        if len(match_id)==0:
            data = endpoint.fetch_match_history(index=1)["Matches"]
            if len(data)==1:
                match_id = data[0]["MatchID"]

        ret = GetEmbed.match(endpoint.player, endpoint.puuid, match_id, response, endpoint, self.bot)
        embeds, graph = ret[0], ret[1]

        if graph==None:
            await interaction.followup.send(embeds=embeds, view=View.share_button(interaction, embeds) if is_private_message else MISSING)
        else:
            if len(embeds)>2:
                await interaction.followup.send(embeds=embeds[:2], file=graph[0], view=View.share_button(interaction, embeds[:2]) if is_private_message else MISSING)
                await interaction.followup.send(embeds=embeds[2:4], view=View.share_button(interaction, embeds[2:4]) if is_private_message else MISSING)
                await interaction.followup.send(embeds=embeds[4:], file=graph[1], view=View.share_button(interaction, embeds[4:]) if is_private_message else MISSING)
            else:
                await interaction.followup.send(embeds=embeds, files=graph, view=View.share_button(interaction, embeds) if is_private_message else MISSING)
    
    @app_commands.command(description='あなたのアカウントのデイリー/ウィークリーミッションの進捗を表示します')
    @app_commands.describe(username='ユーザーネーム (任意)', password='パスワード (任意)')
    # @dynamic_cooldown(cooldown_5s)
    async def mission(self, interaction: Interaction, username: str = None, password: str = None) -> None:
        print(f"[{datetime.datetime.now()}] {interaction.user.name} issued a command /{interaction.command.name}.")

        # check if user is logged in
        is_private_message = True if username is not None or password is not None else False
        
        await interaction.response.defer(ephemeral=is_private_message)
        
        response = ResponseLanguage(interaction.command.name, interaction.locale)
        
        # endpoint
        endpoint = await self.get_endpoint(interaction.user.id, interaction.locale, username, password)
        
        # data
        data = endpoint.fetch_contracts()
        embed = GetEmbed.mission(endpoint.player, data, response)
        
        await interaction.followup.send(embed=embed, view=View.share_button(interaction, [embed]) if is_private_message else MISSING)
    
    @app_commands.command(description='あなたのアカウントのナイトマーケットを表示します')
    @app_commands.describe(username='ユーザーネーム (任意)', password='パスワード (任意)')
    # @dynamic_cooldown(cooldown_5s)
    async def nightmarket(self, interaction: Interaction, username: str = None, password: str = None) -> None:
        print(f"[{datetime.datetime.now()}] {interaction.user.name} issued a command /{interaction.command.name}.")

        # check if user is logged in
        is_private_message = True if username is not None or password is not None else False
        
        await interaction.response.defer(ephemeral=is_private_message)
        
        # language
        response = ResponseLanguage(interaction.command.name, interaction.locale)
        
        # endpoint
        endpoint = await self.get_endpoint(interaction.user.id, interaction.locale, username, password)
        
        # fetch skin price
        skin_price = endpoint.store_fetch_offers()
        self.db.insert_skin_price(skin_price)
        
        # data
        data = endpoint.store_fetch_storefront()
        embeds = GetEmbed.nightmarket(endpoint.player, data, self.bot, response)
        
        await interaction.followup.send(embeds=embeds, view=View.share_button(interaction, embeds) if is_private_message else MISSING)
    
    @app_commands.command(description='あなたのアカウントのバトルパスのティアを表示します')
    @app_commands.describe(username='ユーザーネーム (任意)', password='パスワード (任意)')
    # @dynamic_cooldown(cooldown_5s)
    async def battlepass(self, interaction: Interaction, username: str = None, password: str = None) -> None:
        print(f"[{datetime.datetime.now()}] {interaction.user.name} issued a command /{interaction.command.name}.")

        # check if user is logged in
        is_private_message = True if username is not None or password is not None else False
        
        await interaction.response.defer(ephemeral=is_private_message)
        
        # language
        response = ResponseLanguage(interaction.command.name, interaction.locale)
        
        # endpoint
        endpoint = await self.get_endpoint(interaction.user.id, interaction.locale, username, password)
        
        # data
        data = endpoint.fetch_contracts()
        content = endpoint.fetch_content()
        season = useful.get_season_by_content(content)
        
        embed = GetEmbed.battlepass(endpoint.player, data, season, response)
        
        await interaction.followup.send(embed=embed, view=View.share_button(interaction, [embed]) if is_private_message else MISSING)
    
    # inspired by https://github.com/giorgi-o
    @app_commands.command(description="スキンセットの詳細を表示します")
    @app_commands.describe(bundle="スキンセットの名前")
    @app_commands.guild_only()
    # @dynamic_cooldown(cooldown_5s)
    async def bundle(self, interaction: Interaction, bundle: str) -> None:
        print(f"[{datetime.datetime.now()}] {interaction.user.name} issued a command /{interaction.command.name}.")

        await interaction.response.defer()
        
        response = ResponseLanguage(interaction.command.name, interaction.locale)
        
        # cache
        cache = self.db.read_cache()
        
        # default language language
        default_language = 'en-US'
        
        # find bundle
        find_bundle_en_US = [cache['bundles'][i] for i in cache['bundles'] if bundle.lower() in cache['bundles'][i]['names'][default_language].lower()]
        find_bundle_locale = [cache['bundles'][i] for i in cache['bundles'] if bundle.lower() in cache['bundles'][i]['names'][str(VLR_locale)].lower()]
        find_bundle = find_bundle_en_US if len(find_bundle_en_US) > 0 else find_bundle_locale
        
        # bundle view
        view = View.BaseBundle(interaction, find_bundle, response)
        await view.start()
    
    # inspired by https://github.com/giorgi-o
    @app_commands.command(description="注目のスキンセットを表示します")
    # @dynamic_cooldown(cooldown_5s)
    async def bundles(self, interaction: Interaction) -> None:
        print(f"[{datetime.datetime.now()}] {interaction.user.name} issued a command /{interaction.command.name}.")

        await interaction.response.defer()
        
        response = ResponseLanguage(interaction.command.name, interaction.locale)
        
        # endpoint
        endpoint = await self.get_endpoint(interaction.user.id, interaction.locale)
        
        # data
        bundle_entries = endpoint.store_fetch_storefront()
        
        # bundle view   
        view = View.BaseBundle(interaction, bundle_entries, response)
        await view.start_furture()
    
    @app_commands.command(description="エージェントの詳細を表示します")
    @app_commands.describe(agent="エージェントの名前")
    @app_commands.guild_only()
    # @dynamic_cooldown(cooldown_5s)
    async def agent(self, interaction: Interaction, agent: str) -> None:
        print(f"[{datetime.datetime.now()}] {interaction.user.name} issued a command /{interaction.command.name}.")

        await interaction.response.defer()
        
        response = ResponseLanguage(interaction.command.name, interaction.locale)
        
        # cache
        cache = self.db.read_cache()
        
        # default language language
        default_language = 'en-US'
        
        
        # find agents
        find_agent_en_US = []
        find_agent_locale = []

        
        for item_key, item_agent in cache['agents'].items():
            if agent == "all":
                data = item_agent
                data["uuid"] = item_key
                find_agent_en_US.append(data)
            else:
                if agent.lower() in cache['agents'][item_key]['name'][default_language].lower():
                    data = item_agent
                    data["uuid"] = item_key
                    find_agent_en_US.append(data)
                
                if agent.lower() in cache['agents'][item_key]['name'][str(VLR_locale)].lower():
                    data = item_agent
                    data["uuid"] = item_key
                    find_agent_locale.append(data)
            
        find_agent = find_agent_en_US if len(find_agent_en_US) > 0 else find_agent_locale

        # agents view
        view = View.BaseAgent(interaction, find_agent, response)
        await view.start()

    # credit https://github.com/giorgi-o
    # https://github.com/giorgi-o/SkinPeek/wiki/How-to-get-your-Riot-cookies
    @app_commands.command()
    @app_commands.describe(cookie="Cookie")
    async def cookies(self, interaction: Interaction, cookie: str) -> None:
        """ Cookieを使用してあなたのアカウントにログインします """
        print(f"[{datetime.datetime.now()}] {interaction.user.name} issued a command /{interaction.command.name}.")

        await interaction.response.defer(ephemeral=True)
        
        # language
        response = ResponseLanguage(interaction.command.name, interaction.locale)
        
        login = await self.db.cookie_login(interaction.user.id, cookie, interaction.locale)
        
        if login['auth']:
            embed = Embed(f"{response.get('SUCCESS')} **{login['player']}!**")
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        view = ui.View()
        view.add_item(ui.Button(label="Tutorial", emoji="🔗", url="https://youtu.be/cFMNHEHEp2A"))
        await interaction.followup.send(f"{response.get('FAILURE')}", view=view, ephemeral=True)
    
    @app_commands.command(description='あなたの所属するパーティの情報を表示します')
    @app_commands.describe(username='ユーザーネーム (任意)', password='パスワード (任意)')
    # @dynamic_cooldown(cooldown_5s)
    async def party(self, interaction: Interaction, username: str = None, password: str = None) -> None:
        print(f"[{datetime.datetime.now()}] {interaction.user.name} issued a command /{interaction.command.name}.")

        # check if user is logged in
        is_private_message = True if username is not None or password is not None else False
        
        await interaction.response.defer(ephemeral=is_private_message)
        
        response = ResponseLanguage(interaction.command.name, interaction.locale)
        
        # endpoint
        endpoint = await self.get_endpoint(interaction.user.id, interaction.locale, username, password)
        
        # data
        data = endpoint.fetch_partyid_from_puuid()
        if data==None:
            raise ValorantBotError("Failed to fetch partyid")
        endpoint._debug_output_json(data)

        embed = Embed("test command worked fine")
        
        await interaction.followup.send(embed=embed, view=View.share_button(interaction, [embed]) if is_private_message else MISSING)

    # ---------- ROAD MAP ---------- #
    
    # @app_commands.command()
    # async def contract(self, interaction: Interaction) -> None:
    #     # change agent contract
    
    # @app_commands.command()
    # async def party(self, interaction: Interaction) -> None:
    #     # curren party
    #     # pick agent
    #     # current map
    
    # @app_commands.command()
    # async def career(self, interaction: Interaction) -> None:
    #     # match history
    
    # ---------- DEBUGs ---------- #
    
    @app_commands.command(description='このBotのデバッグをします')
    @app_commands.describe(bug="直したいバグ")
    @app_commands.guild_only()
    @owner_only()
    async def debug(self, interaction: Interaction, bug: Literal['Skin price not loading', 'Emoji not loading', 'Cache not loading', 'Too much old emojis']) -> None:
        print(f"[{datetime.datetime.now()}] {interaction.user.name} issued a command /{interaction.command.name}.")

        await interaction.response.defer(ephemeral=True)
        
        response = ResponseLanguage(interaction.command.name, interaction.locale)
        
        if bug == 'Skin price not loading':
            # endpoint
            endpoint = await self.get_endpoint(interaction.user.id, interaction.locale)
            
            # fetch skin price
            skin_price = endpoint.store_fetch_offers()
            self.db.insert_skin_price(skin_price, force=True)

            success = response.get('SUCCESS')
            await interaction.followup.send(embed=Embed(success.format(bug=bug)))
        
        elif bug == 'Emoji not loading':
            ret = await setup_emoji(self.bot, interaction.guild, interaction.locale, force=True)
            success = response.get('SUCCESS')
            await interaction.followup.send(embed=Embed(success.format(bug=bug) + "\n\n" + ret))
        
        elif bug == 'Too much old emojis':
            ret = await setup_emoji(self.bot, interaction.guild, interaction.locale, force=True, reset=True)
            success = response.get('SUCCESS')
            await interaction.followup.send(embed=Embed(success.format(bug=bug) + "\n\n" + ret))
        
        elif bug == 'Cache not loading':
            self.funtion_reload_cache(force=True)
            success = response.get('SUCCESS')
            await interaction.followup.send(embed=Embed(success.format(bug=bug)))
        

async def setup(bot: ValorantBot) -> None:
    await bot.add_cog(ValorantCog(bot))
