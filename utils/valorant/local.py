"""
I WILL REMOVE THIS FILE AFTER THE LOCALIZATION V2 IS DONE
"""

from __future__ import annotations

import contextlib
import json
from typing import Any, Dict

# credit by /giorgi-o/

Locale = {
    'en-US': 'en-US',  # american_english
    'en-GB': 'en-US',  # british_english
    'ja': 'ja-JP',  # japanese
}


def InteractionLanguage(local_code: str) -> Dict[str, Any]:
    return Locale.get(str(local_code), 'en-US')


def __LocalRead(filename: str) -> Dict:
    data = {}
    try:
        with open(f"lang/{filename}.json", "r", encoding='utf-8') as json_file:
            data = json.load(json_file)
    except FileNotFoundError:
        return __LocalRead('en-US')
    return data


def ResponseLanguage(command_name: str, local_code: str) -> Dict[str, Any]:
    local_code = verify_localcode(local_code)
    local = {}
    if command_name==None or len(command_name)==0:
        with contextlib.suppress(KeyError):
            local_dict = __LocalRead(local_code)
            local = local_dict['commands']
        return local
    else:
        with contextlib.suppress(KeyError):
            local_dict = __LocalRead(local_code)
            local = local_dict['commands'][str(command_name)]
        return local


def LocalErrorResponse(value: str, local_code: str) -> Dict[str, Any]:
    local_code = verify_localcode(local_code)
    local = {}
    with contextlib.suppress(KeyError):
        local_dict = __LocalRead(local_code)
        local = local_dict['errors'][value]
    return local
    

def verify_localcode(local_code: str) -> str:
    if local_code in ['en-US', 'en-GB']:
        return 'en-US'
    elif local_code in ['ja-JP']:
        return 'ja'
    return local_code
