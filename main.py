# coding: utf-8

import base64
import enum
import io
import json
import os
import sys
import threading
import time
import tkinter as tk
from tkinter import ttk
from typing import Dict

import Levenshtein
import cv2
import numpy as np
import pyocr
import pyocr.builders
from PIL import Image, ImageFont
from PIL import ImageDraw
from numpy import floor
from obswebsocket import obsws, requests

pyocr.tesseract.TESSERACT_CMD = r'C:\\Program Files\\Tesseract-OCR\\tesseract.exe'

tools = pyocr.get_available_tools()
if len(tools) == 0:
    print("No OCR tool found")
    print("Please install Tesseract-OCR.")
    sys.exit(1)
tool = tools[0]


# HPは性格で変わらないけど管理のしやすさ重視で追加
class Character(enum.Enum):
    SAMISHIGARI = ("さみしがり", [1.0, 1.1, 0.9, 1.0, 1.0, 1.0])
    IJIPPARI = ("いじっぱり", [1.0, 1.1, 1.0, 0.9, 1.0, 1.0])
    YANCHA = ("やんちゃ", [1.0, 1.1, 1.0, 1.0, 0.9, 1.0])
    YUUKAN = ("ゆうかん", [1.0, 1.1, 1.0, 1.0, 1.0, 0.9])
    ZUBUTOI = ("ずぶとい", [1.0, 0.9, 1.1, 1.0, 1.0, 1.0])
    WANPAKU = ("わんぱく", [1.0, 1.0, 1.1, 0.9, 1.0, 1.0])
    NOUTENKI = ("のうてんき", [1.0, 1.0, 1.1, 1.0, 0.9, 1.0])
    NONKI = ("のんき", [1.0, 1.0, 1.1, 1.0, 0.9, 1.0])
    HIKAEME = ("ひかえめ", [1.0, 0.9, 1.0, 1.1, 1.0, 1.0])
    OTTORI = ("おっとり", [1.0, 1.0, 0.9, 1.1, 1.0, 1.0])
    UKKARIYA = ("うっかりや", [1.0, 1.0, 1.0, 1.1, 0.9, 1.0])
    REISEI = ("れいせい", [1.0, 1.0, 1.0, 1.1, 1.0, 0.9])
    ODAYAKA = ("おだやか", [1.0, 0.9, 1.0, 1.0, 1.1, 1.0])
    OTONASII = ("おとなしい", [1.0, 1.0, 0.9, 1.0, 1.1, 1.0])
    SINTYOU = ("しんちょう", [1.0, 1.0, 1.0, 0.9, 1.1, 1.0])
    NAMAIKI = ("なまいき", [1.0, 1.0, 1.0, 1.0, 1.1, 0.9])
    OKUBYOU = ("おくびょう", [1.0, 0.9, 1.0, 1.0, 1.0, 1.1])
    SEKKATI = ("せっかち", [1.0, 1.0, 0.9, 1.0, 1.0, 1.1])
    YOUKI = ("ようき", [1.0, 1.0, 1.0, 0.9, 1.0, 1.1])
    MUJAKI = ("むじゃき", [1.0, 1.0, 1.0, 1.0, 0.9, 1.1])
    MAJIME = ("まじめ", [1.0, 1.0, 1.0, 1.0, 1.0, 1.0])

    def __init__(self, japanese, upper):
        self.japanese = japanese
        self.upper = upper


# ノーマル,ほのお,みず,でんき,くさ,こおり,かくとう,どく,じめん,ひこう,エスパー,むし,いわ,ゴースト,ドラゴン,あく,はがね,フェアリー
class Weakness(enum.Enum):
    NORMAL = (0, [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 0.5, 0.0, 1.0, 1.0, 0.5, 1.0])
    FIRE = (1, [1.0, 0.5, 0.5, 1.0, 2.0, 2.0, 1.0, 1.0, 1.0, 1.0, 1.0, 2.0, 0.5, 1.0, 0.5, 1.0, 2.0, 1.0])
    WATER = (2, [1.0, 2.0, 0.5, 1.0, 0.5, 1.0, 1.0, 1.0, 2.0, 1.0, 1.0, 1.0, 2.0, 1.0, 0.5, 1.0, 1.0, 1.0])
    ELECTRIC = (3, [1.0, 1.0, 2.0, 0.5, 0.5, 1.0, 1.0, 1.0, 0.0, 2.0, 1.0, 1.0, 1.0, 1.0, 0.5, 1.0, 1.0, 1.0])
    GRASS = (4, [1.0, 0.5, 2.0, 1.0, 0.5, 1.0, 1.0, 0.5, 2.0, 0.5, 1.0, 0.5, 2.0, 1.0, 0.5, 1.0, 0.5, 1.0])
    ICE = (5, [1.0, 0.5, 0.5, 1.0, 2.0, 0.5, 1.0, 1.0, 2.0, 2.0, 1.0, 1.0, 1.0, 1.0, 2.0, 1.0, 0.5, 1.0])
    FIGHTING = (6, [2.0, 1.0, 1.0, 1.0, 1.0, 2.0, 1.0, 0.5, 1.0, 0.5, 0.5, 0.5, 2.0, 0.0, 1.0, 2.0, 2.0, 0.5])
    POISON = (7, [1.0, 1.0, 1.0, 1.0, 2.0, 1.0, 1.0, 0.5, 0.5, 1.0, 1.0, 1.0, 0.5, 0.5, 1.0, 1.0, 0.0, 2.0])
    GROUND = (8, [1.0, 2.0, 1.0, 2.0, 0.5, 1.0, 1.0, 2.0, 1.0, 0.0, 1.0, 0.5, 2.0, 1.0, 1.0, 1.0, 2.0, 1.0])
    FLYING = (9, [1.0, 1.0, 1.0, 0.5, 2.0, 1.0, 2.0, 1.0, 1.0, 1.0, 1.0, 2.0, 0.5, 1.0, 1.0, 1.0, 0.5, 1.0])
    PSYCHIC = (10, [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 2.0, 2.0, 1.0, 1.0, 0.5, 1.0, 1.0, 1.0, 1.0, 0.0, 0.5, 1.0])
    BUG = (11, [1.0, 0.5, 1.0, 1.0, 2.0, 1.0, 0.5, 0.5, 1.0, 0.5, 2.0, 1.0, 1.0, 0.5, 1.0, 2.0, 0.5, 0.5])
    ROCK = (12, [1.0, 2.0, 1.0, 1.0, 1.0, 2.0, 0.5, 1.0, 0.5, 2.0, 1.0, 2.0, 1.0, 1.0, 1.0, 1.0, 0.5, 1.0])
    GHOST = (13, [0.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 2.0, 1.0, 1.0, 2.0, 1.0, 0.5, 1.0, 1.0])
    DRAGON = (14, [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 2.0, 1.0, 0.5, 0.0])
    DARK = (15, [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 0.5, 1.0, 1.0, 1.0, 2.0, 1.0, 1.0, 2.0, 1.0, 0.5, 1.0, 0.5])
    STEEL = (16, [1.0, 0.5, 0.5, 0.5, 1.0, 2.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 2.0, 1.0, 1.0, 1.0, 0.5, 2.0])
    FAIRY = (17, [1.0, 0.5, 1.0, 1.0, 1.0, 1.0, 2.0, 0.5, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 2.0, 2.0, 0.5, 1.0])

    def __init__(self, index, multi: list[float]):
        self.index = index
        self.multi = multi


class PokeData:
    name = ""
    enable = False
    state = {}
    upper = {}
    moves = []
    character = Character.MAJIME


move_data = json.load(open("moves/moves.json", "r", encoding="utf-8_sig"))
pokemon_data = json.load(open("pokemon/pokemon.json", "r", encoding="utf-8_sig"))
pick_poke_list: dict[str, PokeData] = dict()
poke_spec_str: tk.StringVar
poke_spec_suggest: tk.StringVar
move_spec_str: tk.StringVar
move_spec_suggest: tk.StringVar
enemy_poke_spec: tk.StringVar
enemy_poke_suggest: tk.StringVar
move_list: list[tk.StringVar] = list()
move_damage_list: list[tk.StringVar] = list()
move_h252_damage_list: list[tk.StringVar] = list()
move_hbd252_damage_list: list[tk.StringVar] = list()

now = False
end = False

now_pokemon: PokeData


def tk_main():
    global poke_spec_str
    global move_spec_str
    global poke_spec_suggest
    global move_spec_suggest
    global enemy_poke_spec
    global enemy_poke_suggest
    global move_list
    global move_damage_list

    def remove_all_items():
        global end
        for x in ws.call(requests.GetSourcesList()).getSources():
            if str(x["name"]).startswith("info"):
                ws.call(requests.DeleteSceneItem(x["name"]))
        ws.disconnect()
        end = True
        exit(2)

    def save_poke():
        pick_poke_list.clear()
        for x, y, state_list, upper_list, moves, seikaku in poke_selects:
            data = PokeData()
            data.name = x.get()
            data.enable = y.get()

            for state_index, single_state in enumerate(["H", "A", "B", "C", "D", "S"]):
                data.state[single_state] = state_list[state_index].get()
                data.upper[single_state] = upper_list[state_index].get()
            for move in moves:
                data.moves.append(move.get())
            data.character = next((f for f in list(Character) if f.japanese == seikaku.get()), None)
            pick_poke_list[x.get()] = data
        poke_save_info_str.set("Saved")

        def delete_saved():
            time.sleep(3)
            poke_save_info_str.set("")

        threading.Thread(target=delete_saved).start()

    gui = tk.Tk()
    gui.title("Pokémon Info")
    gui.geometry("1900x550")
    poke_spec_str = tk.StringVar()
    move_spec_str = tk.StringVar()
    enemy_poke_spec = tk.StringVar()
    poke_spec_suggest = tk.StringVar()
    move_spec_suggest = tk.StringVar()
    enemy_poke_suggest = tk.StringVar()
    for i in range(0, 4):
        move_list.append(tk.StringVar())
        move_damage_list.append(tk.StringVar())
        move_h252_damage_list.append(tk.StringVar())
        move_hbd252_damage_list.append(tk.StringVar())
    tk.Button(master=gui, text="close", foreground='red', command=remove_all_items, width=10).place(x=100, y=300)

    poke_list = list(pokemon_data.keys())

    poke_selects = list(())

    def state_int_only(P):
        if len(P) > 2:
            return False
        if P == "" or P.isnumeric():
            return True
        else:
            return False

    def upper_int_only(P):
        if len(P) > 3:
            return False
        if P == "" or P.isnumeric():
            return True
        else:
            return False

    for i in range(1, 7):
        poke_label = tk.Label(master=gui, text="ポケモン" + str(i))
        poke_box = ttk.Combobox(master=gui, values=poke_list)
        poke_bool = tk.BooleanVar()
        poke_check = tk.Checkbutton(master=gui, text="選出", variable=poke_bool)
        poke_seikaku = tk.StringVar(value="まじめ")
        vcmd = (gui.register(state_int_only))
        vcmd2 = (gui.register(upper_int_only))

        poke_state_list = []
        for index, state in enumerate(["H", "A", "B", "C", "D", "S"]):
            tk.Label(master=gui, text=state).place(x=320 + index * 45, y=i * 30)
            poke_state_val = tk.IntVar(value=31)
            poke_state_box = tk.Spinbox(master=gui, validate='all', validatecommand=(vcmd, "%P"), width=2, from_=0,
                                        to=31, increment=1, textvariable=poke_state_val)
            poke_state_box.place(x=335 + index * 45, y=i * 30)
            poke_state_list.append(poke_state_val)

        poke_upper_list = []
        for index, upper in enumerate(["H", "A", "B", "C", "D", "S"]):
            tk.Label(master=gui, text=upper).place(x=595 + index * 50, y=i * 30)
            poke_upper_val = tk.IntVar(value=0)
            poke_upper_box = tk.Spinbox(master=gui, validate='all', validatecommand=(vcmd2, "%P"), width=3, from_=0,
                                        to=252, increment=252, textvariable=poke_upper_val)
            poke_upper_box.place(x=610 + index * 50, y=i * 30)
            poke_upper_list.append(poke_upper_val)

        poke_move_list = []
        for index in range(1, 5):
            tk.Label(master=gui, text="技" + str(index)).place(x=800 + index * 150, y=i * 30)
            poke_move_val = tk.StringVar()
            poke_move_box = ttk.Combobox(master=gui, values=list(move_data.keys()), textvariable=poke_move_val,
                                         width=15)
            poke_move_box.place(x=830 + index * 150, y=i * 30)
            poke_move_list.append(poke_move_val)

        tk.Label(master=gui, text="性格").place(x=1550, y=i * 30)
        ttk.Combobox(master=gui, values=list(map(lambda x: x.japanese, list(Character))), textvariable=poke_seikaku,
                     width=10).place(x=1600, y=i * 30)

        poke_label.place(x=30, y=i * 30)
        poke_box.place(x=100, y=i * 30)
        poke_check.place(x=260, y=i * 30)
        poke_selects.append((poke_box, poke_bool, poke_state_list, poke_upper_list, poke_move_list, poke_seikaku))

    poke_save = tk.Button(master=gui, text="Save", foreground="green", command=save_poke, width=10)
    poke_save.place(x=100, y=210)

    poke_save_info_str = tk.StringVar()
    poke_save_info = tk.Entry(master=gui, state="readonly", textvariable=poke_save_info_str, width=8)
    poke_save_info.place(x=190, y=213)

    tk.Label(master=gui, text="認識している文字列(ポケモン)").place(x=250, y=300)
    tk.Entry(master=gui, state="readonly", textvariable=poke_spec_str, width=25).place(x=250, y=330)
    tk.Label(master=gui, text="認識している文字列(相手のポケモン)").place(x=250, y=360)
    tk.Entry(master=gui, state="readonly", textvariable=enemy_poke_spec, width=25).place(x=250, y=390)
    tk.Label(master=gui, text="認識している文字列(技)").place(x=250, y=420)
    tk.Entry(master=gui, state="readonly", textvariable=move_spec_str, width=25).place(x=250, y=450)

    tk.Label(master=gui, text="予測したポケモン").place(x=450, y=300)
    tk.Entry(master=gui, state="readonly", textvariable=poke_spec_suggest, width=25).place(x=450, y=330)
    tk.Label(master=gui, text="予測した相手のポケモン").place(x=450, y=360)
    tk.Entry(master=gui, state="readonly", textvariable=enemy_poke_suggest, width=25).place(x=450, y=390)
    tk.Label(master=gui, text="予測した技").place(x=450, y=420)
    tk.Entry(master=gui, state="readonly", textvariable=move_spec_suggest, width=25).place(x=450, y=450)

    tk.Label(master=gui, text="個体値").place(x=320, y=0)
    tk.Label(master=gui, text="努力値").place(x=595, y=0)

    tk.Label(master=gui, text="ダメージ計算").place(x=648, y=270)
    tk.Label(master=gui, text="努力値無振り").place(x=798, y=270)
    tk.Label(master=gui, text="H252振り").place(x=948, y=270)
    tk.Label(master=gui, text="HBD252振り").place(x=1098, y=270)
    for i in range(-1, 3):
        tk.Entry(master=gui, state="readonly", textvariable=move_list[i], width=20).place(x=650, y=350 + i * 50)
        tk.Entry(master=gui, state="readonly", textvariable=move_damage_list[i], width=20).place(x=800, y=350 + i * 50)
        tk.Entry(master=gui, state="readonly", textvariable=move_h252_damage_list[i], width=20).place(x=950,
                                                                                                      y=350 + i * 50)
        tk.Entry(master=gui, state="readonly", textvariable=move_hbd252_damage_list[i], width=20).place(x=1100,
                                                                                                        y=350 + i * 50)

    gui.mainloop()


ws = obsws("localhost", 4444, "tororo")
ws.connect()


def pil2cv(image):
    new_image = np.array(image, dtype=np.uint8)
    if new_image.ndim == 2:  # モノクロ
        pass
    elif new_image.shape[2] == 3:  # カラー
        new_image = cv2.cvtColor(new_image, cv2.COLOR_RGB2BGR)
    elif new_image.shape[2] == 4:  # 透過
        new_image = cv2.cvtColor(new_image, cv2.COLOR_RGBA2BGRA)
    return new_image


def pil_to_base64(img):
    buffer = io.BytesIO()
    img.save(buffer, "png")
    img_str = base64.b64encode(buffer.getvalue()).decode("ascii")

    return img_str


def string_distance(x, text):
    lev_dist = Levenshtein.distance(x, text)
    # 標準化(長い方の文字列の長さで割る)
    devider = len(x) if len(x) > len(text) else len(text)
    try:
        lev_dist = lev_dist / devider
    except ZeroDivisionError:
        return 0
    # 指標を合わせる(0:完全不一致 → 1:完全一致)
    lev_dist = 1 - lev_dist
    return lev_dist


def frame_to_pokemon(image_frame):
    global pick_poke_list
    gray = cv2.cvtColor(image_frame, cv2.COLOR_BGR2GRAY)
    modify = cv2.threshold(gray[890:935, 100:400], 200, 255, cv2.THRESH_BINARY)[1]

    text = tool.image_to_string(Image.fromarray(modify), lang="jpn",
                                builder=pyocr.builders.TextBuilder(tesseract_layout=7)).replace(" ", "")
    poke_spec_str.set(text)
    poke_spec_suggest.set("")
    if text == "":
        return
    near_data: Dict[float, str] = {}
    for x, value in pick_poke_list.items():
        lev_dist = string_distance(value.name, text)
        if lev_dist > 0.4:
            near_data[lev_dist] = value.name
    if len(near_data) != 0:
        lev = max(near_data)
        x = near_data[lev]
        poke_spec_suggest.set(x)


def frame_to_enemy_pokemon(image_frame):
    gray = cv2.cvtColor(image_frame, cv2.COLOR_BGR2GRAY)
    modify = cv2.threshold(gray[95:145, 1535:1820], 200, 255, cv2.THRESH_BINARY)[1]
    image = Image.fromarray(modify)

    text = tool.image_to_string(image, lang="jpn",
                                builder=pyocr.builders.TextBuilder(tesseract_layout=7))
    eng = tool.image_to_string(image, lang="eng",
                               builder=pyocr.builders.TextBuilder(tesseract_layout=7))
    deu = tool.image_to_string(image, lang="deu",
                               builder=pyocr.builders.TextBuilder(tesseract_layout=7))
    fra = tool.image_to_string(image, lang="fra",
                               builder=pyocr.builders.TextBuilder(tesseract_layout=7))
    kor = tool.image_to_string(image, lang="kor",
                               builder=pyocr.builders.TextBuilder(tesseract_layout=7))
    chi_sim = tool.image_to_string(image, lang="chi_sim",
                                   builder=pyocr.builders.TextBuilder(tesseract_layout=7))
    chi_tra = tool.image_to_string(image, lang="chi_tra",
                                   builder=pyocr.builders.TextBuilder(tesseract_layout=7))
    enemy_poke_spec.set(text)
    enemy_poke_suggest.set("")
    if text == "":
        return
    near_data: Dict[float, str] = {}
    for key, value in pokemon_data.items():
        if "parent" in value:
            continue
        lev_dist = string_distance(value["jpn"], text)
        if lev_dist <= 0.33:
            lev_dist = string_distance(value["eng"], eng)
        if lev_dist <= 0.33:
            lev_dist = string_distance(value["deu"], deu)
        if lev_dist <= 0.33:
            lev_dist = string_distance(value["fra"], fra)
        if lev_dist <= 0.33:
            lev_dist = string_distance(value["kor"], kor)
        if lev_dist <= 0.33:
            lev_dist = string_distance(value["chi-sim"], chi_sim)
        if lev_dist <= 0.33:
            lev_dist = string_distance(value["chi-tra"], chi_tra)
        if lev_dist > 0.33:
            near_data[lev_dist] = key
    if len(near_data) != 0:
        lev = max(near_data)
        x = near_data[lev]
        enemy_poke_suggest.set(x)


def frame_to_move(image_frame):
    global now
    gray = cv2.cvtColor(image_frame, cv2.COLOR_BGR2GRAY)
    modify = cv2.threshold(gray[857:910, 284:1350], 200, 255, cv2.THRESH_BINARY)[1]
    text = tool.image_to_string(Image.fromarray(modify), lang="jpn",
                                builder=pyocr.builders.TextBuilder(tesseract_layout=7))
    text = text.replace("/", "").replace("!", "").replace("攻", "").replace("撃", "").replace(" ", "")
    move_spec_str.set(text)
    move_spec_suggest.set("")
    if text == "":
        return
    print(text)
    near_data: Dict[float, str] = {}
    for x in move_data:
        lev_dist = string_distance(x, text)
        if lev_dist <= 0.4:
            text = text.removesuffix("をした")
            lev_dist = string_distance(x, text)
            if lev_dist <= 0.4:
                text.removesuffix("をつかつた")
                lev_dist = string_distance(x, text)
        if x == "ツインビーム":
            if lev_dist <= 0.55:
                continue
        if x == "ソーラービーム":
            if lev_dist <= 0.50:
                continue
        if lev_dist > 0.4:
            near_data[lev_dist] = x

    if len(near_data) != 0:
        lev = max(near_data)
        x = near_data[lev]
        move_spec_suggest.set(x)
        print("近似値:", x, ":", lev)

        if now:
            return
        now = True
        img = "info"
        img_info = "info_" + x

        info_exists = False
        img_exists = False
        for item in ws.call(requests.GetSceneItemList()).getSceneItems():
            if item["sourceName"] == img:
                img_exists = True
            if item["sourceName"] == img_info:
                info_exists = True
        scene = ws.call(requests.GetCurrentScene()).getName()

        if not img_exists:
            ws.call(requests.CreateSource(img, "image_source", scene,
                                          {'file': os.path.abspath("moves/info.png")},
                                          False))
            ws.call(requests.SetSceneItemPosition(img, 1200, 750))
            ws.call(requests.SetSceneItemTransform(img, 1.2, 1.2, 0))
            ws.call(requests.AddFilterToSource(img, "透明", 'chroma_key_filter_v2', {'opacity': 0.3}))

        if not info_exists:
            if not os.path.isfile("moves/cache/" + img_info + ".png"):
                image = Image.new("RGBA", (600, 240))
                draw = ImageDraw.Draw(image)
                draw.font = ImageFont.truetype("C:/Windows/Fonts/MSGOTHIC.ttc", 35)
                draw.text(xy=(40, 50), text=move_data[x]["name"], fill="white", spacing=6, align="right")
                draw.font = ImageFont.truetype("C:/Windows/Fonts/MSGOTHIC.ttc", 30)
                if move_data[x]["power"] == 0:
                    power = "-"
                else:
                    power = move_data[x]["power"]
                draw.text(xy=(240, 11), text="威力:" + str(power), fill="white", spacing=6, align="right")
                if move_data[x]["hit"] == 999:
                    hit = "-"
                else:
                    hit = move_data[x]["hit"]
                draw.text(xy=(360, 11), text="命中:" + str(hit), fill="white", spacing=6, align="right")
                move_class = move_data[x]["class"]
                if move_class == "Ph":
                    move_jpn = "物理"
                elif move_class == "Sp":
                    move_jpn = "特殊"
                else:
                    move_jpn = "変化"

                draw.text(xy=(490, 11), text=str(move_jpn), fill="white", spacing=6, align="right")
                image.paste(Image.open("types/" + move_data[x]["type"] + ".png").copy().resize((180, 36)), (40, 10))

                for i, lore in enumerate(move_data[x]["lore"]):
                    draw.text(xy=(40, 95 + i * 45), text=str(lore), fill="white", spacing=6, align="right")
                image.save("moves/cache/" + img_info + ".png")
            ws.call(requests.CreateSource(img_info, "image_source", scene,
                                          {'file': os.path.abspath("moves/cache/" + img_info + ".png")},
                                          False))
            ws.call(requests.SetSceneItemPosition(img_info, 1200, 750))
            ws.call(requests.SetSceneItemTransform(img_info, 1.2, 1.2, 0))

        ws.call(requests.SetSceneItemProperties(img, visible=True))
        ws.call(requests.SetSceneItemProperties(img_info, visible=True))

        def remove_icons():
            global now
            time.sleep(2.5)
            ws.call(requests.SetSceneItemProperties(img, visible=False))
            ws.call(requests.SetSceneItemProperties(img_info, visible=False))

            now = False

        thread = threading.Thread(target=remove_icons())
        thread.start()


def damage_calculate():
    global move_list
    global move_damage_list
    global pick_poke_list
    global pokemon_data
    global move_h252_damage_list
    global move_hbd252_damage_list
    if poke_spec_suggest.get() == "" or enemy_poke_suggest.get() == "":
        return
    if poke_spec_suggest.get() not in pick_poke_list:
        return
    if enemy_poke_suggest.get() not in pokemon_data.keys():
        return
    poke = pick_poke_list[poke_spec_suggest.get()]
    poke_data = pokemon_data[poke_spec_suggest.get()]
    enemy_poke = pokemon_data[enemy_poke_suggest.get()]

    for index, poke_move in enumerate(poke.moves):
        if poke_move == "":
            continue
        move = move_data[poke_move]
        move_index = Weakness[move["type"].upper()].index
        multi = Weakness[poke_data["type_1"].upper()].multi[move_index]
        if "type_2" in poke_data:
            multi *= Weakness[poke_data["type_2"].upper()].multi[move_index]
        move_class = move["class"]
        power = move["power"]
        if move_class == "Ph":
            special_attack = floor(((poke_data["A"] * 2 + poke.state["A"] + poke.upper["A"] / 4) * 50 / 100 + 5) *
                                   poke.character.upper[1])
            health = floor((enemy_poke["H"] * 2 + 31 + 0 / 4) * 50 / 100 + 50 + 10)
            h252 = floor((enemy_poke["H"] * 2 + 31 + 252 / 4) * 50 / 100 + 50 + 10)
            defense = floor((enemy_poke["B"] * 2 + 31 + 0 / 4) * 50 / 100 + 5)
            b252 = floor((enemy_poke["B"] * 2 + 31 + 252 / 4) * 50 / 100 + 5)
            damage_min = floor(floor(floor(floor(22 * power * special_attack / defense) / 50 + 2) * multi) * 0.86)
            damage_max = floor(floor(floor(22 * power * special_attack / defense) / 50 + 2) * multi)
            b252_damage_min = floor(floor(floor(floor(22 * power * special_attack / b252) / 50 + 2) * multi) * 0.86)
            b252_damage_max = floor(floor(floor(22 * power * special_attack / b252) / 50 + 2) * multi)
            move_list[index - 1].set(poke_move)
            move_damage_list[index - 1].set(str(floor(damage_min / health * 100 * 10) / 10) + "%~" + str(
                floor(damage_max / health * 100 * 10) / 10) + "%")
            move_h252_damage_list[index - 1].set(str(floor(damage_min / h252 * 100 * 10) / 10) + "%~" + str(
                floor(damage_max / h252 * 100 * 10) / 10) + "%")
            move_hbd252_damage_list[index - 1].set(str(floor(b252_damage_min / h252 * 100 * 10) / 10) + "%~" + str(
                floor(b252_damage_max / h252 * 100 * 10) / 10) + "%")
        elif move_class == "Sp":
            special_attack = floor(((poke_data["C"] * 2 + poke.state["C"] + poke.upper["C"] / 4) * 50 / 100 + 5) *
                                   poke.character.upper[3])
            print("sp_attack" + str(special_attack))
            health = floor((enemy_poke["H"] * 2 + 31 + 0 / 4) * 50 / 100 + 50 + 10)
            print("hp" + str(health))
            h252 = floor((enemy_poke["H"] * 2 + 31 + 252 / 4) * 50 / 100 + 50 + 10)
            sp_defense = floor((enemy_poke["D"] * 2 + 31 + 0 / 4) * 50 / 100 + 5)
            print("sp_d", str(sp_defense))
            d252 = floor((enemy_poke["D"] * 2 + 31 + 252 / 4) * 50 / 100 + 5)
            damage_min = floor(floor(floor(floor(22 * power * special_attack / sp_defense) / 50 + 2) * multi) * 0.86)
            print("damage-min", str(damage_min))
            damage_max = floor(floor(floor(22 * power * special_attack / sp_defense) / 50 + 2) * multi)
            print("damage-max", str(damage_max))
            d252_damage_min = floor(floor(floor(floor(22 * power * special_attack / d252) / 50 + 2) * multi) * 0.86)
            d252_damage_max = floor(floor(floor(22 * power * special_attack / d252) / 50 + 2) * multi)

            move_list[index - 1].set(poke_move)
            move_damage_list[index - 1].set(str(floor(damage_min / health * 100 * 10) / 10) + "%~" + str(
                floor(damage_max / health * 100 * 10) / 10) + "%")
            move_h252_damage_list[index - 1].set(str(floor(damage_min / h252 * 100 * 10) / 10) + "%~" + str(
                floor(damage_max / h252 * 100 * 10) / 10) + "%")
            move_hbd252_damage_list[index - 1].set(str(floor(d252_damage_min / h252 * 100 * 10) / 10) + "%~" + str(
                floor(d252_damage_max / h252 * 100 * 10) / 10) + "%")


def main_task():
    threading.Thread(target=tk_main).start()
    camera = cv2.VideoCapture(1, cv2.CAP_DSHOW)
    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
    camera.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
    camera.set(cv2.CAP_PROP_FPS, 30)
    ret, frame = camera.read()
    if ret is True:
        while camera.read()[0] is True:
            ret, frame = camera.read()
            frame_to_move(frame)
            frame_to_pokemon(frame)
            frame_to_enemy_pokemon(frame)
            damage_calculate()
        camera.release()
        cv2.destroyAllWindows()


if __name__ == '__main__':
    print("てすと")
    main_task()
