import os
import sqlite3 as sq

import tkinter
from PIL import Image, ImageTk
from colorthief import ColorThief
from webcolors import css3_hex_to_names, hex_to_rgb

from scipy.spatial import KDTree
from matplotlib import pyplot as plt

import re
from nltk.stem import SnowballStemmer
from googletrans import Translator


class SearchMode:
    """
    Режим поиска изображений по запросу
    """
    def __init__(self):
        # Создание окна
        self.root = tkinter.Tk()
        self.root.geometry('1040x900')
        self.root.title("Search images")

        # Создание рабочего пространства
        self.frame = tkinter.Frame(self.root)
        self.frame.grid()

        # Список для ссылок на изображения
        self.list_links_images = []
        
        # Размер выводимых изображений
        self.w = 256
        self.h = 256
        self.size = (self.w, self.h)

        # Ограничение по кол-ву изображений в строке
        self.col_limit = 4

        # Текстовое поле
        self.txt_search = tkinter.Entry(self.root, width=40)
        self.txt_search.grid(row=0, column=1, padx=10)

        # Кнопка поиска
        self.but_search = tkinter.Button(self.frame, text="Поиск",
                                         command=lambda: self.search(self.txt_search.get()))
        self.but_search.grid(row=0, column=2, padx=10, pady=10, sticky="nw")

        # Бинд кнопки поиска на "Enter"
        self.root.bind('<Return>', lambda event=None: self.but_search.invoke())

        # Кнопка перевода текста
        self.but_translate = tkinter.Button(self.frame, text="ru -> en",
                                            command=lambda: self.search(self.translate(self.txt_search.get())))
        self.but_translate.grid(row=0, column=0, columnspan=2, padx=75, pady=10, sticky="nw")

        # Бинд кнопки перевода текста на "Shift + Enter"
        self.root.bind('<Shift-Return>', lambda event=None: self.but_translate.invoke())

        # Обработка событий
        self.root.mainloop()

    def search(self, txt):
        """
        Поиск и отрисовка картинок из БД по запросу
        :param txt: текстовый запрос
        :return: True
        """
        images = self.search_images_by_id(str(txt))
        length_images = len(images)

        if length_images > 0:
            row_span = 0

            # Очистка списка
            self.list_links_images *= 0

            for i in range(0, length_images):
                # Изменение размера изображения,
                # добавление сслыки на изображение в список
                with Image.open(images[i]) as img:
                    img = img.resize(self.size)
                    img_tk = ImageTk.PhotoImage(img)
                    self.list_links_images.append(img_tk)

                # Ограничение по кол-ву выводимых столбцов
                if i % self.col_limit == 0:
                    row_span += 1
                col_span = i % self.col_limit

                # Отрисовка изображения в окне приложения
                canvas_img = tkinter.Canvas(self.root, width=self.w, height=self.h)
                canvas_img.grid(row=row_span, column=col_span)
                canvas_img.create_image(0, 0, anchor='nw', image=self.list_links_images[i])

        return True

    def search_images_by_id(self, search_request):
        """
        Поиск картинок со схожим описанием поискового запроса по их id в БД
        :param search_request: поисковой запрос
        :return: ссылки на изображения
        """
        img_list = []

        with sq.connect("images.db") as con:
            cur = con.cursor()
            cur.execute("""
                        SELECT id, name, class, category, color_1, color_2, color_3, 
                        characteristic_1, characteristic_2, characteristic_3 
                        FROM requests
                        """)
            row = cur.fetchall()

            length_cortege_row = len(row)
            length_row = len(row[0])
            db = []

            for i in range(length_cortege_row):
                for j in range(1, length_row):
                    db.append(row[i][j])

                if self.match(search_request, db):
                    cur.execute(f"SELECT path_img FROM requests WHERE id = ?", (row[i][0],))
                    img = cur.fetchone()
                    img_list.append(*img)

                # Очистка списка
                db *= 0

        return list(set(img_list))

    @staticmethod
    def match(search, db):
        """
        Оценка совпадения поискового запроса и значений из БД
        :param search: поисковой запрос
        :param db: значения полей из БД
        :return: если к/ф совпадения > 0.65 возвращает True, иначе - False
        """
        search = re.findall(r'\w+', search.lower())
        str_db = ' '.join(db).lower()
        db = re.findall(r'\w+', str_db)

        if search and db:
            normal_form_search = []
            normal_form_db = []
            stemmer = SnowballStemmer("english")

            # Приведение слов к начальной форме
            for word in search:
                s = stemmer.stem("{}".format(word))
                normal_form_search.append(s)

            for word in db:
                s = stemmer.stem("{}".format(word))
                normal_form_db.append(s)

            # Вычисление к\ф совпадения поискового запроса и данных из БД
            sum_k = 0
            for i in range(len(normal_form_search)):
                k = round((i + 1) / (len(normal_form_search) * .75), 2)
                k *= 1 if normal_form_search[i] in normal_form_db else 0
                sum_k += k

            matching_coefficient = sum_k / len(normal_form_search)

            print(normal_form_search, normal_form_db, matching_coefficient)

            if matching_coefficient > .65:
                return True
            return False

    @staticmethod
    def translate(text):
        """
        Перевод с русского на английский
        :param text: текст на русском языке
        :return: текст на английском языке
        """
        try:
            translator = Translator()
            result = translator.translate(str(text), src='ru', dest='en')
        except Exception as ex:
            print(ex)
            return False

        return result.text.lower()


class AddingMode:
    """
    Режим добавления описания к изображениям в БД
    """
    def __init__(self):
        directory = os.path.abspath(os.curdir) + '/img/'
        files = os.listdir(directory)

        with sq.connect("photo_search.db") as con:
            cur = con.cursor()

            for img in files:
                path_img = directory + img

                # Вывод изображения из папки /img/ с помощью библиотеки matplotlib
                img_show = plt.imread(path_img)
                plt.imshow(img_show)
                plt.show()

                # Обработка и добавление описания изображения в БД
                name = input("name: ").lower()

                # Выход из режима добавления - "!"
                if name == "!":
                    break

                # При нажатии <Enter> описание для текущего изображения пропускается
                elif name != "":
                    class_name = input("class: ").lower()
                    category = input("category: ").lower()
                    characteristic_1 = input("characteristic_1: ").lower()
                    characteristic_2 = input("characteristic_2: ").lower()
                    characteristic_3 = input("characteristic_3: ").lower()
                    color_1, color_2, color_3 = self.dominant_color(path_img)

                    # Добавление описания в БД
                    cur.execute(f"""
                                INSERT INTO requests (
                                name, path_img, class, category, color_1, color_2, color_3, 
                                characteristic_1, characteristic_2, characteristic_3
                                ) 
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                                (name, path_img, class_name, category, color_1, color_2, color_3,
                                 characteristic_1, characteristic_2, characteristic_3))

    def dominant_color(self, path):
        """
        Определение трёх основных цветов изображения
        :param path: путь к изображению
        :return: список названий цветов (на англ. яз.)
        """
        color_thief = ColorThief(path)
        palette = color_thief.get_palette(color_count=2)
        color_names = []

        for rgb in palette:
            color_names.append(self.convert_rgb_to_names(rgb))

        return color_names

    @staticmethod
    def convert_rgb_to_names(rgb_tuple):
        """
        Конвертирование RGB в название цвета
        :param rgb_tuple: кортеж из RGB значений
        :return: название цвета (на англ. яз.)
        """
        css3_db = css3_hex_to_names
        names = []
        rgb_values = []

        for color_hex, color_name in css3_db.items():
            names.append(color_name)
            rgb_values.append(hex_to_rgb(color_hex))

        kdt_db = KDTree(rgb_values)
        distance, index = kdt_db.query(rgb_tuple)

        return names[index]


if __name__ == '__main__':
    """
    Переключение между режимами работы:
    SearchMode() - режим поиска изображений,
    AddingMode() - режим добавления описания к изображения в БД
    """
    SearchMode()
    # AddingMode()
