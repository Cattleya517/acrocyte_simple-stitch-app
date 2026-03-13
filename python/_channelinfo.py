_CHANNEL = [
    {"color": "0000FF", "title": "DAPI",  'rank': "00", "name": ["B", "DAPI", "HOECHST", "W0"]},
    {"color": "00FF00", "title": "CD45",  'rank': "01", "name": ["G", "FITC", "CD45"]},
    {"color": "FFFFFF", "title": "TX",    'rank': "02", "name": ["TRANSMITTEDLIGHT", "TX"]},
    {"color": "FFFF00", "title": "HER2",  'rank': "03", "name": ["Y", "TRITC", "HER2", "PDL1", "PD-L1", "TEXASRED"]},
    {"color": "FFFFFF", "title": "TL25",  'rank': "04", "name": ["K", "TL25"]},
    {"color": "FF0000", "title": "EpCam", 'rank': "05", "name": ["R", "CY5", "EPCAM"]},
]

def _normalize_name(name):
    return name.replace(" ", "").upper()

def name_to_title(name):
    if isinstance(name, str):
        normalized = _normalize_name(name)
        for prop in _CHANNEL:
            if normalized in prop["name"]:
                return prop["title"]
    return None

def name_to_rank(name):
    if isinstance(name, str):
        normalized = _normalize_name(name)
        for prop in _CHANNEL:
            if normalized in prop["name"]:
                return f"{prop['rank']}_{normalized}"
        return f"99_{normalized}"
    return None
