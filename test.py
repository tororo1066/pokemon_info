import json
import pandas as pd
import requests

pokemon = json.load(open("pokemon/pokemon.json", encoding="utf-8"))

url = "https://yakkun.com/sv/pokemon_weight.htm"

headers = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:61.0) Gecko/20100101 Firefox/61.0"}

response = requests.get(url, headers=headers)

data = pd.read_html(response.content, header=0)[0]

for da in data.values:
    print(da)
    if da[2] in pokemon.keys():
        pokemon[da[2]]["weight"] = da[4]

json.dump(pokemon, open("pokemon/pokemon.json", "w", encoding="utf-8"), indent=2, ensure_ascii=False, sort_keys=False)

print(data)