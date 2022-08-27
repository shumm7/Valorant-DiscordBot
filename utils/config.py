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
    return JSON.read("config", "config")

def SaveConfig(cfg: Dict) -> None:
    JSON.save("config", cfg, "config")