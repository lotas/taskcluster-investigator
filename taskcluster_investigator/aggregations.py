def get_nested_value(nested_dict: dict, path: str) -> any:
    keys = path.split(".")
    value = nested_dict
    try:
        for key in keys:
            value = value.get(key) if key in value else value[key]
            if value is None:
                return None
        return value
    except KeyError:
        return None


def extract_fields(iterator, fields: dict[str, str]) -> list[dict[str, any]]:
    out = []
    for row in iterator:
        out.append({name: get_nested_value(row, fields[name]) for name in fields})
    return out


def summarize(rows: list[dict], fields: dict[str, str]):
    def inc_counter(group, key):
        if key not in group:
            group[key] = 0
        group[key] += 1

    groups = {k: {} for k in fields}

    for row in rows:
        for k in fields:
            field = fields[k]
            value = get_nested_value(row, field)
            inc_counter(groups[k], str(value))

    for g in fields:
        print(f"\nSummary: {g}")
        for k in groups[g]:
            print(f"{k}: {groups[g][k]}")

    return groups
