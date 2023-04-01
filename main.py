# coding: utf-8
import enum
import glob
import json
import os
import sys
import threading
import time
import tkinter as tk
import traceback
import webbrowser
from fractions import Fraction
from tkinter import filedialog
from tkinter import messagebox
from tkinter import ttk
from typing import Dict

import Levenshtein
import cv2
import numpy as np
import pyocr
import pyocr.builders
import yaml
from PIL import Image, ImageFont
from PIL import ImageDraw
from numpy import floor
from obswebsocket import obsws, requests

pyocr.tesseract.TESSERACT_CMD = os.path.abspath("Tesseract-OCR/tesseract.exe")

tools = pyocr.get_available_tools()
if len(tools) == 0:
    print("No OCR tool found")
    print("Please install Tesseract-OCR.")
    messagebox.showerror("Error", "Can't find Tesseract-OCR. " + os.path.abspath("Tesseract-OCR") + " is not exists?")
    sys.exit(1)
tool = tools[0]

text_builder = pyocr.builders.TextBuilder(tesseract_layout=7)

disable_obs = True


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


# 仮置き
class HeldItem(enum.Enum):
    NONE = ("なし", [1.0, 1.0, 1.0, 1.0, 1.0, 1.0], None, None)

    MUSCLE_BAND = ("ちからのハチマキ", [1.0, 1.1, 1.0, 1.0, 1.0, 1.0], None, None)
    WISE_GLASSES = ("ものしりメガネ", [1.0, 1.0, 1.0, 1.1, 1.0, 1.0], None, None)
    CHOICE_BAND = ("こだわりハチマキ", [1.0, 1.5, 1.0, 1.0, 1.0, 1.0], None, None)
    CHOICE_SCARF = ("こだわりスカーフ", [1.0, 1.0, 1.0, 1.0, 1.0, 1.5], None, None)
    CHOICE_SPECS = ("こだわりメガネ", [1.0, 1.0, 1.0, 1.5, 1.0, 1.0], None, None)
    LIFE_ORB = ("いのちのたま", [1.0, 1.3, 1.0, 1.3, 1.0, 1.0], None, None)
    BOOST_ENERGY_ATTACK = ("ブーストエナジー(攻撃)", [1.0, 1.3, 1.0, 1.0, 1.0, 1.0], None, None)
    BOOST_ENERGY_DEFENCE = ("ブーストエナジー(防御)", [1.0, 1.0, 1.3, 1.0, 1.0, 1.0], None, None)
    BOOST_ENERGY_SP_ATTACK = ("ブーストエナジー(特攻)", [1.0, 1.0, 1.0, 1.3, 1.0, 1.0], None, None)
    BOOST_ENERGY_SP_DEFENCE = ("ブーストエナジー(特防)", [1.0, 1.0, 1.0, 1.0, 1.3, 1.0], None, None)
    BOOST_ENERGY_SPEED = ("ブーストエナジー(素早さ)", [1.0, 1.0, 1.0, 1.0, 1.0, 1.5], None, None)

    GROUND_ITEM = ("やわらかいすな", [1.0, 1.2, 1.0, 1.2, 1.0, 1.0], "type", "ground")
    DARK_ITEM = ("くろいメガネ", [1.0, 1.2, 1.0, 1.2, 1.0, 1.0], "type", "dark")
    FIGHTING_ITEM = ("くろおび", [1.0, 1.2, 1.0, 1.2, 1.0, 1.0], "type", "fighting")
    ICE_ITEM = ("とけないこおり", [1.0, 1.2, 1.0, 1.2, 1.0, 1.0], "type", "ice")
    PSYCHIC_ITEM = ("まがったスプーン", [1.0, 1.2, 1.0, 1.2, 1.0, 1.0], "type", "psychic")
    STEEL_ITEM = ("メタルコート", [1.0, 1.2, 1.0, 1.2, 1.0, 1.0], "type", "steel")
    ELECTRIC_ITEM = ("じしゃく", [1.0, 1.2, 1.0, 1.2, 1.0, 1.0], "type", "electric")
    ROCK_ITEM = ("かたいいし", [1.0, 1.2, 1.0, 1.2, 1.0, 1.0], "type", "rock")
    POISON_ITEM = ("どくバリ", [1.0, 1.2, 1.0, 1.2, 1.0, 1.0], "type", "poison")
    GHOST_ITEM = ("のろいのおふだ", [1.0, 1.2, 1.0, 1.2, 1.0, 1.0], "type", "ghost")
    DRAGON_ITEM = ("りゅうのキバ", [1.0, 1.2, 1.0, 1.2, 1.0, 1.0], "type", "dragon")
    GRASS_ITEM = ("きせきのタネ", [1.0, 1.2, 1.0, 1.2, 1.0, 1.0], "type", "grass")
    FIRE_ITEM = ("もくたん", [1.0, 1.2, 1.0, 1.2, 1.0, 1.0], "type", "fire")
    WATER_ITEM = ("しんぴのしずく", [1.0, 1.2, 1.0, 1.2, 1.0, 1.0], "type", "water")
    NORMAL_ITEM = ("シルクのスカーフ", [1.0, 1.2, 1.0, 1.2, 1.0, 1.0], "type", "normal")
    BUG_ITEM = ("ぎんのこな", [1.0, 1.2, 1.0, 1.2, 1.0, 1.0], "type", "bug")

    def __init__(self, japanese, multi: list[float], conditionInfo: str, condition: str):
        self.japanese = japanese
        self.multi = multi
        self.conditionInfo = conditionInfo
        self.condition = condition


class PokeData:

    def __init__(self):
        self.name = ""
        self.enable = False
        self.state = {}
        self.upper = {}
        self.moves = []
        self.character = Character.MAJIME
        self.held_item = HeldItem.NONE
        self.game_upper = [Fraction(1, 1), Fraction(1, 1), Fraction(1, 1), Fraction(1, 1), Fraction(1, 1), Fraction(1, 1)]
        self.terastal = ""
        self.prevent_terastal = ""


with open("moves/moves.json", "r", encoding="utf-8_sig") as f:
    move_data = json.load(f)
with open("pokemon/pokemon.json", "r", encoding="utf-8_sig") as f:
    pokemon_data: dict = json.load(f)
pick_poke_list: dict[str, PokeData] = dict()
enemy_poke_info_list: dict[str, PokeData] = dict()
poke_spec_str: tk.StringVar
poke_spec_suggest: tk.StringVar
move_spec_str: tk.StringVar
move_spec_suggest: tk.StringVar
enemy_poke_spec: tk.StringVar
enemy_poke_suggest: tk.StringVar
move_list: list[tk.StringVar] = list()
move_damage_list: list[tk.StringVar] = list()
move_h4_damage_list: list[tk.StringVar] = list()
move_h252_damage_list: list[tk.StringVar] = list()
move_hbd252_damage_list: list[tk.StringVar] = list()
move_max_damage_list: list[tk.StringVar] = list()

poke_list_list: list[tk.StringVar] = list()
move_list_list: list[tk.StringVar] = list()
move_damage_list_list: list[list[tk.StringVar]] = list()
move_h4_damage_list_list: list[list[tk.StringVar]] = list()
move_h252_damage_list_list: list[list[tk.StringVar]] = list()
move_hbd252_damage_list_list: list[list[tk.StringVar]] = list()
move_max_damage_list_list: list[list[tk.StringVar]] = list()

pick_poke_s: tk.StringVar
enemy_poke_s: list[tk.StringVar] = list()

try:
    os.mkdir(os.path.abspath("party"))
except FileExistsError:
    pass
state_check_image = cv2.imread(os.path.abspath("compareImages/state_check.png"))
check_my_poke_image = cv2.imread(os.path.abspath("compareImages/check_my_poke.png"))
initialize_check_image = cv2.imread(os.path.abspath("compareImages/initialize_check.png"))
terastal_types_image = dict()
for file in glob.glob(os.path.abspath("compareImages/terastal_type/*.png")):
    terastal_types_image[os.path.basename(file).replace(".png", "")] = cv2.imread(file)

now = False
damage_cal_menu_open_now = False
other_poke_menu_open_now = False
debug_menu_open_now = False
end = False

check_one_lang: tk.BooleanVar
one_lang: tk.StringVar

enable_held_item: tk.BooleanVar
enable_prevent_terastal: tk.BooleanVar

test_running = False

now_pokemon: PokeData

terastal_type_suggest: tk.StringVar
enemy_terastal_type_suggest: tk.StringVar
upper_suggest: tk.StringVar
enemy_upper_suggest: tk.StringVar

with open('config/config.yml') as f:
    config_yml = yaml.safe_load(f.read())

ws = obsws(config_yml["obs"]["host"], config_yml["obs"]["port"], config_yml["obs"]["pass"])


def get_width() -> int:
    return config_yml["size"]["width"]


def get_height() -> int:
    return config_yml["size"]["height"]


def int_only(P) -> bool:
    if P == "" or P.isnumeric():
        return True
    else:
        return False


def cv2pil(image):
    new_image = image.copy()
    if new_image.ndim == 2:  # モノクロ
        pass
    elif new_image.shape[2] == 3:  # カラー
        new_image = cv2.cvtColor(new_image, cv2.COLOR_BGR2RGB)
    elif new_image.shape[2] == 4:  # 透過
        new_image = cv2.cvtColor(new_image, cv2.COLOR_BGRA2RGBA)
    new_image = Image.fromarray(new_image)
    return new_image


def tk_main():
    global poke_spec_str
    global move_spec_str
    global poke_spec_suggest
    global move_spec_suggest
    global enemy_poke_spec
    global enemy_poke_suggest
    global move_list
    global move_damage_list
    global poke_list_list
    global move_list_list
    global move_damage_list_list
    global move_h252_damage_list_list
    global move_hbd252_damage_list_list
    global move_h4_damage_list_list, move_h4_damage_list, move_max_damage_list, move_max_damage_list_list
    global pick_poke_s, enemy_poke_s
    global check_one_lang, one_lang, enable_held_item
    global terastal_type_suggest, enemy_terastal_type_suggest, upper_suggest, enemy_upper_suggest, enable_prevent_terastal

    def remove_all_items():
        global end
        if not disable_obs:
            for x in ws.call(requests.GetSourcesList()).getSources():
                if str(x["name"]).startswith("info"):
                    ws.call(requests.DeleteSceneItem(x["name"]))
            ws.disconnect()
        end = True
        sys.exit(0)

    def save_poke():
        try:
            pick_poke_list.clear()
            for x, y, state_list, upper_list, moves, character, held_item, terastal in poke_selects:
                if x.get() == "":
                    continue
                data = PokeData()
                data.name = x.get()
                data.enable = y.get()

                for state_index, single_state in enumerate(["H", "A", "B", "C", "D", "S"]):
                    data.state[single_state] = state_list[state_index].get()
                    data.upper[single_state] = upper_list[state_index].get()
                for move in moves:
                    data.moves.append(move.get())
                data.character = next((f for f in list(Character) if f.japanese == character.get().replace("\n", "")),
                                      Character.MAJIME)
                data.held_item = next((f for f in list(HeldItem) if f.japanese == held_item.get().replace("\n", "")),
                                      HeldItem.NONE)
                data.prevent_terastal = type_japanese_to_english(terastal.get().replace("\n", ""))
                pick_poke_list[x.get()] = data
            poke_save_info_str.set("Saved")

            def delete_saved():
                time.sleep(3)
                poke_save_info_str.set("")

            threading.Thread(target=delete_saved).start()
        except (Exception,):
            t, v, tb = sys.exc_info()
            messagebox.showerror("Error", "\n".join(traceback.format_exception(t, v, tb)))

    def save_poke_as_file():
        def delete_saved():
            time.sleep(3)
            poke_save_info_str.set("")

        try:
            file = filedialog.asksaveasfile(defaultextension="poke", filetypes=[("Poke", "*.poke")],
                                            initialdir=os.path.abspath("party"))
            if file is None:
                poke_save_info_str.set("Cancel")
                threading.Thread(target=delete_saved).start()
                return
            for x, y, state_list, upper_list, moves, character, held_item, terastal in poke_selects:
                if x.get() == "":
                    continue
                file.write(x.get() + "," + " ".join(map(lambda up_str: str(up_str.get()), state_list)) + "," + " ".join(
                    map(lambda up_str: str(up_str.get()), upper_list)) + "," + " ".join(
                    map(lambda move_str: move_str.get(), moves)) + "," + character.get() + "," + held_item.get().replace("\n","") + "," + terastal.get() + "\n")

            file.close()
            poke_save_info_str.set("Saved")
            threading.Thread(target=delete_saved).start()
        except (Exception,):
            t, v, tb = sys.exc_info()
            messagebox.showerror("Error", "\n".join(traceback.format_exception(t, v, tb)))

    def type_japanese_to_english(type):
        if type == "ノーマル":
            return "normal"
        elif type == "ほのお":
            return "fire"
        elif type == "みず":
            return "water"
        elif type == "でんき":
            return "electric"
        elif type == "くさ":
            return "grass"
        elif type == "こおり":
            return "ice"
        elif type == "かくとう":
            return "fighting"
        elif type == "どく":
            return "poison"
        elif type == "じめん":
            return "ground"
        elif type == "ひこう":
            return "flying"
        elif type == "エスパー":
            return "psychic"
        elif type == "むし":
            return "bug"
        elif type == "いわ":
            return "rock"
        elif type == "ゴースト":
            return "ghost"
        elif type == "ドラゴン":
            return "dragon"
        elif type == "あく":
            return "dark"
        elif type == "はがね":
            return "steel"
        elif type == "フェアリー":
            return "fairy"
        else:
            return type

    def load_poke():
        def delete_saved():
            time.sleep(3)
            poke_save_info_str.set("")

        try:
            pick_poke_list.clear()
            file = filedialog.askopenfile(defaultextension="poke", filetypes=[("Poke", "*.poke")],
                                          initialdir=os.path.abspath("party"))
            if file is None:
                poke_save_info_str.set("Cancel")
                threading.Thread(target=delete_saved).start()
                return
            for line_index, line in enumerate(file.readlines()):
                for x_index, x in enumerate(line.split(",")):
                    if x_index == 0:
                        poke_selects[line_index][0].set(x)
                    elif x_index == 1:
                        for state_index, ori_state in enumerate(x.split(" ")):
                            poke_selects[line_index][2][state_index].set(int(ori_state))
                    elif x_index == 2:
                        for upper_index, ori_upper in enumerate(x.split(" ")):
                            poke_selects[line_index][3][upper_index].set(int(ori_upper))
                    elif x_index == 3:
                        for move_index, ori_move in enumerate(x.split(" ")):
                            poke_selects[line_index][4][move_index].set(ori_move)
                    elif x_index == 4:
                        poke_selects[line_index][5].set(x)
                    elif x_index == 5:
                        poke_selects[line_index][6].set(x)
                    elif x_index == 6:
                        poke_selects[line_index][7].set(x)
        except (Exception,):
            t, v, tb = sys.exc_info()
            messagebox.showerror("Error", "\n".join(traceback.format_exception(t, v, tb)))
        save_poke()

    def other_poke_menu():
        global other_poke_menu_open_now
        if other_poke_menu_open_now:
            return
        other_poke_menu_open_now = True

        def on_close():
            global other_poke_menu_open_now
            other_poke_menu_open_now = False
            top.destroy()

        top = tk.Toplevel(master=gui)
        top.geometry("900x1100")
        top.focus_force()

        for i in range(0, 7):
            tk.Entry(master=top, state="readonly", textvariable=poke_list_list[i], width=15).place(x=0, y=50 + 140 * i)
            tk.Label(master=top, text="努力値無振り").place(x=0, y=70 + 140 * i)
            tk.Label(master=top, text="H4振り").place(x=0, y=90 + 140 * i)
            tk.Label(master=top, text="H252振り").place(x=0, y=110 + 140 * i)
            tk.Label(master=top, text="HBD252振り").place(x=0, y=130 + 140 * i)
            tk.Label(master=top, text="HBD252振り+性格").place(x=0, y=150 + 140 * i)
        for i in range(0, 4):
            tk.Entry(master=top, state="readonly", textvariable=move_list_list[i], width=25).place(x=100 + 200 * i,
                                                                                                   y=25)
            for i_2 in range(0, 7):
                tk.Entry(master=top, state="readonly", textvariable=move_damage_list_list[i_2][i], width=25).place(
                    x=100 + 200 * i, y=70 + 140 * i_2)
                tk.Entry(master=top, state="readonly", textvariable=move_h4_damage_list_list[i_2][i], width=25).place(
                    x=100 + 200 * i, y=90 + 140 * i_2)
                tk.Entry(master=top, state="readonly", textvariable=move_h252_damage_list_list[i_2][i], width=25).place(
                    x=100 + 200 * i, y=110 + 140 * i_2)
                tk.Entry(master=top, state="readonly", textvariable=move_hbd252_damage_list_list[i_2][i],
                         width=25).place(x=100 + 200 * i, y=130 + 140 * i_2)
                tk.Entry(master=top, state="readonly", textvariable=move_max_damage_list_list[i_2][i],
                         width=25).place(x=100 + 200 * i, y=150 + 140 * i_2)

        top.protocol("WM_DELETE_WINDOW", on_close)
        top.mainloop()

    def damage_cal_menu():
        global damage_cal_menu_open_now
        if damage_cal_menu_open_now:
            return

        damage_cal_menu_open_now = True

        def on_close():
            global damage_cal_menu_open_now
            damage_cal_menu_open_now = False
            top.destroy()

        top = tk.Toplevel()
        top.title("ダメージ計算")
        top.geometry("820x320")
        top.focus_force()

        tk.Button(master=top, text="名前から判断できないキャラ", foreground="green", command=other_poke_menu).place(x=600,
                                                                                                           y=200)
        tk.Label(master=top, text="相手のポケモン").place(x=0, y=30)
        tk.Entry(master=top, state="readonly", textvariable=enemy_poke_suggest, width=15).place(x=0, y=50)
        tk.Label(master=top, text="努力値無振り").place(x=0, y=70)
        tk.Label(master=top, text="H4振り").place(x=0, y=90)
        tk.Label(master=top, text="H252振り").place(x=0, y=110)
        tk.Label(master=top, text="HBD252振り").place(x=0, y=130)
        tk.Label(master=top, text="HBD252振り+性格").place(x=0, y=150)

        for i in range(0, 4):
            tk.Entry(master=top, state="readonly", textvariable=move_list[i], width=25).place(x=100 + 180 * i,
                                                                                              y=25)
            tk.Entry(master=top, state="readonly", textvariable=move_damage_list[i], width=25).place(
                x=100 + 180 * i, y=70)
            tk.Entry(master=top, state="readonly", textvariable=move_h4_damage_list[i], width=25).place(
                x=100 + 180 * i, y=90)
            tk.Entry(master=top, state="readonly", textvariable=move_h252_damage_list[i], width=25).place(
                x=100 + 180 * i, y=110)
            tk.Entry(master=top, state="readonly", textvariable=move_hbd252_damage_list[i],
                     width=25).place(x=100 + 180 * i, y=130)
            tk.Entry(master=top, state="readonly", textvariable=move_max_damage_list[i],
                     width=25).place(x=100 + 180 * i, y=150)

        tk.Label(master=top, text="自分のポケモン").place(x=0, y=190)
        tk.Entry(master=top, state="readonly", textvariable=poke_spec_suggest, width=15).place(x=80, y=195)
        tk.Label(master=top, text="自分の素早さ実数値").place(x=0, y=250)
        tk.Entry(master=top, state="readonly", textvariable=pick_poke_s, width=4).place(x=75, y=270)
        tk.Label(master=top, text="相手の素早さ実数値").place(x=120, y=230)
        for i, s in enumerate(["最布", "準布", "最速", "準速", "無振", "下降", "最遅"]):
            tk.Label(master=top, text=s).place(x=120 + i * 35, y=250)
            tk.Entry(master=top, state="readonly", textvariable=enemy_poke_s[i], width=4).place(x=120 + i * 35, y=270)
        tk.Label(master=top, text="持ち物を有効にする").place(x=180, y=190)
        tk.Checkbutton(master=top, variable=enable_held_item).place(x=280, y=190)
        tk.Label(master=top, text="仮テラスタル").place(x=320, y=190)
        tk.Checkbutton(master=top, variable=enable_prevent_terastal).place(x=380, y=190)
        top.protocol("WM_DELETE_WINDOW", on_close)
        top.mainloop()

    def setting_menu():
        global config_yml

        def on_close():
            config_yml["size"]["width"] = width.get()
            config_yml["size"]["height"] = height.get()
            config_yml["delay"] = delay.get()
            config_yml["fps"] = fps.get()
            config_yml["cameraIndex"] = cameraIndex.get()

            with open("config/config.yml", "r+") as f:
                yaml.dump_all([config_yml], f, sort_keys=False)

            top.destroy()

        def valid(string: str):
            if string == "":
                return True
            return string.isnumeric()

        def valid_double(string: str):
            if string == "":
                return True
            return string.isdigit()

        top = tk.Toplevel(master=gui)
        top.title("詳細設定")
        top.geometry("600x800")
        top.grab_set()
        top.focus_force()
        top.transient(gui)
        int_only_vcmd = top.register(func=valid)
        width = tk.IntVar(master=top, value=config_yml["size"]["width"])
        height = tk.IntVar(master=top, value=config_yml["size"]["height"])
        delay = tk.DoubleVar(master=top, value=config_yml["delay"])
        fps = tk.IntVar(master=top, value=config_yml["fps"])
        cameraIndex = tk.IntVar(master=top, value=config_yml["cameraIndex"])

        tk.Label(master=top, text="ソフト再起動後に反映").place(x=10, y=10)
        tk.Label(master=top, text="ゲームのウィンドウの大きさ").place(x=10, y=40)
        tk.Entry(master=top, validate="all", validatecommand=(int_only_vcmd, "%P"), textvariable=width, width=5).place(
            x=140,
            y=40)
        tk.Label(master=top, text="x").place(x=166, y=40)
        tk.Entry(master=top, validate="all", validatecommand=(int_only_vcmd, "%P"), textvariable=height, width=5).place(
            x=176,
            y=40)

        tk.Label(master=top, text="画像処理の遅延(秒)").place(x=10, y=65)
        tk.Entry(master=top, validate="all", validatecommand=(int_only_vcmd, "%P"), textvariable=delay, width=5).place(
            x=140,
            y=65)
        tk.Label(master=top, text="fps").place(x=10, y=85)
        tk.Entry(master=top, validate="all", validatecommand=(top.register(func=valid_double), "%P"), textvariable=fps, width=5).place(
            x=140,
            y=85)
        tk.Label(master=top, text="仮想カメラの番号").place(x=10, y=105)
        tk.Entry(master=top, validate="all", validatecommand=(int_only_vcmd, "%P"), textvariable=cameraIndex, width=5).place(
            x=140,
            y=105)

        top.protocol("WM_DELETE_WINDOW", on_close)

        top.mainloop()

    def debug_menu():
        def on_close():
            top.quit()
            top.destroy()

        top = tk.Toplevel(master=gui)
        top.title("デバッグ")
        top.geometry("600x800")
        top.grab_set()
        top.focus_force()
        top.protocol("WM_DELETE_WINDOW", on_close)

        tk.Entry(master=top, state="readonly", textvariable=terastal_type_suggest, width=25).place(x=0, y=0)
        tk.Entry(master=top, state="readonly", textvariable=enemy_terastal_type_suggest, width=25).place(x=0, y=20)
        tk.Entry(master=top, state="readonly", textvariable=upper_suggest, width=25).place(x=0, y=40)
        tk.Entry(master=top, state="readonly", textvariable=enemy_upper_suggest, width=25).place(x=0, y=60)
        top.mainloop()

    gui = tk.Tk()
    gui.title("Pokémon Info")
    gui.geometry("1830x550")
    poke_spec_str = tk.StringVar()
    move_spec_str = tk.StringVar()
    enemy_poke_spec = tk.StringVar()
    poke_spec_suggest = tk.StringVar()
    move_spec_suggest = tk.StringVar()
    enemy_poke_suggest = tk.StringVar()
    pick_poke_s = tk.StringVar()
    check_one_lang = tk.BooleanVar(value=False)
    enable_held_item = tk.BooleanVar(value=True)
    enable_prevent_terastal = tk.BooleanVar(value=False)
    one_lang = tk.StringVar()

    terastal_type_suggest = tk.StringVar()
    enemy_terastal_type_suggest = tk.StringVar()
    upper_suggest = tk.StringVar()
    enemy_upper_suggest = tk.StringVar()
    for i in range(0, 7):
        enemy_poke_s.append(tk.StringVar())
    for i in range(0, 7):
        poke_list_list.append(tk.StringVar())
        move_damage_list_list.append(list())
        move_h4_damage_list_list.append(list())
        move_h252_damage_list_list.append(list())
        move_hbd252_damage_list_list.append(list())
        move_max_damage_list_list.append(list())
        for i_2 in range(0, 4):
            move_damage_list_list[i].append(tk.StringVar())
            move_h4_damage_list_list[i].append(tk.StringVar())
            move_h252_damage_list_list[i].append(tk.StringVar())
            move_hbd252_damage_list_list[i].append(tk.StringVar())
            move_max_damage_list_list[i].append(tk.StringVar())
    for i in range(0, 4):
        move_list.append(tk.StringVar())
        move_damage_list.append(tk.StringVar())
        move_h4_damage_list.append(tk.StringVar())
        move_h252_damage_list.append(tk.StringVar())
        move_hbd252_damage_list.append(tk.StringVar())
        move_max_damage_list.append(tk.StringVar())
        move_list_list.append(tk.StringVar())
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
        poke_held_item = tk.StringVar(value="なし")
        poke_terastal_type = tk.StringVar(value="ノーマル")
        vcmd = (gui.register(state_int_only))
        vcmd2 = (gui.register(upper_int_only))

        poke_state_list = []
        for index, state in enumerate(["H", "A", "B", "C", "D", "S"]):
            tk.Label(master=gui, text=state).place(x=290 + index * 45, y=i * 30)
            poke_state_val = tk.IntVar(value=31)
            poke_state_box = tk.Spinbox(master=gui, validate='all', validatecommand=(vcmd, "%P"), width=2, from_=0,
                                        to=31, increment=1, textvariable=poke_state_val)
            poke_state_box.place(x=305 + index * 45, y=i * 30)
            poke_state_list.append(poke_state_val)

        poke_upper_list = []
        for index, upper in enumerate(["H", "A", "B", "C", "D", "S"]):
            tk.Label(master=gui, text=upper).place(x=565 + index * 50, y=i * 30)
            poke_upper_val = tk.IntVar(value=0)
            poke_upper_box = tk.Spinbox(master=gui, validate='all', validatecommand=(vcmd2, "%P"), width=3, from_=0,
                                        to=252, increment=252, textvariable=poke_upper_val)
            poke_upper_box.place(x=580 + index * 50, y=i * 30)
            poke_upper_list.append(poke_upper_val)

        poke_move_list = []
        for index in range(1, 5):
            poke_move_val = tk.StringVar()
            poke_move_box = ttk.Combobox(master=gui, values=list(move_data.keys()), textvariable=poke_move_val,
                                         width=15)
            poke_move_box.place(x=750 + index * 130, y=i * 30)
            poke_move_list.append(poke_move_val)

        ttk.Combobox(master=gui, values=list(map(lambda x: x.japanese, list(Character))), textvariable=poke_seikaku,
                     width=8).place(x=1400, y=i * 30)

        ttk.Combobox(master=gui, values=list(map(lambda x: x.japanese, list(HeldItem))), textvariable=poke_held_item,
                     width=18).place(x=1485, y=i * 30)

        ttk.Combobox(master=gui, values=["ノーマル", "ほのお", "みず", "でんき", "くさ", "こおり", "かくとう", "どく", "じめん", "ひこう", "エスパー", "むし", "いわ", "ゴースト", "ドラゴン", "あく", "はがね", "フェアリー"], textvariable=poke_terastal_type,
                     width=8).place(x=1630, y=i * 30)

        poke_label.place(x=10, y=i * 30)
        poke_box.place(x=70, y=i * 30)
        poke_check.place(x=230, y=i * 30)
        poke_selects.append(
            (poke_box, poke_bool, poke_state_list, poke_upper_list, poke_move_list, poke_seikaku, poke_held_item,poke_terastal_type))

    poke_save = tk.Button(master=gui, text="Save", foreground="green", command=save_poke, width=10)
    poke_save.place(x=100, y=210)

    poke_save_as_file = tk.Button(master=gui, text="Save As File", foreground="blue", command=save_poke_as_file,
                                  width=20)
    poke_save_as_file.place(x=100, y=240)

    poke_load = tk.Button(master=gui, text="Load", foreground="purple", command=load_poke,
                          width=20)
    poke_load.place(x=100, y=270)

    tk.Button(master=gui, text="Close", foreground='red', command=remove_all_items, width=10).place(x=100, y=300)

    tk.Label(master=gui, text="相手のポケモンを特定の言語だけでチェックする").place(x=10, y=330)
    tk.Checkbutton(master=gui, variable=check_one_lang).place(x=10, y=360)
    tk.Label(master=gui, text="言語").place(x=30, y=360)
    ttk.Combobox(master=gui, values=["日本語", "英語", "ドイツ語", "フランス語", "韓国語", "中国語(簡体字)", "中国語(繁体字)"],
                 textvariable=one_lang, width=10).place(x=70, y=360)

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

    tk.Label(master=gui, text="個体値").place(x=290, y=0)
    tk.Label(master=gui, text="努力値").place(x=565, y=0)
    for i in range(1, 5):
        tk.Label(master=gui, text="技" + str(i)).place(x=750 + i * 130, y=0)
    tk.Label(master=gui, text="性格").place(x=1400, y=0)
    tk.Label(master=gui, text="持ち物").place(x=1485, y=0)
    tk.Label(master=gui, text="テラスタイプ").place(x=1630, y=0)

    tk.Label(master=gui, text="ダメージ計算").place(x=648, y=270)
    tk.Label(master=gui, text="努力値無振り").place(x=798, y=270)
    tk.Label(master=gui, text="H4振り").place(x=948, y=270)
    tk.Label(master=gui, text="H252振り").place(x=1098, y=270)
    tk.Label(master=gui, text="HBD252振り").place(x=1248, y=270)
    tk.Label(master=gui, text="HBD252振り+性格").place(x=1398, y=270)
    tk.Button(master=gui, text="名前から判断できないキャラ", foreground="green", command=other_poke_menu).place(x=1550, y=300)

    tk.Label(master=gui, text="自分の素早さ実数値").place(x=1550, y=370)
    tk.Entry(master=gui, state="readonly", textvariable=pick_poke_s, width=4).place(x=1665, y=370)
    tk.Label(master=gui, text="持ち物を有効にする").place(x=1700, y=370)
    tk.Checkbutton(master=gui, variable=enable_held_item).place(x=1800, y=370)
    tk.Label(master=gui, text="相手の素早さ実数値").place(x=1550, y=400)
    for i, s in enumerate(["最布", "準布", "最速", "準速", "無振", "下降", "最遅"]):
        tk.Label(master=gui, text=s).place(x=1550 + i * 35, y=420)
        tk.Entry(master=gui, state="readonly", textvariable=enemy_poke_s[i], width=4).place(x=1550 + i * 35, y=440)

    for i in range(4):
        tk.Entry(master=gui, state="readonly", textvariable=move_list[i], width=20).place(x=650, y=300 + i * 50)
        tk.Entry(master=gui, state="readonly", textvariable=move_damage_list[i], width=20).place(x=800, y=300 + i * 50)
        tk.Entry(master=gui, state="readonly", textvariable=move_h4_damage_list[i], width=20).place(x=950,
                                                                                                    y=300 + i * 50)
        tk.Entry(master=gui, state="readonly", textvariable=move_h252_damage_list[i], width=20).place(x=1100,
                                                                                                      y=300 + i * 50)
        tk.Entry(master=gui, state="readonly", textvariable=move_hbd252_damage_list[i], width=20).place(x=1250,
                                                                                                        y=300 + i * 50)
        tk.Entry(master=gui, state="readonly", textvariable=move_max_damage_list[i], width=20).place(x=1400,
                                                                                                     y=300 + i * 50)
    root_menu = tk.Menu(master=gui)
    gui.config(menu=root_menu)

    file_bar = tk.Menu(master=gui, tearoff=0)
    setting_bar = tk.Menu(master=gui, tearoff=0)
    view_bar = tk.Menu(master=gui, tearoff=0)
    file_bar.add_command(label="パーティを保存", command=save_poke)
    file_bar.add_command(label="パーティをファイルとして保存", command=save_poke_as_file)
    file_bar.add_command(label="パーティをファイルから読み込む", command=load_poke)
    view_bar.add_command(label="ダメージ計算のウィンドウを個別で表示する", command=damage_cal_menu)
    view_bar.add_command(label="Debug Menu", command=debug_menu)
    setting_bar.add_command(label="詳細設定", command=setting_menu)
    root_menu.add_cascade(label="ファイル", menu=file_bar)
    root_menu.add_cascade(label="表示", menu=view_bar)
    root_menu.add_cascade(label="設定", menu=setting_bar)

    gui.protocol("WM_DELETE_WINDOW", remove_all_items)

    gui.mainloop()


def string_distance(x, text) -> float:
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
    modify = cv2.threshold(
        gray[int(get_height() * 0.824):int(get_height() * 0.866), int(get_width() * 0.052):int(get_width() * 0.208)],
        200, 255, cv2.THRESH_BINARY)[1]

    text = tool.image_to_string(Image.fromarray(modify), lang="jpn",
                                builder=pyocr.builders.TextBuilder(tesseract_layout=7)).replace(" ", "")
    poke_spec_str.set(text)
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
    global text_builder
    gray = cv2.cvtColor(image_frame, cv2.COLOR_BGR2GRAY)
    modify = cv2.threshold(
        gray[int(get_height() * 0.088):int(get_height() * 0.134), int(get_width() * 0.799):int(get_width() * 0.948)],
        200, 255, cv2.THRESH_BINARY)[1]
    image = Image.fromarray(modify)

    if check_one_lang.get():
        lang = one_lang.get()
        if lang == "日本語":
            inc_lang = "jpn"
        elif lang == "英語":
            inc_lang = "eng"
        elif lang == "ドイツ語":
            inc_lang = "deu"
        elif lang == "フランス語":
            inc_lang = "fra"
        elif lang == "韓国語":
            inc_lang = "kor"
        elif lang == "中国語(簡体字)":
            inc_lang = "chi_sim"
        elif lang == "中国語(繁体字)":
            inc_lang = "chi_tra"
        else:
            inc_lang = "jpn"
        text = tool.image_to_string(image, inc_lang, text_builder)
        enemy_poke_spec.set(text)
        if text == "":
            return

        near_data: Dict[float, str] = {}

        for key, value in pokemon_data.items():
            if "parent" in value:
                continue
            lev_dist = 0.00
            if inc_lang == "eng" and "," in value["eng"]:
                if "," in value["eng"]:
                    for splitEng in value["eng"].split(","):
                        lev_dist = string_distance(splitEng, text)
                        if lev_dist > 0.55:
                            break
            else:
                lev_dist = string_distance(value[inc_lang], text)
            if lev_dist > 0.55:
                near_data[lev_dist] = key
        if len(near_data) != 0:
            lev = max(near_data)
            x = near_data[lev]
            enemy_poke_suggest.set(x)
        return

    text = tool.image_to_string(image, lang="jpn",
                                builder=text_builder)
    eng = tool.image_to_string(image, lang="eng",
                               builder=text_builder)
    deu = tool.image_to_string(image, lang="deu",
                               builder=text_builder)
    fra = tool.image_to_string(image, lang="fra",
                               builder=text_builder)
    kor = tool.image_to_string(image, lang="kor",
                               builder=text_builder)
    chi_sim = tool.image_to_string(image, lang="chi_sim",
                                   builder=text_builder)
    chi_tra = tool.image_to_string(image, lang="chi_tra",
                                   builder=text_builder)

    enemy_poke_spec.set(text)
    if text == "":
        return
    near_data: Dict[float, str] = {}

    for key, value in pokemon_data.items():
        if "parent" in value:
            continue
        lev_dist = string_distance(value["jpn"], text)
        if lev_dist <= 0.6:
            if "," in value["eng"]:
                for splitEng in value["eng"].split(","):
                    lev_dist = string_distance(splitEng, eng)
                    if lev_dist > 0.6:
                        break
            else:
                lev_dist = string_distance(value["eng"], eng)
        if lev_dist <= 0.6:
            lev_dist = string_distance(value["deu"], deu)
        if lev_dist <= 0.6:
            lev_dist = string_distance(value["fra"], fra)
        if lev_dist <= 0.6:
            lev_dist = string_distance(value["kor"], kor)
        if lev_dist <= 0.6:
            lev_dist = string_distance(value["chi_sim"], chi_sim)
        if lev_dist <= 0.6:
            lev_dist = string_distance(value["chi_tra"], chi_tra)
        if lev_dist > 0.6:
            near_data[lev_dist] = key
    if len(near_data) != 0:
        lev = max(near_data)
        x = near_data[lev]
        enemy_poke_suggest.set(x)


def frame_to_move(image_frame):
    global now, disable_obs
    if disable_obs:
        return
    gray = cv2.cvtColor(image_frame, cv2.COLOR_BGR2GRAY)
    modify = cv2.threshold(
        gray[int(get_height() * 0.793):int(get_height() * 0.843), int(get_width() * 0.148):int(get_width() * 0.703)],
        200, 255, cv2.THRESH_BINARY)[1]
    text = tool.image_to_string(Image.fromarray(modify), lang="jpn",
                                builder=pyocr.builders.TextBuilder(tesseract_layout=7))
    text = text.replace("/", "").replace("!", "").replace("攻", "").replace("撃", "").replace(" ", "")
    move_spec_str.set(text)
    if text == "":
        return
    near_data: Dict[float, str] = {}
    for x in move_data:
        lev_dist = string_distance(x, text)
        if lev_dist <= 0.4:
            text = text.removesuffix("をした")
            lev_dist = string_distance(x, text)
            if lev_dist <= 0.4:
                text.removesuffix("をつかつた")
                lev_dist = string_distance(x, text)
        if "ー" in x:
            if lev_dist <= 0.5:
                continue
        if x == "ツインビーム":
            if lev_dist <= 0.55:
                continue
        if lev_dist > 0.4:
            near_data[lev_dist] = x

    if len(near_data) != 0:
        lev = max(near_data)
        x = near_data[lev]
        move_spec_suggest.set(x)

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


def attack_cal(poke, poke_data, enemy_poke, move):
    if move["power"] == 0:
        return "無効", "無効", "無効", "無効", "無効"
    move_type = Weakness[move["type"].upper()].multi
    if enemy_poke["name"] in enemy_poke_info_list and enemy_poke_info_list[enemy_poke["name"]].terastal != "":
        data = enemy_poke_info_list[enemy_poke["name"]]
        multi = move_type[Weakness[data.terastal.upper()].index]
    else:
        multi = move_type[Weakness[enemy_poke["type_1"].upper()].index]
        if "type_2" in enemy_poke:
            multi *= move_type[Weakness[enemy_poke["type_2"].upper()].index]

    terastal_check = False

    if poke.terastal == poke_data["type_1"]:
        terastal_check = True
        multi *= 2.0
    elif move["type"] == poke_data["type_1"]:
        multi *= 1.5
    if "type_2" in poke_data:
        if poke.terastal == poke_data["type_2"]:
            terastal_check = True
            multi *= 2.0
        elif move["type"] == poke_data["type_2"]:
            multi *= 1.5
    if poke.terastal == move["type"] and not terastal_check:
        multi *= 1.5

    if poke.held_item != HeldItem.NONE and enable_held_item.get():
        if poke.held_item.conditionInfo == "type":
            if poke.held_item.condition == move["type"]:
                multi *= poke.held_item.multi[1]
        else:
            multi *= poke.held_item.multi[1]
    multi *= poke.game_upper[1]
    frac = Fraction(1, 1)
    if enemy_poke["name"] in enemy_poke_info_list:
        frac = enemy_poke_info_list[enemy_poke["name"]].game_upper[2]
    power = move["power"]
    attack = floor(((poke_data["A"] * 2 + poke.state["A"] + poke.upper["A"] / 4) * 50 / 100 + 5) *
                   poke.character.upper[1])
    health = floor((enemy_poke["H"] * 2 + 31 + 0 / 4) * 50 / 100 + 50 + 10)
    h252 = floor((enemy_poke["H"] * 2 + 31 + 252 / 4) * 50 / 100 + 50 + 10)
    h4 = floor((enemy_poke["H"] * 2 + 31 + 4 / 4) * 50 / 100 + 50 + 10)
    defense = floor(floor((enemy_poke["B"] * 2 + 31 + 0 / 4) * 50 / 100 + 5) * frac)
    b252 = floor(floor((enemy_poke["B"] * 2 + 31 + 252 / 4) * 50 / 100 + 5) * frac)
    b_max = b252 * 1.1
    damage_min = floor(floor(floor(floor(22 * power * attack / defense) / 50 + 2) * multi) * 0.86)
    damage_max = floor(floor(floor(22 * power * attack / defense) / 50 + 2) * multi)
    b252_damage_min = floor(floor(floor(floor(22 * power * attack / b252) / 50 + 2) * multi) * 0.86)
    b252_damage_max = floor(floor(floor(22 * power * attack / b252) / 50 + 2) * multi)
    b_max_damage_min = floor(floor(floor(floor(22 * power * attack / b_max) / 50 + 2) * multi) * 0.86)
    b_max_damage_max = floor(floor(floor(22 * power * attack / b_max) / 50 + 2) * multi)

    if "spam" in move:
        spam = move["spam"]
        minSpam = spam.split("~")[0]
        maxSpam = spam.split("~")[1]
        damage_min = damage_min * int(minSpam)
        damage_max = damage_max * int(maxSpam)

    return (str(floor(damage_min / health * 100 * 10) / 10) + "%~" + str(
        floor(damage_max / health * 100 * 10) / 10) + "% (" + str(int(damage_min)) + "~" + str(
        int(damage_max)) + ")",
            str(floor(damage_min / h4 * 100 * 10) / 10) + "%~" + str(
                floor(damage_max / h4 * 100 * 10) / 10) + "% (" + str(int(damage_min)) + "~" + str(
                int(damage_max)) + ")",
            str(floor(damage_min / h252 * 100 * 10) / 10) + "%~" + str(
                floor(damage_max / h252 * 100 * 10) / 10) + "% (" + str(int(damage_min)) + "~" + str(
                int(damage_max)) + ")",
            str(floor(b252_damage_min / h252 * 100 * 10) / 10) + "%~" + str(
                floor(b252_damage_max / h252 * 100 * 10) / 10) + "% (" + str(int(b252_damage_min)) + "~" + str(
                int(b252_damage_max)) + ")",
            str(floor(b_max_damage_min / h252 * 100 * 10) / 10) + "%~" + str(
                floor(b_max_damage_max / h252 * 100 * 10) / 10) + "% (" + str(int(b_max_damage_min)) + "~" + str(
                int(b_max_damage_max)) + ")"
            )


def sp_attack_cal(poke, poke_data, enemy_poke, move):
    if move["power"] == 0:
        return "無効", "無効", "無効", "無効", "無効"

    move_type = Weakness[move["type"].upper()].multi
    if enemy_poke["name"] in enemy_poke_info_list and enemy_poke_info_list[enemy_poke["name"]].terastal != "":
        data = enemy_poke_info_list[enemy_poke["name"]]
        multi = move_type[Weakness[data.terastal.upper()].index]
    else:
        multi = move_type[Weakness[enemy_poke["type_1"].upper()].index]
        if "type_2" in enemy_poke:
            multi *= move_type[Weakness[enemy_poke["type_2"].upper()].index]

    terastal_check = False

    if poke.terastal == poke_data["type_1"]:
        terastal_check = True
        multi *= 2.0
    elif move["type"] == poke_data["type_1"]:
        multi *= 1.5
    if "type_2" in poke_data:
        if poke.terastal == poke_data["type_2"]:
            terastal_check = True
            multi *= 2.0
        elif move["type"] == poke_data["type_2"]:
            multi *= 1.5
    if poke.terastal == move["type"] and not terastal_check:
        multi *= 1.5

    if poke.held_item != HeldItem.NONE and enable_held_item.get():
        if poke.held_item.conditionInfo == "type":
            if poke.held_item.condition == move["type"]:
                multi *= poke.held_item.multi[3]
        else:
            multi *= poke.held_item.multi[3]
    multi *= poke.game_upper[3]

    frac = Fraction(1, 1)
    if enemy_poke["name"] in enemy_poke_info_list:
        frac = enemy_poke_info_list[enemy_poke["name"]].game_upper[4]
    power = move["power"]
    special_attack = floor(((poke_data["C"] * 2 + poke.state["C"] + poke.upper["C"] / 4) * 50 / 100 + 5) *
                           poke.character.upper[3])
    health = floor((enemy_poke["H"] * 2 + 31 + 0 / 4) * 50 / 100 + 50 + 10)
    h4 = floor((enemy_poke["H"] * 2 + 31 + 4 / 4) * 50 / 100 + 50 + 10)
    h252 = floor((enemy_poke["H"] * 2 + 31 + 252 / 4) * 50 / 100 + 50 + 10)
    sp_defense = floor(floor((enemy_poke["D"] * 2 + 31 + 0 / 4) * 50 / 100 + 5) * frac)
    d252 = floor(floor((enemy_poke["D"] * 2 + 31 + 252 / 4) * 50 / 100 + 5) * frac)
    d_max = d252 * 1.1
    damage_min = floor(floor(floor(floor(22 * power * special_attack / sp_defense) / 50 + 2) * multi) * 0.86)
    damage_max = floor(floor(floor(22 * power * special_attack / sp_defense) / 50 + 2) * multi)
    d252_damage_min = floor(floor(floor(floor(22 * power * special_attack / d252) / 50 + 2) * multi) * 0.86)
    d252_damage_max = floor(floor(floor(22 * power * special_attack / d252) / 50 + 2) * multi)
    d_max_damage_min = floor(floor(floor(floor(22 * power * special_attack / d_max) / 50 + 2) * multi) * 0.86)
    d_max_damage_max = floor(floor(floor(22 * power * special_attack / d_max) / 50 + 2) * multi)

    if "spam" in move:
        spam = move["spam"]
        minSpam = spam.split("~")[0]
        maxSpam = spam.split("~")[1]
        damage_min = damage_min * int(minSpam)
        damage_max = damage_max * int(maxSpam)

    return (str(floor(damage_min / health * 100 * 10) / 10) + "%~" + str(
        floor(damage_max / health * 100 * 10) / 10) + "% (" + str(int(damage_min)) + "~" + str(
        int(damage_max)) + ")",
            str(floor(damage_min / h4 * 100 * 10) / 10) + "%~" + str(
                floor(damage_max / h4 * 100 * 10) / 10) + "% (" + str(int(damage_min)) + "~" + str(
                int(damage_max)) + ")",
            str(floor(damage_min / h252 * 100 * 10) / 10) + "%~" + str(
                floor(damage_max / h252 * 100 * 10) / 10) + "% (" + str(int(damage_min)) + "~" + str(
                int(damage_max)) + ")",
            str(floor(d252_damage_min / h252 * 100 * 10) / 10) + "%~" + str(
                floor(d252_damage_max / h252 * 100 * 10) / 10) + "% (" + str(int(d252_damage_min)) + "~" + str(
                int(d252_damage_max)) + ")",
            str(floor(d_max_damage_min / h252 * 100 * 10) / 10) + "%~" + str(
                floor(d_max_damage_max / h252 * 100 * 10) / 10) + "% (" + str(int(d_max_damage_min)) + "~" + str(
                int(d_max_damage_max)) + ")"
            )


def damage_calculate():
    global move_list
    global move_damage_list
    global pick_poke_list
    global pokemon_data
    global move_h252_damage_list
    global move_hbd252_damage_list
    global poke_list_list, move_list_list, move_damage_list_list, move_h252_damage_list_list, move_hbd252_damage_list_list
    global move_h4_damage_list_list, move_h4_damage_list, move_max_damage_list, move_max_damage_list_list,enable_prevent_terastal
    if poke_spec_suggest.get() == "" or enemy_poke_suggest.get() == "":
        return
    if poke_spec_suggest.get() not in pick_poke_list:
        return
    if enemy_poke_suggest.get() not in pokemon_data.keys():
        return
    poke = pick_poke_list[poke_spec_suggest.get()]
    poke_data = pokemon_data[poke_spec_suggest.get()]
    enemy_poke = pokemon_data[enemy_poke_suggest.get()]

    if enable_prevent_terastal.get():
        poke.terastal = poke.prevent_terastal

    for index, poke_move in enumerate(poke.moves):
        if poke_move == "":
            continue
        move = move_data[poke_move]
        move_class = move["class"]
        if enemy_poke["name"] == "List":
            for i, pokemon in enumerate(enemy_poke["list"]):
                ene_poke = pokemon_data[pokemon]
                poke_list_list[i].set(pokemon)
                ire_cal = irregular_cal(poke, poke_data, ene_poke, move)
                if ire_cal is not None:
                    move_list[index].set(poke_move)
                    move_damage_list[index].set(ire_cal[0])
                    move_h4_damage_list[index].set(ire_cal[1])
                    move_h252_damage_list[index].set(ire_cal[2])
                    move_hbd252_damage_list[index].set(ire_cal[3])
                    move_max_damage_list[index].set(ire_cal[4])
                    continue
                if move_class == "St":
                    zero = ""
                    move_list_list[index].set(poke_move)
                    move_damage_list_list[i][index].set(zero)
                    move_h4_damage_list_list[i][index].set(zero)
                    move_h252_damage_list_list[i][index].set(zero)
                    move_hbd252_damage_list_list[i][index].set(zero)
                    move_max_damage_list_list[i][index].set(zero)
                if move_class == "Ph":
                    cal = attack_cal(poke, poke_data, ene_poke, move)

                    move_list_list[index].set(poke_move)
                    move_damage_list_list[i][index].set(cal[0])
                    move_h4_damage_list_list[i][index].set(cal[1])
                    move_h252_damage_list_list[i][index].set(cal[2])
                    move_hbd252_damage_list_list[i][index].set(cal[3])
                    move_max_damage_list_list[i][index].set(cal[4])
                elif move_class == "Sp":
                    cal = sp_attack_cal(poke, poke_data, ene_poke, move)

                    move_list_list[index].set(poke_move)
                    move_damage_list_list[i][index].set(cal[0])
                    move_h4_damage_list_list[i][index].set(cal[1])
                    move_h252_damage_list_list[i][index].set(cal[2])
                    move_hbd252_damage_list_list[i][index].set(cal[3])
                    move_max_damage_list_list[i][index].set(cal[4])
            continue

        ire_cal = irregular_cal(poke, poke_data, enemy_poke, move)
        if ire_cal is not None:
            move_list[index].set(poke_move)
            move_damage_list[index].set(ire_cal[0])
            move_h4_damage_list[index].set(ire_cal[1])
            move_h252_damage_list[index].set(ire_cal[2])
            move_hbd252_damage_list[index].set(ire_cal[3])
            move_max_damage_list[index].set(ire_cal[4])
            continue

        if move_class == "St":
            zero = ""
            move_list[index].set(poke_move)
            move_damage_list[index].set(zero)
            move_h4_damage_list[index].set(zero)
            move_h252_damage_list[index].set(zero)
            move_hbd252_damage_list[index].set(zero)
            move_max_damage_list[index].set(zero)
            continue
        if move_class == "Ph":
            cal = attack_cal(poke, poke_data, enemy_poke, move)

            move_list[index].set(poke_move)
            move_damage_list[index].set(cal[0])
            move_h4_damage_list[index].set(cal[1])
            move_h252_damage_list[index].set(cal[2])
            move_hbd252_damage_list[index].set(cal[3])
            move_max_damage_list[index].set(cal[4])
        elif move_class == "Sp":
            cal = sp_attack_cal(poke, poke_data, enemy_poke, move)
            move_list[index].set(poke_move)
            move_damage_list[index].set(cal[0])
            move_h4_damage_list[index].set(cal[1])
            move_h252_damage_list[index].set(cal[2])
            move_hbd252_damage_list[index].set(cal[3])
            move_max_damage_list[index].set(cal[4])


def irregular_cal(poke, poke_data, enemy_poke, move):
    if move["name"] == "テラバースト":
        if poke.terastal != "":
            move["type"] = poke.terastal
            if check_a_c_state(poke, poke_data) == "Ph":
                cal = attack_cal(poke, poke_data, enemy_poke, move)
            else:
                cal = sp_attack_cal(poke, poke_data, enemy_poke, move)
        else:
            move["type"] = "normal"
            cal = sp_attack_cal(poke, poke_data, enemy_poke, move)

        return cal

    def grass_knock_or_kick():
        weight = enemy_poke["weight"]
        if weight < 10:
            return 20
        elif weight < 25:
            return 40
        elif weight < 50:
            return 60
        elif weight < 100:
            return 80
        elif weight < 200:
            return 100
        else:
            return 120

    if move["name"] == "くさむすび":
        power = grass_knock_or_kick()
        move["power"] = power
        return sp_attack_cal(poke, poke_data, enemy_poke, move)
    if move["name"] == "けたぐり":
        power = grass_knock_or_kick()
        move["power"] = power
        return attack_cal(poke, poke_data, enemy_poke, move)

    def stamp():
        self_weight = poke_data["weight"]
        enemy_weight = enemy_poke["weight"]
        diff = Fraction(enemy_weight, self_weight)
        if diff <= Fraction(1, 5):
            return 120
        elif diff <= Fraction(1, 4):
            return 100
        elif diff <= Fraction(1, 3):
            return 80
        elif diff <= Fraction(1, 2):
            return 60
        else:
            return 40

    if move["name"] == "ヒートスタンプ" or move["name"] == "ヘビーボンバー":
        power = stamp()
        move["power"] = power
        return attack_cal(poke, poke_data, enemy_poke, move)

    def body_press():
        move_type = Weakness[move["type"].upper()].multi
        if enemy_poke["name"] in enemy_poke_info_list and enemy_poke_info_list[enemy_poke["name"]].terastal != "":
            data = enemy_poke_info_list[enemy_poke.name]
            multi = move_type[Weakness[data.terastal.upper()].index]
        else:
            multi = move_type[Weakness[enemy_poke["type_1"].upper()].index]
            if "type_2" in enemy_poke:
                multi *= move_type[Weakness[enemy_poke["type_2"].upper()].index]

        terastal_check = False

        if move["type"] == poke_data["type_1"]:
            if poke.terastal == poke_data["type_1"]:
                terastal_check = True
                multi *= 2.0
            else:
                multi *= 1.5
        elif "type_2" in poke_data:
            if move["type"] == poke_data["type_2"]:
                if poke.terastal == poke_data["type_2"]:
                    terastal_check = True
                    multi *= 2.0
                else:
                    multi *= 1.5
        if poke.terastal == move["type"] and not terastal_check:
            multi *= 1.5

        if poke.held_item != HeldItem.NONE and enable_held_item.get():
            if poke.held_item.conditionInfo == "type":
                if poke.held_item.condition == move["type"]:
                    multi *= poke.held_item.multi[2]
            else:
                multi *= poke.held_item.multi[2]
        multi *= poke.game_upper[2]
        frac = Fraction(1, 1)
        if enemy_poke["name"] in enemy_poke_info_list:
            frac = enemy_poke_info_list[enemy_poke["name"]].game_upper[2]
        power = move["power"]
        attack = floor(((poke_data["B"] * 2 + poke.state["B"] + poke.upper["B"] / 4) * 50 / 100 + 5) *
                       poke.character.upper[2])
        health = floor((enemy_poke["H"] * 2 + 31 + 0 / 4) * 50 / 100 + 50 + 10)
        h252 = floor((enemy_poke["H"] * 2 + 31 + 252 / 4) * 50 / 100 + 50 + 10)
        h4 = floor((enemy_poke["H"] * 2 + 31 + 4 / 4) * 50 / 100 + 50 + 10)
        defense = floor(floor((enemy_poke["B"] * 2 + 31 + 0 / 4) * 50 / 100 + 5) * frac)
        b252 = floor(floor((enemy_poke["B"] * 2 + 31 + 252 / 4) * 50 / 100 + 5) * frac)
        b_max = b252 * 1.1
        damage_min = floor(floor(floor(floor(22 * power * attack / defense) / 50 + 2) * multi) * 0.86)
        damage_max = floor(floor(floor(22 * power * attack / defense) / 50 + 2) * multi)
        b252_damage_min = floor(floor(floor(floor(22 * power * attack / b252) / 50 + 2) * multi) * 0.86)
        b252_damage_max = floor(floor(floor(22 * power * attack / b252) / 50 + 2) * multi)
        b_max_damage_min = floor(floor(floor(floor(22 * power * attack / b_max) / 50 + 2) * multi) * 0.86)
        b_max_damage_max = floor(floor(floor(22 * power * attack / b_max) / 50 + 2) * multi)
        return (str(floor(damage_min / health * 100 * 10) / 10) + "%~" + str(
            floor(damage_max / health * 100 * 10) / 10) + "% (" + str(int(damage_min)) + "~" + str(
            int(damage_max)) + ")",
                str(floor(damage_min / h4 * 100 * 10) / 10) + "%~" + str(
                    floor(damage_max / h4 * 100 * 10) / 10) + "% (" + str(int(damage_min)) + "~" + str(
                    int(damage_max)) + ")",
                str(floor(damage_min / h252 * 100 * 10) / 10) + "%~" + str(
                    floor(damage_max / h252 * 100 * 10) / 10) + "% (" + str(int(damage_min)) + "~" + str(
                    int(damage_max)) + ")",
                str(floor(b252_damage_min / h252 * 100 * 10) / 10) + "%~" + str(
                    floor(b252_damage_max / h252 * 100 * 10) / 10) + "% (" + str(int(b252_damage_min)) + "~" + str(
                    int(b252_damage_max)) + ")",
                str(floor(b_max_damage_min / h252 * 100 * 10) / 10) + "%~" + str(
                    floor(b_max_damage_max / h252 * 100 * 10) / 10) + "% (" + str(int(b_max_damage_min)) + "~" + str(
                    int(b_max_damage_max)) + ")"
                )

    if move["name"] == "ボディプレス":
        return body_press()

    return None


def check_a_c_state(poke, poke_data):
    attack = floor(floor(((poke_data["A"] * 2 + poke.state["A"] + poke.upper["A"] / 4) * 50 / 100 + 5) *
                         poke.character.upper[1]) * poke.game_upper[1])

    special_attack = floor(floor(((poke_data["C"] * 2 + poke.state["C"] + poke.upper["C"] / 4) * 50 / 100 + 5) *
                                 poke.character.upper[3]) * poke.game_upper[3])

    if attack > special_attack:
        return "Ph"
    else:
        return "Sp"


def set_poke_s():
    global pick_poke_s, enemy_poke_s, poke_spec_suggest, enemy_poke_suggest
    if poke_spec_suggest.get() != "" and poke_spec_suggest.get() in pick_poke_list:
        poke = pick_poke_list[poke_spec_suggest.get()]
        poke_data = pokemon_data[poke_spec_suggest.get()]
        s = floor(floor(
            floor((poke_data["S"] * 2 + poke.state["S"] + poke.upper["S"] / 4) * 50 / 100 + 5) * poke.character.upper[
                5]) * poke.game_upper[5])

        if enable_held_item.get():
            s = floor(s * poke.held_item.multi[5])
        pick_poke_s.set(str(int(s)))
    if enemy_poke_suggest.get() != "" and enemy_poke_suggest.get() in pokemon_data:
        poke_data = pokemon_data[enemy_poke_suggest.get()]
        if poke_data["name"] == "List":
            return
        frac = Fraction(1, 1)
        if poke_data["name"] in enemy_poke_info_list.keys():
            frac = enemy_poke_info_list[poke_data["name"]].game_upper[5]
        slowest_s = floor(floor(floor((poke_data["S"] * 2 + 0 + 0 / 4) * 50 / 100 + 5) * 0.9) * frac)
        slow_s = floor(floor(floor((poke_data["S"] * 2 + 31 + 0 / 4) * 50 / 100 + 5) * 0.9) * frac)
        normal_s = floor(floor((poke_data["S"] * 2 + 31 + 0 / 4) * 50 / 100 + 5) * frac)
        fast_s = floor(floor((poke_data["S"] * 2 + 31 + 252 / 4) * 50 / 100 + 5) * frac)
        fastest_s = floor(floor(floor((poke_data["S"] * 2 + 31 + 252 / 4) * 50 / 100 + 5) * 1.1) * frac)
        fast_scarf_s = floor(floor(floor((poke_data["S"] * 2 + 31 + 252 / 4) * 50 / 100 + 5) * 1.5) * frac)
        fastest_scarf_s = floor(
            floor(floor(floor((poke_data["S"] * 2 + 31 + 252 / 4) * 50 / 100 + 5) * 1.1) * 1.5) * frac)
        enemy_poke_s[6].set(str(int(slowest_s)))
        enemy_poke_s[5].set(str(int(slow_s)))
        enemy_poke_s[4].set(str(int(normal_s)))
        enemy_poke_s[3].set(str(int(fast_s)))
        enemy_poke_s[2].set(str(int(fastest_s)))
        enemy_poke_s[1].set(str(int(fast_scarf_s)))
        enemy_poke_s[0].set(str(int(fastest_scarf_s)))


def is_rgb_near(rgb1, rgb2, rgb_range=20):
    r1, g1, b1 = rgb1
    r2, g2, b2 = rgb2
    if abs(r1 - r2) < rgb_range and abs(g1 - g2) < rgb_range and abs(b1 - b2) < rgb_range:
        return True
    else:
        return False


def state_check(frame):
    global text_builder
    _, max_val, _, _ = cv2.minMaxLoc(cv2.matchTemplate(frame, state_check_image, cv2.TM_CCOEFF_NORMED))
    if max_val > 0.98:

        terastal_types = {}

        for type_name, image in terastal_types_image.items():
            _, max_val, _, _ = cv2.minMaxLoc(cv2.matchTemplate(frame[int(get_height() * 0.2):int(get_height() * 0.2602), int(get_width() * 0.084):int(get_width() * 0.118)], image, cv2.TM_CCOEFF_NORMED))
            if max_val > 0.82:
                terastal_types[max_val] = type_name

        terastal_type = ""

        if len(terastal_types) != 0:
            terastal_type = terastal_types[max(terastal_types.keys())]

        color = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        # 40x 60x
        up_states = [0, 0, 0, 0, 0]
        for i in range(0, 5):
            y_loc = int(get_height() * 0.5509) + i * int(get_height() * 0.0555)
            for i_2 in range(0, 6):
                x_loc = int(get_width() * 0.2604) + i_2 * int(get_width() * 0.0208)
                if is_rgb_near(color[y_loc][x_loc], (100, 220, 0)):
                    up_states[i] += 1
                if is_rgb_near(color[y_loc][x_loc], (230, 50, 55)):
                    up_states[i] -= 1

        up_fractions = [Fraction(1, 1)]
        for i in up_states:
            if i > 0:
                up_fractions.append(Fraction(i + 2, 2))
            elif i < 0:
                up_fractions.append(Fraction(2, abs(i) + 2))
            else:
                up_fractions.append(Fraction(1, 1))

        _, my_poke_max_val, _, _ = cv2.minMaxLoc(cv2.matchTemplate(frame, check_my_poke_image, cv2.TM_CCOEFF_NORMED))
        poke = frame[int(get_height() * 0.0815):int(get_height() * 0.1157), int(get_width() * 0.0860):int(get_width() * 0.2135)]  # 88:165, 120:410
        poke = cv2.cvtColor(poke, cv2.COLOR_BGR2GRAY)
        poke = cv2.threshold(poke, 200, 255, cv2.THRESH_BINARY)[1]
        if my_poke_max_val > 0.8:
            pokemon = tool.image_to_string(cv2pil(poke), lang="jpn", builder=text_builder)
            for key, value in pick_poke_list.items():
                lev_dist = string_distance(pokemon, key)
                if lev_dist > 0.55:
                    data = pick_poke_list[key]
                    if terastal_type != "":
                        enable_prevent_terastal.set(False)
                        data.terastal = terastal_type
                    data.game_upper = up_fractions
                    upper_suggest.set(str(up_fractions))
                    terastal_type_suggest.set(terastal_type)
                    break

        else:
            image = cv2pil(poke)

            if check_one_lang.get():
                lang = one_lang.get()
                if lang == "日本語":
                    inc_lang = "jpn"
                elif lang == "英語":
                    inc_lang = "eng"
                elif lang == "ドイツ語":
                    inc_lang = "deu"
                elif lang == "フランス語":
                    inc_lang = "fra"
                elif lang == "韓国語":
                    inc_lang = "kor"
                elif lang == "中国語(簡体字)":
                    inc_lang = "chi_sim"
                elif lang == "中国語(繁体字)":
                    inc_lang = "chi_tra"
                else:
                    inc_lang = "jpn"
                text = tool.image_to_string(image, inc_lang, text_builder)
                if text == "":
                    return

                near_data: Dict[float, str] = {}

                for key, value in pokemon_data.items():
                    if "parent" in value:
                        continue
                    lev_dist = 0.00
                    if inc_lang == "eng" and "," in value["eng"]:
                        if "," in value["eng"]:
                            for splitEng in value["eng"].split(","):
                                lev_dist = string_distance(splitEng, text)
                                if lev_dist > 0.6:
                                    break
                    else:
                        lev_dist = string_distance(value[inc_lang], text)
                    if lev_dist > 0.6:
                        near_data[lev_dist] = key
                if len(near_data) != 0:
                    lev = max(near_data)
                    x = near_data[lev]
                    data = PokeData()
                    data.game_upper = up_fractions
                    if terastal_type != "":
                        data.terastal = terastal_type
                    enemy_poke_info_list[x] = data
                    enemy_upper_suggest.set(str(up_fractions))
                    enemy_terastal_type_suggest.set(terastal_type)
                return

            text = tool.image_to_string(image, lang="jpn",
                                        builder=text_builder)
            eng = tool.image_to_string(image, lang="eng",
                                       builder=text_builder)
            deu = tool.image_to_string(image, lang="deu",
                                       builder=text_builder)
            fra = tool.image_to_string(image, lang="fra",
                                       builder=text_builder)
            kor = tool.image_to_string(image, lang="kor",
                                       builder=text_builder)
            chi_sim = tool.image_to_string(image, lang="chi_sim",
                                           builder=text_builder)
            chi_tra = tool.image_to_string(image, lang="chi_tra",
                                           builder=text_builder)

            enemy_poke_spec.set(text)
            if text == "":
                return
            near_data: Dict[float, str] = {}

            for key, value in pokemon_data.items():
                if "parent" in value:
                    continue
                lev_dist = string_distance(value["jpn"], text)
                if lev_dist <= 0.6:
                    if "," in value["eng"]:
                        for splitEng in value["eng"].split(","):
                            lev_dist = string_distance(splitEng, eng)
                            if lev_dist > 0.6:
                                break
                    else:
                        lev_dist = string_distance(value["eng"], eng)
                if lev_dist <= 0.6:
                    lev_dist = string_distance(value["deu"], deu)
                if lev_dist <= 0.6:
                    lev_dist = string_distance(value["fra"], fra)
                if lev_dist <= 0.6:
                    lev_dist = string_distance(value["kor"], kor)
                if lev_dist <= 0.6:
                    lev_dist = string_distance(value["chi_sim"], chi_sim)
                if lev_dist <= 0.6:
                    lev_dist = string_distance(value["chi_tra"], chi_tra)
                if lev_dist > 0.6:
                    near_data[lev_dist] = key
            if len(near_data) != 0:
                lev = max(near_data)
                x = near_data[lev]
                data = PokeData()
                data.game_upper = up_fractions
                if terastal_type != "":
                    data.terastal = terastal_type
                enemy_poke_info_list[x] = data
                enemy_upper_suggest.set(str(up_fractions))
                enemy_terastal_type_suggest.set(terastal_type)

def initialize_check(frame):
    global enable_prevent_terastal
    _, max_val, _, _ = cv2.minMaxLoc(cv2.matchTemplate(frame, initialize_check_image, cv2.TM_CCOEFF_NORMED))
    if max_val > 0.9:
        enable_prevent_terastal.set(False)
        for poke in pick_poke_list.values():
            poke.terastal = ""
        enemy_poke_info_list.clear()


def main_task():
    global end, ws
    try:
        if not disable_obs:
            ws.connect()
    except (Exception,):
        def on_close():
            config_yml["obs"]["host"] = host.get()
            config_yml["obs"]["port"] = int(port.get())
            config_yml["obs"]["pass"] = password.get()
            with open("config/config.yml", "r+") as f:
                yaml.dump_all([config_yml], f, sort_keys=False)
            setting.destroy()
            sys.exit(0)

        messagebox.showinfo("設定エラー",
                            "obsに接続できませんでした\nWebSocketの指定をしてください(obsが起動されてないと接続できません)\n(このウィンドウを閉じると移動します)")
        setting = tk.Tk()
        vcmd = setting.register(int_only)
        setting.title("WebSocketの指定をする")
        setting.geometry("300x120")
        setting.focus_force()
        tk.Label(master=setting, text="ホスト").place(x=0, y=20)
        host = tk.Entry(master=setting, textvariable=tk.StringVar(value=config_yml["obs"]["host"]))
        host.place(x=100, y=20)
        tk.Label(master=setting, text="ポート").place(x=0, y=40)
        port = tk.Entry(master=setting, textvariable=tk.IntVar(value=config_yml["obs"]["port"]),
                        validatecommand=(vcmd, "%P"), validate='all')
        port.place(x=100, y=40)
        tk.Label(master=setting, text="パスワード").place(x=0, y=60)
        password = tk.Entry(master=setting, textvariable=tk.StringVar(value=config_yml["obs"]["pass"]))
        password.place(x=100, y=60)
        tk.Label(master=setting, text="ウィンドウを閉じると設定します").place(x=0, y=80)
        url = tk.Label(master=setting, text="詳しくはこちらから", foreground="blue")
        url.bind("<Button-1>", lambda e: webbrowser.open_new("https://google.com"))
        url.place(x=0, y=100)
        setting.protocol("WM_DELETE_WINDOW", on_close)
        setting.mainloop()
    camera = cv2.VideoCapture(config_yml["cameraIndex"], cv2.CAP_DSHOW)
    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, get_height())
    camera.set(cv2.CAP_PROP_FRAME_WIDTH, get_width())
    camera.set(cv2.CAP_PROP_FPS, config_yml["fps"])
    ret, frame = camera.read()
    if ret is True:
        threading.Thread(target=tk_main, daemon=True).start()
        while camera.read()[0] and not end:
            ret, frame = camera.read()
            try:
                frame_to_move(frame)
                frame_to_pokemon(frame)
                frame_to_enemy_pokemon(frame)
                threading.Thread(target=state_check, args=(frame,)).start()
                threading.Thread(target=set_poke_s).start()
                threading.Thread(target=initialize_check, args=(frame,)).start()
                damage_calculate()
                time.sleep(config_yml["delay"])

            except RuntimeError:
                break
        camera.release()
        cv2.destroyAllWindows()
        sys.exit(0)
    else:
        def on_close():
            config_yml["cameraIndex"] = int(spinbox.get())
            with open("config/config.yml", "r+") as f:
                yaml.dump_all([config_yml], f, sort_keys=False)
            setting.destroy()
            sys.exit(0)

        messagebox.showinfo("設定エラー", "カメラが読み込めませんでした\nカメラのidを指定してください\n(このウィンドウを閉じると移動します)")
        setting = tk.Tk()
        vcmd = setting.register(int_only)
        setting.title("カメラidを設定する(0から)")
        setting.geometry("300x80")
        setting.focus_force()
        spinbox = tk.Spinbox(master=setting, increment=1, textvariable=tk.IntVar(value=config_yml["cameraIndex"]),
                             from_=0, to=999, validatecommand=(vcmd, "%P"), validate='all')
        spinbox.place(x=0, y=20)
        tk.Label(master=setting, text="ウィンドウを閉じると設定します").place(x=0, y=40)
        url = tk.Label(master=setting, text="詳しくはこちらから", foreground="blue")
        url.bind("<Button-1>", lambda e: webbrowser.open_new("https://google.com"))
        url.place(x=0, y=60)
        setting.protocol("WM_DELETE_WINDOW", on_close)
        setting.mainloop()


if __name__ == '__main__':
    main_task()
