"""Choices of an ordered item in plain French, for the e-mails and the Stripe page.
Same labels as the shop (Haeron_guitar/app/utils/configuratorLabels.ts) : a code missing here is shown "nicely"."""

COMPONENTS = {
    "body_sup": "Corps supérieur",
    "body_inf": "Corps inférieur",
    "neck": "Manche",
    "fingerboard": "Touche",
    "mic_plate": "Plaque micro",
}

OPTIONS = {
    "material": "Matière",
    "finish": "Finition",
    "color": "Couleur",
    "wood_essence": "Essence de bois",
    "post_treatment": "Traitement de surface",
    "radius": "Radius",
}
OPTION_ORDER = list(OPTIONS)

VALUES = {
    "color_red": "Rouge",
    "color_blue": "Bleu",
    "color_green": "Vert",
    "color_black": "Noir",
    "wood": "Bois",
    "aluminium": "Aluminium",
    "painted": "Peint",
    "raw": "Brut",
    "walnut": "Noyer",
    "maple": "Érable",
    "pine": "Pin",
    "chrome": "Chromé",
    "anodised": "Anodisé",
    "polished": "Poli",
    "radius_10": '10"',
    "radius_12": '12"',
}


def prettify(code):
    text = str(code or "").replace("_", " ").strip()
    return text[:1].upper() + text[1:]


def _part_model(component_key, name):
    # "body_sup_starlight" for the component "body_sup" -> "Starlight"
    prefix = f"{component_key}_"
    return prettify(name[len(prefix):] if name.startswith(prefix) else name)


def summarize(snapshot):
    """One line per component : "Corps supérieur : Starlight · Matière aluminium · Couleur bleu"."""
    if not snapshot:
        return []
    lines = []
    for component in snapshot if isinstance(snapshot, list) else [snapshot]:
        if not isinstance(component, dict):
            continue
        key = component.get("component", "")
        product = component.get("part_model") or component.get("name")
        parts = [_part_model(key, product)] if product else []
        options = sorted(
            component.get("options", []),
            key=lambda o: OPTION_ORDER.index(o.get("name")) if o.get("name") in OPTION_ORDER else len(OPTION_ORDER),
        )
        for option in options:
            value = VALUES.get(option.get("value"), prettify(option.get("value")))
            parts.append(f"{OPTIONS.get(option.get('name'), prettify(option.get('name')))} {value.lower()}")
        if parts:
            lines.append(f"{COMPONENTS.get(key, prettify(key))} : {' · '.join(parts)}")
    return lines
