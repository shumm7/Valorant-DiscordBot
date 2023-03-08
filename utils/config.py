import json
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

class JSON:

    def read(filename: str, force: bool = True, dir: str = "data") -> Dict:
        """Read json file"""
        try:
            with open(dir + "/" + filename + ".json", "r", encoding='utf-8') as json_file:
                data = json.load(json_file)
        except FileNotFoundError:
            from utils.valorant.cache import create_json
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
            from utils.valorant.cache import create_json
            create_json(filename, {})
            return JSON.save(filename, data)

def LoadConfig() -> Dict:
    return JSON.read("config", dir="config")

def SaveConfig(cfg: Dict) -> None:
    JSON.save("config", cfg, "config")

def NewConfigData() -> Dict:
    return {
        "bot-start-notify": False,
        "default-language": "en-US",
        "command-description-language": "en-US",
        "owner-id": -1,
        "emoji-server-id": [-1],
        "reset-cache-when-updated": False,
        "reset-fonts-when-restart": False,
        "backup-google-drive": False,
        "article": {
            "description": 150
        },
        "emojis": {
            "default": True,
            "tier": False,
            "agent": True
        },
        "colors": {
            "default": 16598356,
            "success": 7855479,
            "error": 16598356,
            "items": 989475,
            "premium": 15841325,
            "win": 3978097,
            "draw": 4286945,
            "lose": 16598356
        },
        "commands": {
            "match": {
                "font": {
                    "heatmap-regular": ["Noto Sans CJK JP", "Regular"],
                    "heatmap-bold": ["Noto Sans CJK JP", "Bold"],
                    "graph-regular": ["Noto Sans CJK JP", "Regular"],
                    "stats-title": ["Noto Sans CJK JP", "Bold"],
                    "stats-player": ["Noto Sans CJK JP", "Bold"],
                    "stats-regular": ["Noto Sans CJK JP", "Regular"],
                    "stats-bold": ["Noto Sans CJK JP", "Bold"]
                },
                "color": {
                    "base": 0,
                    "point": 16730186,
                    "text": 16777215,
                    "text-base": 10526880,
                    "text-impact": 15265171,
                    "victory-text": 8050877,
                    "defeat-text": 16730186,
                    "draw-text": 16777215
                }
            }
        }
    }
    
def GetColor(key: str) -> int:
    return LoadConfig().get("colors", {}).get(key, 0x000000)