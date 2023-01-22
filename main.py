# coding: utf-8
import enum
import json
import os
import sys
import threading
import time
import tkinter as tk
import traceback
from tkinter import filedialog
from tkinter import messagebox
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

pyocr.tesseract.TESSERACT_CMD = os.path.abspath("Tesseract-OCR/tesseract.exe")

tools = pyocr.get_available_tools()
if len(tools) == 0:
    print("No OCR tool found")
    print("Please install Tesseract-OCR.")
    messagebox.showerror("Error", "Can't find Tesseract-OCR. " + os.path.abspath("Tesseract-OCR") + " is not exists?")
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


# 仮置き
class HeldItem(enum.Enum):
    NONE = ("なし", [1.0,1.0,1.0,1.0,1.0,1.0], None,None)

    MUSCLE_BAND = ("ちからのハチマキ", [1.0, 1.1, 1.0, 1.0, 1.0, 1.0], None, None)
    WISE_GLASSES = ("ものしりメガネ", [1.0, 1.0, 1.0, 1.1, 1.0, 1.0], None, None)
    CHOICE_BAND = ("こだわりハチマキ", [1.0, 1.5, 1.0, 1.0, 1.0, 1.0], None, None)
    CHOICE_SCARF = ("こだわりスカーフ", [1.0, 1.0, 1.0, 1.0, 1.0, 1.5], None, None)
    CHOICE_SPECS = ("こだわりメガネ", [1.0, 1.0, 1.0, 1.5, 1.0, 1.0], None, None)
    LIFE_ORB = ("いのちのたま", [1.0, 1.3, 1.0, 1.3, 1.0, 1.0], None, None)

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
    name = ""
    enable = False
    state = {}
    upper = {}
    moves = []
    character = Character.MAJIME
    held_item = HeldItem.NONE


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

terastal_image = cv2.imread(os.path.abspath("compareImages/terastal.png"))

now = False
end = False

test_running = False

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
    global poke_list_list
    global move_list_list
    global move_damage_list_list
    global move_h252_damage_list_list
    global move_hbd252_damage_list_list
    global move_h4_damage_list_list, move_h4_damage_list, move_max_damage_list, move_max_damage_list_list
    global pick_poke_s, enemy_poke_s

    def remove_all_items():
        global end
        for x in ws.call(requests.GetSourcesList()).getSources():
            if str(x["name"]).startswith("info"):
                ws.call(requests.DeleteSceneItem(x["name"]))
        ws.disconnect()
        end = True
        exit(2)

    def save_poke():
        try:
            pick_poke_list.clear()
            for x, y, state_list, upper_list, moves, character, held_item in poke_selects:
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
            for x, y, state_list, upper_list, moves, character, held_item in poke_selects:
                if x.get() == "":
                    continue
                file.write(x.get() + "," + " ".join(map(lambda up_str: str(up_str.get()), state_list)) + "," + " ".join(
                    map(lambda up_str: str(up_str.get()), upper_list)) + "," + " ".join(
                    map(lambda move_str: move_str.get(), moves)) + "," + character.get() + "," + held_item.get() + "\n")
            file.close()
            poke_save_info_str.set("Saved")
            threading.Thread(target=delete_saved).start()
        except (Exception,):
            t, v, tb = sys.exc_info()
            messagebox.showerror("Error", "\n".join(traceback.format_exception(t, v, tb)))

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
        except (Exception,):
            t, v, tb = sys.exc_info()
            messagebox.showerror("Error", "\n".join(traceback.format_exception(t, v, tb)))
        save_poke()

    def other_poke_menu():
        top = tk.Toplevel(master=gui)
        top.geometry("1000x1050")
        top.grab_set()
        top.focus_force()
        top.transient(gui)

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
        top.mainloop()

    gui = tk.Tk()
    gui.title("Pokémon Info")
    gui.geometry("1900x550")
    poke_spec_str = tk.StringVar()
    move_spec_str = tk.StringVar()
    enemy_poke_spec = tk.StringVar()
    poke_spec_suggest = tk.StringVar()
    move_spec_suggest = tk.StringVar()
    enemy_poke_suggest = tk.StringVar()
    pick_poke_s = tk.StringVar()
    for i in range(0, 6):
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

    tk.Button(master=gui, text="Close", foreground='red', command=remove_all_items, width=10).place(x=100, y=300)

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
                     width=10).place(x=1580, y=i * 30)

        tk.Label(master=gui, text="持ち物").place(x=1680, y=i * 30)
        ttk.Combobox(master=gui, values=list(map(lambda x: x.japanese, list(HeldItem))), textvariable=poke_held_item,
                     width=15).place(x=1720, y=i * 30)

        poke_label.place(x=30, y=i * 30)
        poke_box.place(x=100, y=i * 30)
        poke_check.place(x=260, y=i * 30)
        poke_selects.append((poke_box, poke_bool, poke_state_list, poke_upper_list, poke_move_list, poke_seikaku, poke_held_item))

    poke_save = tk.Button(master=gui, text="Save", foreground="green", command=save_poke, width=10)
    poke_save.place(x=100, y=210)

    poke_save_as_file = tk.Button(master=gui, text="Save As File", foreground="blue", command=save_poke_as_file,
                                  width=20)
    poke_save_as_file.place(x=100, y=240)

    poke_load = tk.Button(master=gui, text="Load", foreground="purple", command=load_poke,
                          width=20)
    poke_load.place(x=100, y=270)

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
    tk.Label(master=gui, text="H4振り").place(x=948, y=270)
    tk.Label(master=gui, text="H252振り").place(x=1098, y=270)
    tk.Label(master=gui, text="HBD252振り").place(x=1248, y=270)
    tk.Label(master=gui, text="HBD252振り+性格").place(x=1398, y=270)
    tk.Button(master=gui, text="名前から判断できないキャラ", foreground="green", command=other_poke_menu).place(x=1550, y=300)

    tk.Label(master=gui, text="自分の素早さ実数値").place(x=1550, y=370)
    tk.Entry(master=gui, state="readonly", textvariable=pick_poke_s, width=4).place(x=1665, y=370)
    tk.Label(master=gui, text="相手の素早さ実数値").place(x=1550, y=400)
    for i, s in enumerate(["最遅", "下降", "無振", "準速", "最速", "最速スカーフ"]):
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

    setting_menu = tk.Menu(master=gui, tearoff=0)
    root_menu.add_cascade(label="設定", menu=setting_menu)

    gui.mainloop()


ws = obsws("localhost", 4444, "tororo")
ws.connect()


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
            if "," in value["eng"]:
                for splitEng in value["eng"].split(","):
                    lev_dist = string_distance(splitEng, eng)
                    if lev_dist > 0.33:
                        break
            else:
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
        if x == "ソーラービーム":
            if lev_dist <= 0.50:
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


def set_poke_s():
    global pick_poke_s, enemy_poke_s, poke_spec_suggest, enemy_poke_suggest
    if poke_spec_suggest.get() != "" and poke_spec_suggest.get() in pick_poke_list:
        poke = pick_poke_list[poke_spec_suggest.get()]
        poke_data = pokemon_data[poke_spec_suggest.get()]
        s = floor(
            floor((poke_data["S"] * 2 + poke.state[5] + poke.upper[5] / 4) * 50 / 100 + 5) * poke.character.upper[5])
        pick_poke_s.set(str(int(s)))
    if enemy_poke_suggest.get() != "" and enemy_poke_suggest.get() in pokemon_data:
        poke_data = pokemon_data[enemy_poke_suggest.get()]
        slowest_s = floor(floor((poke_data["S"] * 2 + 0 + 0 / 4) * 50 / 100 + 5) * 0.9)
        slow_s = floor(floor((poke_data["S"] * 2 + 31 + 0 / 4) * 50 / 100 + 5) * 0.9)
        normal_s = floor((poke_data["S"] * 2 + 31 + 0 / 4) * 50 / 100 + 5)
        fast_s = floor((poke_data["S"] * 2 + 31 + 252 / 4) * 50 / 100 + 5)
        fastest_s = floor(floor((poke_data["S"] * 2 + 31 + 252 / 4) * 50 / 100 + 5) * 1.1)
        fastest_scarf_s = floor(floor(floor((poke_data["S"] * 2 + 31 + 252 / 4) * 50 / 100 + 5) * 1.1) * 1.5)
        enemy_poke_s[0].set(str(int(slowest_s)))
        enemy_poke_s[1].set(str(int(slow_s)))
        enemy_poke_s[2].set(str(int(normal_s)))
        enemy_poke_s[3].set(str(int(fast_s)))
        enemy_poke_s[4].set(str(int(fastest_s)))
        enemy_poke_s[5].set(str(int(fastest_scarf_s)))


def damage_calculate():
    def attack_cal(poke, poke_data, enemy_poke, move):
        if move["power"] == 0:
            return ("0.0%~0.0% (0~0)",
                    "0.0%~0.0% (0~0)",
                    "0.0%~0.0% (0~0)",
                    "0.0%~0.0% (0~0)",
                    "0.0%~0.0% (0~0)")
        move_type = Weakness[move["type"].upper()].multi
        multi = move_type[Weakness[enemy_poke["type_1"].upper()].index]
        if "type_2" in enemy_poke:
            multi *= move_type[Weakness[enemy_poke["type_2"].upper()].index]
        if move["type"] == poke_data["type_1"]:
            multi *= 1.5
        elif "type_2" in poke_data:
            if move["type"] == poke_data["type_2"]:
                multi *= 1.5
        if poke.held_item != HeldItem.NONE:
            if poke.held_item.conditionInfo == "type":
                if poke.held_item.condition == move["type"]:
                    multi *= poke.held_item.multi[1]
            else:
                multi *= poke.held_item.multi[1]
        power = move["power"]
        attack = floor(((poke_data["A"] * 2 + poke.state["A"] + poke.upper["A"] / 4) * 50 / 100 + 5) *
                       poke.character.upper[1])
        health = floor((enemy_poke["H"] * 2 + 31 + 0 / 4) * 50 / 100 + 50 + 10)
        h252 = floor((enemy_poke["H"] * 2 + 31 + 252 / 4) * 50 / 100 + 50 + 10)
        h4 = floor((enemy_poke["H"] * 2 + 31 + 4 / 4) * 50 / 100 + 50 + 10)
        defense = floor((enemy_poke["B"] * 2 + 31 + 0 / 4) * 50 / 100 + 5)
        b252 = floor((enemy_poke["B"] * 2 + 31 + 252 / 4) * 50 / 100 + 5)
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

    def sp_attack_cal(poke, poke_data, enemy_poke, move):
        if move["power"] == 0:
            return ("0.0%~0.0% (0~0)",
                    "0.0%~0.0% (0~0)",
                    "0.0%~0.0% (0~0)",
                    "0.0%~0.0% (0~0)",
                    "0.0%~0.0% (0~0)")
        move_type = Weakness[move["type"].upper()].multi
        multi = move_type[Weakness[enemy_poke["type_1"].upper()].index]
        if "type_2" in enemy_poke:
            multi *= move_type[Weakness[enemy_poke["type_2"].upper()].index]
        if move["type"] == poke_data["type_1"]:
            multi *= 1.5
        elif "type_2" in poke_data:
            if move["type"] == poke_data["type_2"]:
                multi *= 1.5
        if poke.held_item != HeldItem.NONE:
            if poke.held_item.conditionInfo == "type":
                if poke.held_item.condition == move["type"]:
                    multi *= poke.held_item.multi[3]
            else:
                multi *= poke.held_item.multi[3]
        power = move["power"]
        special_attack = floor(((poke_data["C"] * 2 + poke.state["C"] + poke.upper["C"] / 4) * 50 / 100 + 5) *
                               poke.character.upper[3])
        health = floor((enemy_poke["H"] * 2 + 31 + 0 / 4) * 50 / 100 + 50 + 10)
        h4 = floor((enemy_poke["H"] * 2 + 31 + 4 / 4) * 50 / 100 + 50 + 10)
        h252 = floor((enemy_poke["H"] * 2 + 31 + 252 / 4) * 50 / 100 + 50 + 10)
        sp_defense = floor((enemy_poke["D"] * 2 + 31 + 0 / 4) * 50 / 100 + 5)
        d252 = floor((enemy_poke["D"] * 2 + 31 + 252 / 4) * 50 / 100 + 5)
        d_max = d252 * 1.1
        damage_min = floor(floor(floor(floor(22 * power * special_attack / sp_defense) / 50 + 2) * multi) * 0.86)
        damage_max = floor(floor(floor(22 * power * special_attack / sp_defense) / 50 + 2) * multi)
        d252_damage_min = floor(floor(floor(floor(22 * power * special_attack / d252) / 50 + 2) * multi) * 0.86)
        d252_damage_max = floor(floor(floor(22 * power * special_attack / d252) / 50 + 2) * multi)
        d_max_damage_min = floor(floor(floor(floor(22 * power * special_attack / d_max) / 50 + 2) * multi) * 0.86)
        d_max_damage_max = floor(floor(floor(22 * power * special_attack / d_max) / 50 + 2) * multi)
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

    global move_list
    global move_damage_list
    global pick_poke_list
    global pokemon_data
    global move_h252_damage_list
    global move_hbd252_damage_list
    global poke_list_list, move_list_list, move_damage_list_list, move_h252_damage_list_list, move_hbd252_damage_list_list
    global move_h4_damage_list_list, move_h4_damage_list, move_max_damage_list, move_max_damage_list_list
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
        move_class = move["class"]
        if enemy_poke["name"] == "List":
            for i, pokemon in enumerate(enemy_poke["list"]):
                ene_poke = pokemon_data[pokemon]
                poke_list_list[i - 1].set(pokemon)
                if move_class == "St":
                    move_list_list[index - 1].set(poke_move)
                if move_class == "Ph":
                    cal = attack_cal(poke, poke_data, ene_poke, move)

                    move_list_list[index - 1].set(poke_move)
                    move_damage_list_list[i - 1][index - 1].set(cal[0])
                    move_h4_damage_list_list[i - 1][index - 1].set(cal[1])
                    move_h252_damage_list_list[i - 1][index - 1].set(cal[2])
                    move_hbd252_damage_list_list[i - 1][index - 1].set(cal[3])
                    move_max_damage_list_list[i - 1][index - 1].set(cal[4])
                elif move_class == "Sp":
                    cal = sp_attack_cal(poke, poke_data, ene_poke, move)

                    move_list_list[index - 1].set(poke_move)
                    move_damage_list_list[i - 1][index - 1].set(cal[0])
                    move_h4_damage_list_list[i - 1][index - 1].set(cal[1])
                    move_h252_damage_list_list[i - 1][index - 1].set(cal[2])
                    move_hbd252_damage_list_list[i - 1][index - 1].set(cal[3])
                    move_max_damage_list_list[i - 1][index - 1].set(cal[4])
            continue
        if move_class == "St":
            move_list[index - 1].set(poke_move)
            continue
        if move_class == "Ph":
            cal = attack_cal(poke, poke_data, enemy_poke, move)

            move_list[index - 1].set(poke_move)
            move_damage_list[index - 1].set(cal[0])
            move_h4_damage_list[index - 1].set(cal[1])
            move_h252_damage_list[index - 1].set(cal[2])
            move_hbd252_damage_list[index - 1].set(cal[3])
            move_max_damage_list[index - 1].set(cal[4])
        elif move_class == "Sp":
            cal = sp_attack_cal(poke, poke_data, enemy_poke, move)

            move_list[index - 1].set(poke_move)
            move_damage_list[index - 1].set(cal[0])
            move_h4_damage_list[index - 1].set(cal[1])
            move_h252_damage_list[index - 1].set(cal[2])
            move_hbd252_damage_list[index - 1].set(cal[3])
            move_max_damage_list[index - 1].set(cal[4])


def test(camera, frame):
    global test_running, terastal_image

    def terastal_type_check():
        time.sleep(1)
        camera.read()[1]

    if test_running:
        return
    dist = np.count_nonzero(frame == terastal_image) / terastal_image.size
    if dist >= 0.55:
        test_running = True
        threading.Thread(target=terastal_type_check).start()


def main_task():
    global end
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
            # test(camera, frame)
            set_poke_s()
            damage_calculate()
        camera.release()
        cv2.destroyAllWindows()


if __name__ == '__main__':
    main_task()
