from __future__ import annotations

import contextlib, math
from datetime import datetime, timedelta
from pydoc import describe
from turtle import title
from typing import Awaitable, Dict, List, TYPE_CHECKING, Union

# Standard
import discord
from discord import ButtonStyle, Interaction, TextStyle, ui

from utils.valorant.endpoint import API_ENDPOINT
from .resources import get_item_type
# Local
from .useful import format_relative, GetEmoji, GetItems, JSON
from ..errors import ValorantBotError
from ..locale_v2 import ValorantTranslator

VLR_locale = ValorantTranslator()

if TYPE_CHECKING:
    from bot import ValorantBot
    from .db import DATABASE


class share_button(ui.View):
    def __init__(self, interaction: Interaction, embeds: List[discord.Embed]) -> None:
        self.interaction: Interaction = interaction
        self.embeds = embeds
        super().__init__(timeout=300)
    
    async def on_timeout(self) -> None:
        """ Called when the view times out """
        await self.interaction.edit_original_message(view=None)
    
    @ui.button(label='Share to friends', style=ButtonStyle.primary)
    async def button_callback(self, interaction: Interaction, button: ui.Button):
        await interaction.channel.send(embeds=self.embeds)
        await self.interaction.edit_original_message(content='\u200b', embed=None, view=None)


class NotifyView(discord.ui.View):
    def __init__(self, user_id: int, uuid: str, name: str, response: Dict) -> None:
        self.user_id = user_id
        self.uuid = uuid
        self.name = name
        self.response = response
        super().__init__(timeout=600)
        self.remove_notify.label = response.get('REMOVE_NOTIFY')
    
    async def interaction_check(self, interaction: Interaction) -> bool:
        if interaction.user.id == int(self.user_id):
            return True
        await interaction.response.send_message('This pagination menu cannot be controlled by you, sorry!', ephemeral=True)
        return False
    
    async def on_timeout(self) -> None:
        """ Called when the view times out """
        
        with contextlib.suppress(Exception):
            self.remve_notify.disabled = True
            await self.message.edit_original_message(view=self)
    
    @discord.ui.button(label='Remove Notify', emoji='✖️', style=ButtonStyle.red)
    async def remove_notify(self, interaction: Interaction, button: ui.Button):
        data = JSON.read('notifys')
        
        for i in range(len(data)):
            if data[i]['uuid'] == self.uuid and data[i]['id'] == str(self.user_id):
                data.pop(i)
                break
        
        JSON.save('notifys', data)
        
        self.remove_notify.disabled = True
        await interaction.response.edit_message(view=self)
        
        removed_notify = self.response.get('REMOVED_NOTIFY')
        await interaction.followup.send(removed_notify.format(skin=self.name), ephemeral=True)


class _NotifyListButton(ui.Button):
    def __init__(self, label, custom_id) -> None:
        super().__init__(
            label=label,
            style=ButtonStyle.red,
            custom_id=str(custom_id)
        )
    
    async def callback(self, interaction: Interaction) -> None:
        
        await interaction.response.defer()
        
        data: list = JSON.read('notifys')
        for i in range(len(data)):
            if data[i]['uuid'] == self.custom_id and data[i]['id'] == str(self.view.interaction.user.id):
                data.pop(i)
                break
        
        JSON.save('notifys', data)
        
        del self.view.skin_source[self.custom_id]
        self.view.update_button()
        embed = self.view.main_embed()
        await self.view.interaction.edit_original_message(embed=embed, view=self.view)


class NotifyViewList(ui.View):
    skin_source: Dict
    
    def __init__(self, interaction: Interaction, response: Dict) -> None:
        self.interaction: Interaction = interaction
        self.response = response
        self.bot: ValorantBot = getattr(interaction, "client", interaction._state._get_client())
        self.default_language = 'en-US'
        super().__init__(timeout=600)
    
    async def on_timeout(self) -> None:
        """ Called when the view times out. """
        embed = discord.Embed(color=0x2F3136, description='🕙 Timeout')
        await self.interaction.edit_original_message(embed=embed, view=None)
    
    async def interaction_check(self, interaction: Interaction) -> bool:
        if interaction.user == self.interaction.user:
            return True
        await interaction.response.send_message('This pagination menu cannot be controlled by you, sorry!', ephemeral=True)
        return False
    
    def update_button(self) -> None:
        self.clear_items()
        self.create_button()
    
    def create_button(self) -> None:
        data = self.skin_source
        for index, skin in enumerate(data, start=1):
            self.add_item(_NotifyListButton(label=index, custom_id=skin))
    
    def get_data(self) -> None:
        """ Gets the data from the cache. """
        
        database = JSON.read('notifys')
        notify_skin = [x['uuid'] for x in database if x['id'] == str(self.interaction.user.id)]
        skin_source = {}
        
        for uuid in notify_skin:
            skin = GetItems.get_skin(uuid)
            name = skin['names'][str(VLR_locale)]
            icon = skin['icon']
            
            skin_source[uuid] = {
                'name': name,
                'icon': icon,
                'price': GetItems.get_skin_price(uuid),
                'emoji': GetEmoji.tier_by_bot(uuid, self.bot)
            }
        self.skin_source = skin_source
    
    def main_embed(self) -> discord.Embed:
        """ Main embed for the view """
        
        skin_list = self.skin_source
        vp_emoji = discord.utils.get(self.bot.emojis, name='ValorantPointIcon')
        
        title = self.response.get('TITLE')
        embed = discord.Embed(description='\u200b', title=title, color=0xfd4554)
        
        click_for_remove = self.response.get('REMOVE_NOTIFY')
        
        if len(skin_list) == 0:
            description = self.response.get('DONT_HAVE_NOTIFY')
            embed.description = description
        else:
            embed.set_footer(text=click_for_remove)
            count = 0
            text_format = []
            for skin in skin_list:
                name = skin_list[skin]['name']
                icon = skin_list[skin]['icon']
                price = skin_list[skin]['price']
                emoji = skin_list[skin]['emoji']
                count += 1
                text_format.append(f"**{count}.** {emoji} **{name}**\n{vp_emoji} {price}")
            else:
                embed.description = '\n'.join(text_format)
                if len(skin_list) == 1:
                    embed.set_thumbnail(url=icon)
        
        return embed
    
    async def start(self) -> Awaitable[None]:
        """ Starts the view. """
        self.get_data()
        self.create_button()
        embed = self.main_embed()
        await self.interaction.followup.send(embed=embed, view=self)


class TwoFA_UI(ui.Modal, title='Two-factor authentication'):
    """Modal for riot login with multifactorial authentication"""
    
    def __init__(self, interaction: Interaction, db: DATABASE, cookie: dict, message: str, label: str, response: Dict) -> None:
        super().__init__(timeout=600)
        self.interaction: Interaction = interaction
        self.db = db
        self.cookie = cookie
        self.response = response
        self.two2fa.placeholder = message
        self.two2fa.label = label
    
    two2fa = ui.TextInput(
        label='Input 2FA Code',
        max_length=6,
        style=TextStyle.short
    )
    
    async def on_submit(self, interaction: Interaction) -> None:
        """ Called when the user submits the modal. """
        
        code = self.two2fa.value
        if code:
            cookie = self.cookie
            user_id = self.interaction.user.id
            auth = self.db.auth
            auth.locale_code = self.interaction.locale
            
            async def send_embed(content: str) -> Awaitable[None]:
                embed = discord.Embed(description=content, color=0xfd4554)
                if interaction.response.is_done():
                    return await interaction.followup.send(embed=embed, ephemeral=True)
                await interaction.response.send_message(embed=embed, ephemeral=True)
            
            if not code.isdigit():
                return await send_embed(f"`{code}` is not a number")
            
            auth = await auth.give2facode(code, cookie)
            
            if auth['auth'] == 'response':
                
                login = await self.db.login(user_id, auth, self.interaction.locale)
                if login['auth']:
                    return await send_embed(f"{self.response.get('SUCCESS')} **{login['player']}!**")
                
                return await send_embed(login['error'])
            
            elif auth['auth'] == 'failed':
                return await send_embed(auth['error'])
    
    async def on_error(self, interaction: Interaction, error: Exception) -> None:
        """ Called when the user submits the modal with an error. """
        print("TwoFA_UI:", error)
        embed = discord.Embed(description='Oops! Something went wrong.', color=0xfd4554)
        await interaction.response.send_message(embed=embed, ephemeral=True)


# inspired by https://github.com/giorgi-o
class BaseBundle(ui.View):
    def __init__(self, interaction: Interaction, entries: Dict, response: Dict) -> None:
        self.interaction: Interaction = interaction
        self.entries = entries
        self.response = response
        self.language = str(VLR_locale)
        self.bot: ValorantBot = getattr(interaction, "client", interaction._state._get_client())
        self.current_page: int = 0
        self.embeds: List[List[discord.Embed]] = []
        self.page_format = {}
        super().__init__()
        self.clear_items()
    
    def fill_items(self, force=False) -> None:
        self.clear_items()
        if len(self.embeds) > 1 or force:
            self.add_item(self.back_button)
            self.add_item(self.next_button)
    
    def base_embed(self, title: str, description: str, icon: str, color: int = 0x0F1923) -> discord.Embed:
        """ Base embed for the view """
        
        embed = discord.Embed(title=title, description=description, color=color)
        embed.set_thumbnail(url=icon)
        return embed
    
    def build_embeds(self, selected_bundle: int = 1) -> None:
        """ Builds the bundle embeds """
        
        vp_emoji = discord.utils.get(self.bot.emojis, name='ValorantPointIcon')
        
        embeds_list = []
        embeds = []
        
        collection_title = self.response.get('TITLE')
        
        for index, bundle in enumerate(sorted(self.entries, key=lambda c: c['names'][self.language]), start=1):
            if index == selected_bundle:
                embeds.append(discord.Embed(title=bundle['names'][self.language] + f" {collection_title}", description=f"{vp_emoji} {bundle['price']}", color=0xfd4554).set_image(url=bundle['icon']))
                
                for items in sorted(bundle['items'], key=lambda x: x['price'], reverse=True):
                    item = GetItems.get_item_by_type(items['type'], items['uuid'])
                    item_type = get_item_type(items['type'])
                    
                    emoji = GetEmoji.tier_by_bot(items['uuid'], self.bot) if item_type == 'Skins' else ''
                    icon = item['icon'] if item_type != 'Player Cards' else item['icon']['large']
                    color = 0xfd4554 if item_type == 'Skins' else 0x0F1923
                    
                    embed = self.base_embed(f"{emoji} {item['names'][self.language]}", f"{vp_emoji} {items['price']}", icon, color)
                    embeds.append(embed)
                    
                    if len(embeds) == 10:
                        embeds_list.append(embeds)
                        embeds = []
                
                if len(embeds) != 0:
                    embeds_list.append(embeds)
        
        self.embeds = embeds_list
    
    def build_featured_bundle(self, bundle: List[Dict]) -> List[discord.Embed]:
        """ Builds the featured bundle embeds """
        
        vp_emoji = discord.utils.get(self.bot.emojis, name='ValorantPointIcon')
        
        name = bundle['names'][self.language]
        
        featured_bundle_title = self.response.get('TITLE')
        
        duration = bundle['duration']
        duration_text = self.response.get('DURATION').format(duration=format_relative(datetime.utcnow() + timedelta(seconds=duration)))
        
        bundle_price = bundle['price']
        bundle_base_price = bundle['base_price']
        bundle_price_text = f"**{bundle_price}** {(f'~~{bundle_base_price}~~' if bundle_base_price != bundle_price else '')}"
        
        embed = discord.Embed(
            title=featured_bundle_title.format(bundle=name),
            description=f"{vp_emoji} {bundle_price_text}"
                        f" ({duration_text})",
            color=0xfd4554
        )
        embed.set_image(url=bundle['icon'])
        
        embed_list = []
        
        embeds = [embed]
        
        for items in sorted(bundle['items'], reverse=True, key=lambda c: c['base_price']):
            
            item = GetItems.get_item_by_type(items['type'], items['uuid'])
            item_type = get_item_type(items['type'])
            emoji = GetEmoji.tier_by_bot(items['uuid'], self.bot) if item_type == 'Skins' else ''
            icon = item['icon'] if item_type != 'Player Cards' else item['icon']['large']
            color = 0xfd4554 if item_type == 'Skins' else 0x0F1923
            
            item_price = items['price']
            item_base_price = items['base_price']
            item_price_text = f"**{item_price}** {(f'~~{item_base_price}~~' if item_base_price != item_price else '')}"
            
            embed = self.base_embed(f"{emoji} {item['names'][self.language]}", f"**{vp_emoji}** {item_price_text}", icon, color)
            
            embeds.append(embed)
            
            if len(embeds) == 10:
                embed_list.append(embeds)
                embeds = []
        
        if len(embeds) != 0:
            embed_list.append(embeds)
        
        return embed_list
    
    def build_select(self) -> None:
        """ Builds the select bundle """
        for index, bundle in enumerate(sorted(self.entries, key=lambda c: c['names']['en-US']), start=1):
            self.select_bundle.add_option(label=bundle['names'][self.language], value=index)
    
    @ui.select(placeholder='Select a bundle:')
    async def select_bundle(self, interaction: Interaction, select: ui.Select):
        self.build_embeds(int(select.values[0]))
        self.fill_items()
        self.update_button()
        embeds = self.embeds[0]
        await interaction.response.edit_message(embeds=embeds, view=self)
    
    @ui.button(label='Back')
    async def back_button(self, interaction: Interaction, button: ui.Button):
        self.current_page = 0
        embeds = self.embeds[self.current_page]
        self.update_button()
        await interaction.response.edit_message(embeds=embeds, view=self)
    
    @ui.button(label='Next')
    async def next_button(self, interaction: Interaction, button: ui.Button):
        self.current_page = 1
        embeds = self.embeds[self.current_page]
        self.update_button()
        await interaction.response.edit_message(embeds=embeds, view=self)
    
    def update_button(self) -> None:
        """ Updates the button """
        self.next_button.disabled = self.current_page == len(self.embeds) - 1
        self.back_button.disabled = self.current_page == 0
    
    async def interaction_check(self, interaction: Interaction) -> bool:
        if interaction.user == self.interaction.user:
            return True
        await interaction.response.send_message('This menus cannot be controlled by you, sorry!', ephemeral=True)
        return False
    
    async def start(self) -> Awaitable[None]:
        """ Starts the bundle view """
        
        if len(self.entries) == 1:
            self.build_embeds()
            self.fill_items()
            self.update_button()
            embeds = self.embeds[0]
            return await self.interaction.followup.send(embeds=embeds, view=self)
        elif len(self.entries) != 0:
            self.add_item(self.select_bundle)
            placeholder = self.response.get('DROPDOWN_CHOICE_TITLE')
            self.select_bundle.placeholder = placeholder
            self.build_select()
            return await self.interaction.followup.send('\u200b', view=self)
        
        not_found_bundle = self.response.get('NOT_FOUND_BUNDLE')
        raise ValorantBotError(not_found_bundle)
    
    async def start_furture(self) -> Awaitable[None]:
        """ Starts the featured bundle view """
        
        BUNDLES = []
        FBundle = self.entries['FeaturedBundle']['Bundles']
        
        for fbd in FBundle:
            get_bundle = GetItems.get_bundle(fbd["DataAssetID"])
            
            bundle_payload = {
                "uuid": fbd["DataAssetID"],
                "icon": get_bundle['icon'],
                "names": get_bundle['names'],
                "duration": fbd["DurationRemainingInSeconds"],
                "items": []
            }
            
            price = 0
            baseprice = 0
            
            for items in fbd['Items']:
                item_payload = {
                    "uuid": items["Item"]["ItemID"],
                    "type": items["Item"]["ItemTypeID"],
                    "item": GetItems.get_item_by_type(items["Item"]["ItemTypeID"], items["Item"]["ItemID"]),
                    "amount": items["Item"]["Amount"],
                    "price": items["DiscountedPrice"],
                    "base_price": items["BasePrice"],
                    "discount": items["DiscountPercent"]
                }
                price += int(items["DiscountedPrice"])
                baseprice += int(items["BasePrice"])
                bundle_payload['items'].append(item_payload)
            
            bundle_payload['price'] = price
            bundle_payload['base_price'] = baseprice
            
            BUNDLES.append(bundle_payload)
        
        if len(BUNDLES) > 1:
            return await self.interaction.followup.send('\u200b', view=SelectionFeaturedBundleView(BUNDLES, self))
        
        self.embeds = self.build_featured_bundle(BUNDLES[0])
        self.fill_items()
        self.update_button()
        await self.interaction.followup.send(embeds=self.embeds[0], view=self)

class BaseAgent(ui.View):
    def __init__(self, interaction: Interaction, entries: Dict, response: Dict) -> None:
        self.interaction: Interaction = interaction
        self.entries = entries
        self.response = response
        self.language = str(VLR_locale)
        self.bot: ValorantBot = getattr(interaction, "client", interaction._state._get_client())
        self.current_page: int = 0
        self.embeds: List[discord.Embed] = []
        self.page_format = {}
        super().__init__()
        self.clear_items()
    
    def agent_format(self, format: str, agent: Dict) -> str:
        default_language = 'en-US'

        return format.format(
            name = agent['name'][self.language],
            description = agent['description'][self.language],
            role = agent["role"]["name"][self.language],

            name_en = agent["name"][default_language],
            role_en = agent["role"]["name"][default_language],
            name_en_capital = agent["name"][default_language].upper(),
            role_en_capital = agent["role"]["name"][default_language].upper(),

            icon = agent['icon'],
            portrait = agent['portrait'],
            bust_portrait = agent['bust_portrait'],
            killfeed_portrait = agent["killfeed_portrait"],
            background = agent["background"],

            agent_emoji = GetEmoji.agent_by_bot(agent["uuid"], self.bot),
            role_emoji = GetEmoji.role_by_bot(agent["uuid"], self.bot)
        )

    def build_embeds(self, selected_agent: str, response: Dict) -> None:
        """ Builds the agent embeds """
        
        embeds = []

        for agent in self.entries:
            if agent["uuid"] == selected_agent:
                color, subcolor = agent['color'][0], agent['color'][1]

                embed = discord.Embed(
                    title=self.agent_format(response.get("TITLE", ""), agent),
                    description=self.agent_format(response.get("RESPONSE", ""), agent),
                    color=color
                )
                embed.set_author(name=self.agent_format(response.get("HEADER", ""), agent))
                embed.set_thumbnail(url=self.agent_format(response.get("THUMBNAIL", ""), agent))
                embed.set_image(url=self.agent_format("IMAGE", agent))

                embeds.append(embed)
                
                i = 0
                key_text = response.get("KEYS", {})
                keys = [key_text.get("KEY1", ""), key_text.get("KEY2", ""), key_text.get("KEY3", ""), key_text.get("KEY4", ""), key_text.get("PASSIVE", "")]
                for ability in agent["abilities"]:
                    name, description, icon = ability["name"][self.language], ability["description"][self.language], ability["icon"]
                    embed_ability = discord.Embed(title=f"{keys[i]} - {name}", description=f"{description}", color=subcolor).set_thumbnail(url=icon)
                    embeds.append(embed_ability)
                    
                    i = i + 1

        self.embeds = embeds

    
    def build_select(self) -> None:
        """ Builds the select bundle """
        for index, agent in enumerate(sorted(self.entries, key=lambda c: c['name']['en-US']), start=1):
            self.select_agent.add_option(label=agent['name'][self.language], value=agent["uuid"])
    
    @ui.select(placeholder='Select an agent:')
    async def select_agent(self, interaction: Interaction, select: ui.Select):
        self.clear_items()
        self.build_embeds(select.values[0], self.response)
        embeds = self.embeds
        await interaction.response.edit_message(embeds=embeds, view=self)
    
    async def interaction_check(self, interaction: Interaction) -> bool:
        if interaction.user == self.interaction.user:
            return True
        await interaction.response.send_message('This menus cannot be controlled by you, sorry!', ephemeral=True)
        return False
    
    async def start(self) -> Awaitable[None]:
        """ Starts the agent view """
        
        if len(self.entries) == 1:
            self.build_embeds(self.entries[0]["uuid"])
            embeds = self.embeds
            return await self.interaction.followup.send(embeds=embeds, view=self)
        elif len(self.entries) != 0:
            self.add_item(self.select_agent)
            placeholder = self.response.get('DROPDOWN_CHOICE_TITLE')
            self.select_agent.placeholder = placeholder
            self.build_select()
            return await self.interaction.followup.send('\u200b', view=self)
        
        not_found_agent = self.response.get('NOT_FOUND')
        raise ValorantBotError(not_found_agent)

class BaseWeapon(ui.View):
    def __init__(self, interaction: Interaction, entries: Dict, response: Dict) -> None:
        self.interaction: Interaction = interaction
        self.entries = entries
        self.response = response
        self.language = str(VLR_locale)
        self.bot: ValorantBot = getattr(interaction, "client", interaction._state._get_client())
        self.current_page: int = 0
        self.embeds: List[discord.Embed] = []
        self.page_format = {}
        super().__init__()
        self.clear_items()
    
    
    def floor(self, n: float, m: int = 2) -> float:
        return math.floor(n * 10 ** m) / (10 ** m)
    
    def weapon_format(self, format: str, weapon: Dict) -> str:
        default_language = 'en-US'

        
        alt_fire_mode = weapon.get("stats", {}).get("alt_fire_mode")
        alt = None
        if alt_fire_mode!=None:
            alt=self.response.get("ALT_MODE", {}).get(alt_fire_mode, "")
        
        feature = weapon.get("stats", {}).get("feature")
        feature_str = None
        if feature!=None:
            feature_str = self.response.get("FEATURE", {}).get(feature, "")

        accuracy = ""
        if weapon.get("stats", {}).get("accuracy", [None, None])[1]!=None:
            accuracy = str(self.floor(weapon.get("stats", {}).get("accuracy", [-1, -1])[0], 3)) + "/" + str(self.floor(weapon.get("stats", {}).get("accuracy", [-1, -1])[1], 3))
        else:
            accuracy = str(self.floor(weapon.get("stats", {}).get("accuracy", [-1, -1])[0], 3))

        return format.format(
            # name
            name = weapon['names'][self.language],
            name_en = weapon["names"][default_language],
            name_en_capital = weapon["names"][default_language].upper(),

            # image
            icon = weapon['icon'],
            killfeed_icon = weapon["killfeed_icon"],
            shop_icon = weapon.get("shop_icon", ""),
            fire_mode_emoji = GetEmoji.get("FireMode", self.bot),
            wall_emoji = GetEmoji.get("WallPenetration", self.bot),
            credits_emoji = GetEmoji.get("Credits", self.bot),

            # detail
            wall = self.response.get("WALL", {}).get(weapon.get("stats", {}).get("wall", "")),
            fire_mode = self.response.get("FIREMODE", {}).get(weapon.get("stats", {}).get("fire_mode", "Automatic")),

            firerate = self.floor(weapon.get("stats", {}).get("firerate", -1), 2),
            run_speed = self.floor(weapon.get("stats", {}).get("run_speed", -1), 2),
            run_speed_multiplier = math.floor(weapon.get("stats", {}).get("run_speed_multiplier", 0) * 100),
            equip_time = weapon.get("stats", {}).get("equip_time", -1),
            accuracy = accuracy,
            reload_time = weapon.get("stats", {}).get("reload_time", -1),
            magazine = weapon.get("stats", {}).get("magazine", -1),
            shotgun_pellet = weapon.get("stats", {}).get("shotgun_pellet", 1),

            # alt
            alt = alt,

            ads_zoom = weapon.get("stats", {}).get("zoom", -1),
            ads_firerate = self.floor(weapon.get("stats", {}).get("ads_firerate", -1), 3),
            ads_firerate_multiplier = math.floor(weapon.get("stats", {}).get("ads_firerate", 0) / weapon.get("stats", {}).get("firerate", -1) * 100),
            ads_run_speed = self.floor(weapon.get("stats", {}).get("ads_run_speed", -1), 3),
            ads_run_speed_multiplier = math.floor(weapon.get("stats", {}).get("ads_run_speed_multiplier", 0) * 100),
            ads_burst = weapon.get("stats", {}).get("ads_burst", 1),

            air_shotgun_pellet = weapon.get("stats", {}).get("air_shotgun_pellet", 1),
            air_distance = weapon.get("stats", {}).get("air_distance", -1),

            alt_shotgun_pellet = weapon.get("stats", {}).get("alt_shotgun_pellet", 1),
            alt_shotgun_burst = weapon.get("stats", {}).get("alt_burst", -1),

            # feature
            feature = feature_str,

            # shop
            category = weapon.get("category", {}).get("text", {}).get(self.language, ""),
            category_en = weapon.get("category", {}).get("text", {}).get(default_language, ""),
            credits = weapon.get("cost", 0)
        )

    def build_embeds(self, selected_weapon: str) -> None:
        """ Builds the weapon embeds """
        
        embeds = []
        lang = self.response

        for weapon in self.entries:
            if weapon["uuid"] == selected_weapon:
                if weapon["uuid"]=="2f59173c-4bed-b6c3-2191-dea9b58be9c7": #Melee
                    # Main
                    embed = discord.Embed(title=self.weapon_format(lang.get("DETAIL", {}).get("TITLE", ""), weapon))

                    embed.set_author(name=self.weapon_format(lang.get("DETAIL", {}).get("HEADER", ""), weapon))
                    embed.set_footer(text=self.weapon_format(lang.get("DETAIL", {}).get("FOOTER", ""), weapon))
                    embed.set_thumbnail(url=self.weapon_format(lang.get("DETAIL", {}).get("THUMBNAIL", ""), weapon))
                    embed.set_image(url=self.weapon_format(lang.get("DETAIL", {}).get("IMAGE", ""), weapon))
                    embeds.append(embed)

                    # Damage
                    embed = discord.Embed(
                        title=self.weapon_format(lang.get("DAMAGE", {}).get("TITLE", ""), weapon),
                        description=self.weapon_format(lang.get("DAMAGE", {}).get("MELEE", ""), weapon)
                    )
                    embeds.append(embed)

                else:
                    # Main
                    embed = discord.Embed(
                        title=self.weapon_format(lang.get("DETAIL", {}).get("TITLE", ""), weapon),
                        description=self.weapon_format(lang.get("DETAIL", {}).get("DESCRIPTION", ""), weapon)
                    )
                    embed.add_field(name=self.weapon_format(lang.get("DETAIL", {}).get("NAME1", ""), weapon), value=self.weapon_format(lang.get("DETAIL", {}).get("VALUE1", ""), weapon))
                    embed.add_field(name=self.weapon_format(lang.get("DETAIL", {}).get("NAME2", ""), weapon), value=self.weapon_format(lang.get("DETAIL", {}).get("VALUE2", ""), weapon))
                    embed.add_field(name=self.weapon_format(lang.get("DETAIL", {}).get("NAME3", ""), weapon), value=self.weapon_format(lang.get("DETAIL", {}).get("VALUE3", ""), weapon))
                    embed.add_field(name=self.weapon_format(lang.get("DETAIL", {}).get("NAME4", ""), weapon), value=self.weapon_format(lang.get("DETAIL", {}).get("VALUE4", ""), weapon))
                    embed.add_field(name=self.weapon_format(lang.get("DETAIL", {}).get("NAME5", ""), weapon), value=self.weapon_format(lang.get("DETAIL", {}).get("VALUE5", ""), weapon))
                    embed.add_field(name=self.weapon_format(lang.get("DETAIL", {}).get("NAME6", ""), weapon), value=self.weapon_format(lang.get("DETAIL", {}).get("VALUE6", ""), weapon))

                    embed.set_author(name=self.weapon_format(lang.get("DETAIL", {}).get("HEADER", ""), weapon))
                    embed.set_footer(text=self.weapon_format(lang.get("DETAIL", {}).get("FOOTER", ""), weapon))
                    embed.set_thumbnail(url=self.weapon_format(lang.get("DETAIL", {}).get("THUMBNAIL", ""), weapon))
                    embed.set_image(url=self.weapon_format(lang.get("DETAIL", {}).get("IMAGE", ""), weapon))

                    embeds.append(embed)

                    # Damage
                    embed = discord.Embed(
                        title=self.weapon_format(lang.get("DAMAGE", {}).get("TITLE", ""), weapon),
                        description=self.weapon_format(lang.get("DAMAGE", {}).get("DESCRIPTION", ""), weapon)
                    )
                    count = 0
                    for damage in weapon.get("stats", {}).get("damage", []):
                        def damage_format(format: str)->str:
                            shotgun = ""
                            if weapon.get("stats", {}).get("shotgun_pellet", 1)>1 and count==len(damage):
                                shotgun = self.weapon_format(lang.get("DAMAGE", {}).get("SHOTGUN", ""), weapon)

                            return format.format(
                                range_start=damage.get("range", [0, 0])[0],
                                range_end=damage.get("range", [0, 0])[1],

                                head=damage.get("damage", [0, 0, 0])[0],
                                body=damage.get("damage", [0, 0, 0])[1],
                                leg=damage.get("damage", [0, 0, 0])[2],
                                shotgun = shotgun
                            )

                        embed.add_field(name=damage_format(lang.get("DAMAGE", {}).get("RANGE", "")), value=damage_format(lang.get("DAMAGE", {}).get("RESPONSE", "")), inline=False)
                        count += 1

                    embeds.append(embed)

                    # Alt
                    alt_fire_mode = weapon.get("stats", {}).get("alt_fire_mode")
                    if alt_fire_mode!=None:
                        embed = discord.Embed(
                            title=self.weapon_format(lang.get("ALT_FIRE", {}).get("TITLE", ""), weapon),
                            description=self.weapon_format(lang.get("ALT_FIRE", {}).get("DESCRIPTION", ""), weapon)
                        )

                        if weapon.get("stats", {}).get("ads_burst", 1)==1:
                            embed.add_field(name=self.weapon_format(lang.get("ALT_FIRE", {}).get("ALT_TITLE", ""), weapon), value=self.weapon_format(lang.get("ALT_FIRE", {}).get(f"ALT_DESCRIPTION_{alt_fire_mode}", ""), weapon), inline=False)
                        else:
                            embed.add_field(name=self.weapon_format(lang.get("ALT_FIRE", {}).get("ALT_TITLE", ""), weapon), value=self.weapon_format(lang.get("ALT_FIRE", {}).get(f"ALT_DESCRIPTION_{alt_fire_mode}_BURST", ""), weapon), inline=False)
                        embeds.append(embed)
                    
                    # Feature
                    feature = weapon.get("stats", {}).get("feature")
                    if feature!=None:
                        embed = discord.Embed(
                            title=self.weapon_format(lang.get("FEATURE", {}).get("TITLE", ""), weapon),
                            description=self.weapon_format(lang.get("FEATURE", {}).get("DESCRIPTION", ""), weapon)
                        )
                        embed.add_field(name=self.weapon_format(lang.get("FEATURE", {}).get("FEATURE_TITLE", ""), weapon), value=self.weapon_format(lang.get("FEATURE", {}).get(f"FEATURE_DESCRIPTION_{feature}", ""), weapon), inline=False)
                        embeds.append(embed)


        self.embeds = embeds

    
    def build_select(self) -> None:
        """ Builds the select bundle """
        for index, weapon in enumerate(sorted(self.entries, key=lambda c: c['names']['en-US']), start=1):
            self.select_weapon.add_option(label=weapon['names'][self.language], value=weapon["uuid"])
    
    @ui.select(placeholder='Select a weapon:')
    async def select_weapon(self, interaction: Interaction, select: ui.Select):
        self.clear_items()
        self.build_embeds(select.values[0])
        embeds = self.embeds
        await interaction.response.edit_message(embeds=embeds, view=self)
    
    async def interaction_check(self, interaction: Interaction) -> bool:
        if interaction.user == self.interaction.user:
            return True
        await interaction.response.send_message('This menus cannot be controlled by you, sorry!', ephemeral=True)
        return False
    
    async def start(self) -> Awaitable[None]:
        """ Starts the weapon view """
        
        if len(self.entries) == 1:
            self.build_embeds(self.entries[0]["uuid"])
            embeds = self.embeds
            return await self.interaction.followup.send(embeds=embeds, view=self)
        elif len(self.entries) != 0:
            self.add_item(self.select_weapon)
            placeholder = self.response.get('DROPDOWN_CHOICE_TITLE')
            self.select_weapon.placeholder = placeholder
            self.build_select()
            return await self.interaction.followup.send('\u200b', view=self)
        
        not_found_weapon = self.response.get('NOT_FOUND')
        raise ValorantBotError(not_found_weapon)

class BaseCollection(ui.View):
    def __init__(self, interaction: Interaction, entries: Dict, endpoint: API_ENDPOINT, response: Dict) -> None:
        self.interaction: Interaction = interaction
        self.entries = entries
        self.response = response
        self.endpoint = endpoint
        self.language = str(VLR_locale)
        self.bot: ValorantBot = getattr(interaction, "client", interaction._state._get_client())
        self.current_page: int = 0
        self.embeds: List[List[discord.Embed]] = []
        self.page_format = {}
        super().__init__()
        self.clear_items()
    
    def fill_items(self, force=False) -> None:
        self.clear_items()
        if len(self.embeds) > 1 or force:
            self.add_item(self.back_button)
            self.add_item(self.next_button)
    
    def base_embed(self, title: str, description: str, icon: str, color: int = 0x0F1923) -> discord.Embed:
        """ Base embed for the view """
        
        embed = discord.Embed(title=title, description=description, color=color)
        embed.set_thumbnail(url=icon)
        return embed
    
    def build_embeds(self) -> None:
        """ Builds the bundle embeds """
        
        embeds_list = []
        embeds = []
        lang = self.response

        cache = JSON.read('cache')
        conv = JSON.read('conv')

        # Main
        embeds.append(
            discord.Embed(description=lang.get("TITLE", "").format(name=self.endpoint.player), color=0x0F1923)
        )
        
        # Identity
        item = self.entries.get("Identity", [])

        # Player Card
        card_embed = discord.Embed(
            title=cache["playercards"][item["PlayerCardID"]]["names"][self.language],
            color = 0x45FD9C
        ).set_author(name = self.response.get("ITEMS", {})["PLAYER_CARD"])
        #card_embed.set_thumbnail(url=cache["playercards"][item["PlayerCardID"]]["icon"]["small"])
        card_embed.set_thumbnail(url=cache["playercards"][item["PlayerCardID"]]["icon"]["large"])
        card_embed.set_image(url=cache["playercards"][item["PlayerCardID"]]["icon"]["wide"])
        embeds.append(card_embed)

        # Title
        title_embed = discord.Embed(
            title=cache["titles"][item["PlayerTitleID"]]["names"][self.language],
            description= "`" + cache["titles"][item["PlayerTitleID"]]["text"][self.language] + "`",
            color = 0x45FD9C
        ).set_author(name = self.response.get("ITEMS", {})["PLAYER_TITLE"])
        embeds.append(title_embed)

        # Levelboarder
        level_embed = discord.Embed(
            title=self.response.get("LEVELBORDERS").format(level=cache["levelborders"][item["PreferredLevelBorderID"]]["level"]),
            color = 0x45FD9C
        )
        level_embed.set_thumbnail(url = cache["levelborders"][item["PreferredLevelBorderID"]]["icon"])
        level_embed.set_author(name = self.response.get("ITEMS", {})["LEVELBORDER"])
        embeds.append(level_embed)

        # Guns
        for weapon in cache["weapons"].values():
            weapon_uuid = weapon["uuid"]

            for item in self.entries.get("Guns", []):
                if item["ID"]==weapon_uuid:
                    skin_uuid = conv["skins"][item["SkinID"]]
                    chroma_uuid = item["ChromaID"]

                    gun_embed = discord.Embed(
                        title = cache["skins"][skin_uuid]["chromas"][chroma_uuid]["names"][self.language],
                        color = 0xfd4554
                    )
                    if cache["skins"][skin_uuid]["chromas"][chroma_uuid].get("icon")!=None:
                        gun_embed.set_image(url=cache["skins"][skin_uuid]["chromas"][chroma_uuid].get("icon"))
                    else:
                        gun_embed.set_image(url=cache["skins"][skin_uuid]["icon"])
                    gun_embed.set_author(
                        name = weapon["names"][self.language],
                        icon_url = weapon.get("killfeed_icon", "")
                    )

                    if item.get("CharmID")!=None:
                        buddy_uuid = conv["buddies"][item["CharmID"]]
                        gun_embed.set_thumbnail(url=cache["buddies"][buddy_uuid]["icon"])
                        gun_embed.description = cache["buddies"][buddy_uuid]["names"][self.language]

                    embeds.append(gun_embed)

        # Sprays
        spray_slot = {
            "0814b2fe-4512-60a4-5288-1fbdcec6ca48": 0,
            "04af080a-4071-487b-61c0-5b9c0cfaac74": 1,
            "5863985e-43ac-b05d-cb2d-139e72970014": 2
        }
        spray_author = [self.response.get("ITEMS", {})["SPRAY_BEFORE"], self.response.get("ITEMS", {})["SPRAY_INGAME"], self.response.get("ITEMS", {})["SPRAY_AFTER"]]
        spray_embeds = [None,None,None]
        for item in self.entries.get("Sprays", []):
            slot = spray_slot[item["EquipSlotID"]]
            embed = discord.Embed(
                title = cache["sprays"][item["SprayID"]]["names"][self.language],
                color = 0x4563FD
            )
            if cache["sprays"][item["SprayID"]].get("animation_gif")!=None:
                embed.set_thumbnail(url=cache["sprays"][item["SprayID"]]["animation_gif"])
            else:
                embed.set_thumbnail(url=cache["sprays"][item["SprayID"]]["icon"])
            embed.set_author(name = spray_author[slot])

            spray_embeds[slot] = embed
        embeds.extend(spray_embeds)
        
        # Make embeds list
        while len(embeds) > 0:
            if len(embeds) > 10:
                embeds_list.append(embeds[:10])
                embeds = embeds[10:]
            else:
                embeds_list.append(embeds)
                embeds = []
        
        self.embeds = embeds_list
    
    @ui.button(label='Back')
    async def back_button(self, interaction: Interaction, button: ui.Button):
        self.current_page -= 1
        embeds = self.embeds[self.current_page]
        self.update_button()
        await interaction.response.edit_message(embeds=embeds, view=self)
    
    @ui.button(label='Next')
    async def next_button(self, interaction: Interaction, button: ui.Button):
        self.current_page += 1
        embeds = self.embeds[self.current_page]
        self.update_button()
        await interaction.response.edit_message(embeds=embeds, view=self)
    
    def update_button(self) -> None:
        """ Updates the button """
        self.next_button.disabled = self.current_page == len(self.embeds) - 1
        self.back_button.disabled = self.current_page == 0
    
    async def interaction_check(self, interaction: Interaction) -> bool:
        if interaction.user == self.interaction.user:
            return True
        await interaction.response.send_message('This menus cannot be controlled by you, sorry!', ephemeral=True)
        return False
    
    async def start(self) -> Awaitable[None]:
        """ Starts the bundle view """
        
        self.build_embeds()
        self.fill_items()
        self.update_button()
        embeds = self.embeds[0]
        return await self.interaction.followup.send(embeds=embeds, view=self)
    

class SelectionFeaturedBundleView(ui.View):
    def __init__(self, bundles: Dict, other_view: Union[ui.View, BaseBundle] = None):
        self.bundles = bundles
        self.other_view = other_view
        super().__init__(timeout=120)
        self.__build_select()
        self.select_bundle.placeholder = self.other_view.response.get('DROPDOWN_CHOICE_TITLE')
    
    def __build_select(self) -> None:
        """ Builds the select bundle """
        for index, bundle in enumerate(self.bundles):
            self.select_bundle.add_option(label=bundle['names'][str(VLR_locale)], value=index)
    
    @ui.select(placeholder='Select a bundle:')
    async def select_bundle(self, interaction: Interaction, select: ui.Select):
        value = select.values[0]
        bundle = self.bundles[int(value)]
        embeds = self.other_view.build_featured_bundle(bundle)
        self.other_view.fill_items()
        self.other_view.update_button()
        await interaction.response.edit_message(content=None, embeds=embeds[0], view=self.other_view)
