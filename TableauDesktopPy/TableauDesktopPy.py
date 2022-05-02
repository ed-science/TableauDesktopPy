import zipfile
import lxml.etree
import pandas
import re
import getpass
import os
import datetime
import pkg_resources


class Workbook:
    """
    Defines a workbook object from a filename.
    """

    def __init__(self, filename):
        self.filename = os.path.normpath(filename)
        self.xml = self._get_xml()

        self.custom_sql = self._get_custom_sql()
        self.files = self._get_files()
        self.onedrive = self._get_onedrive()
        self.connections = self._get_db_connections()

        # self.fonts = self._get_fonts()
        self.colors = self._get_colors()
        self.color_palettes = self._get_color_palettes()
        self.images = self._get_images()
        self.shapes = self._get_shapes()

    @property  # allow attribute to get value after calling hide fields method
    def hidden_fields(self):
        return self._get_hidden_fields()

    @property
    def active_fields(self):
        return self._get_active_fields()

    @property
    def fields(self):
        return self._get_fields()

    @property
    def fonts(self):
        return self._get_fonts()

    def _get_xml(self):
        """
        Returns the xml of the given .twb or .twbx file.
        """

        # Ensure workbook_file is a workbook file
        twb = self.filename.split(".")

        if twb[-1][:3] != "twb" or len(twb) == 1:
            return self.filename + " is not a valid .twb or .twbx file."

        # unzip packaged workbooks to obtain xml
        if twb[-1] == "twb":
            xml = lxml.etree.parse(self.filename).getroot()

        else:
            with open(self.filename, "rb") as binfile:
                twbx = zipfile.ZipFile(binfile)
                name = [w for w in twbx.namelist() if w.find(".twb") != -1][0]
                unzip = twbx.open(name)
                xml = lxml.etree.parse(unzip).getroot()

        return xml

    def _get_custom_sql(self):
        """
        Returns a list of all unique custom sql queries in the workbook.
        """

        search = self.xml.xpath("//relation[@type='text']")
        return list({sql.text.lower() for sql in search})

    def _get_files(self):
        """
        Returns a list of file connections in the workbook.
        """

        search = self.xml.xpath("//connection[@filename != '']")
        return list({f.attrib["filename"] for f in search})

    def _get_onedrive(self):
        """
        Returns a list of onedrive connections in the workbook.
        """

        search = self.xml.xpath("//connection[@cloudFileProvider='onedrive']")
        return list({od.attrib["filename"] for od in search})

    def _get_db_connections(self):

        """
        Returns a list of other database connections in the workbook.
        """

        search = self.xml.xpath("//connection[@dbname]")
        return list({(db.attrib["dbname"], db.attrib["class"]) for db in search})

    def _get_fonts(self):
        """
        Returns a list of fonts used in the workbook.
        """

        font_search1 = self.xml.xpath("//format[@attr = 'font-family']")
        font_search2 = self.xml.xpath("//run[@fontname]")

        fonts1 = [font.attrib["value"] for font in font_search1]
        fonts2 = [font.attrib["fontname"] for font in font_search2]
        return list(set(fonts1 + fonts2))

    def _get_colors(self):
        """
        Returns dataframe of all individual colors and their associated elements in
        the workbook.
        """

        all_colors = []

        # Get worksheets in workbook
        wksht_search = self.xml.xpath("//worksheet")
        for sheet in wksht_search:

            # Get style elements for each worksheet
            style_search = sheet.xpath(".//style-rule[./format[contains(@value, '#')]]")
            for style in style_search:

                # Get colors for each style element
                color_search = style.xpath(".//format[contains(@value, '#')]")
                all_colors.extend(
                    (
                        sheet.attrib["name"],
                        style.attrib["element"],
                        color.attrib["value"],
                    )
                    for color in color_search
                )

            # Get tooltip elements for each worksheet
            text_search = sheet.xpath(
                ".//formatted-text[./run[contains(@fontcolor, '#')]]"
            )
            for text in text_search:

                # Get fontcolors for each tooltip text element
                ttcolor_search = text.xpath(".//run[contains(@fontcolor, '#')]")
                all_colors.extend(
                    (
                        sheet.attrib["name"],
                        "tooltip",
                        color.attrib["fontcolor"],
                    )
                    for color in ttcolor_search
                )

        unique_colors = list(set(all_colors))

        return pandas.DataFrame(
            unique_colors, columns=["Sheet", "Element", "Color"]
        ).sort_values(["Sheet", "Element"])

    def _get_color_palettes(self):
        """
        Returns list of all named color palettes used in the workbook.
        """

        search = self.xml.xpath("//encoding[@palette !='']")
        return list({color.attrib["palette"] for color in search})

    def _get_hidden_fields(self):
        """
        Returns list of all hidden fields and their datasources in the
        workbook.
        """

        datasources = self.xml.xpath(
            "//datasource[@caption and ./column[@caption or @name]]"
        )
        regex = r"^\[|\]\Z"  # replace brackets from field strings
        fields = []

        for d in datasources:

            # return captions for calculated fields, otherwise return name
            has_caption = d.xpath("./column[@caption and @name and @hidden='true']")
            all_cols = d.xpath("./column[@name and @hidden='true']")

            fields += [
                (col.attrib["caption"], d.attrib["caption"]) for col in has_caption
            ]
            fields += [
                (re.sub(regex, "", col.attrib["name"]), d.attrib["caption"])
                for col in all_cols
                if col not in has_caption
            ]

        return sorted(list(set(fields)))

    def _get_active_fields(self):
        """
        Returns list of all used fields and their datasources in the workbook.
        """

        # views = self.xml.xpath(("//view[.//datasource[@name != 'Parameters']]"))
        regex = r"^\[|\]\Z"  # replace brackets from field strings
        fields = []

        # for v in views:

        datasources = self.xml.xpath(
            (
                "//datasource-dependencies[@datasource != 'Parameters' and "
                "./column[@caption or @name]]"
            )
        )

        for d in datasources:

            # datasource-dependencies element does not show datasource name,
            # just coded string
            ds_name = d.attrib["datasource"]
            ds_caption = self.xml.xpath(
                f".//datasource[@name='{ds_name}' and @caption]"
            )[0].attrib["caption"]


            # return captions for calculated fields, otherwise return name
            has_caption = d.xpath("./column[@caption and @name]")
            all_cols = d.xpath("./column[@name]")

            fields += [(col.attrib["caption"], ds_caption) for col in has_caption]
            fields += [
                (re.sub(regex, "", col.attrib["name"]), ds_caption)
                for col in all_cols
                if col not in has_caption
            ]

        return sorted(list(set(fields)))

    def _get_fields(self):
        """
        Returns list of all fields and their datasources in the workbook.
        """

        fields = self.hidden_fields + self.active_fields

        return sorted(fields)

    def _get_images(self):
        """
        Returns list of all image paths in the workbook.
        """

        search = self.xml.xpath(
            "//zone[@_.fcp.SetMembershipControl.false...type = 'bitmap']"
        )
        return list({img.attrib["param"].lower() for img in search})

    def _get_shapes(self):
        """
        Returns list of all shape names in the workbook.
        """

        search = self.xml.xpath("//shape[@name != '']")
        return list({shape.attrib["name"].lower() for shape in search})

    def hide_field(self, field: str, datasource: str = None, hide: bool = True):
        """
        Hides arbitrary field from workbook.
        - datasource: if the datasource is not specified, all instances of the
        provided field (for all datasources) will be hidden.
        - hide: by default, the function hides fields. Set hide to False to
        unhide hidden fields from the workbook.
        """

        col_name = f"[{field}]"

        # search for captions for calculated fields, otherwise search for name
        if datasource is None:  # grab all instances of field
            to_hide = self.xml.xpath(
                f"//datasource/column[@name = '{col_name}']"
            ) + self.xml.xpath(f"//datasource/column[@caption = '{field}']")


        else:  # grab all instances of datasource/field (should be length 1)
            to_hide = self.xml.xpath(
                f"//datasource[@caption = '{datasource}']/column[@name = '{col_name}']"
            ) + self.xml.xpath(
                f"//datasource[@caption = '{datasource}']/column[@caption = '{field}']"
            )


        for col in to_hide:
            col.attrib["hidden"] = str(hide).lower()

    def change_fonts(self, default: str = "Arial", font_dict: dict = None):
        """
        Replaces fonts in workbook xml.
        - default: default font to map all fonts to.
        - font_dict: mapping of current fonts to new fonts; if no font_dict is provided,
        all fonts are changed to default argument. font_dict requires a mapping from
        "Default" to a new font if you want to replace default fonts that are not
        mentioned explicitly. Otherwise, the font from the default argument is used.
        """

        if font_dict is None:

            fonts_1 = self.xml.xpath("//format[@attr = 'font-family']")
            fonts_2 = self.xml.xpath("//run")

            for font in fonts_1:
                font.attrib["value"] = default

            for font in fonts_2:
                font.attrib["fontname"] = default

            # replace fonts that do not show up explicitly
            styles = self.xml.xpath("//style-rule[@element]")
            for style in styles:
                if len(style.xpath("./format[@attr = 'font-family']")) == 0:
                    style.insert(1, 
                        lxml.etree.Element(
                            "format", attrib={"attr": "font-family", "value": default}
                        )
                )

            # formatted_texts = self.xml.xpath("//formatted-text")
            # for text in formatted_texts:
            #     text.insert(1, lxml.etree.Element("run", attrib={"fontname": default}))

        else:

            if "Default" not in font_dict.keys():
                font_dict["Default"] = default

            for old_font in font_dict:

                fonts_1 = self.xml.xpath(
                    f"//format[@attr = 'font-family' and @value = '{old_font}']"
                )

                fonts_2 = self.xml.xpath(f"//run[@fontname = '{old_font}']")
                fonts_3 = [x for x in self.xml.xpath("//run") if x not in fonts_2]

                for font in fonts_1:
                    font.attrib["value"] = font_dict[old_font]

                for font in fonts_2:
                    font.attrib["fontname"] = font_dict[old_font]

                for font in fonts_3:
                    font.attrib["fontname"] = font_dict["Default"]

            # replace fonts that do not show up explicitly
            styles = self.xml.xpath("//style-rule[@element]")
            for style in styles:
                if len(style.xpath("./format[@attr = 'font-family']")) == 0:
                    style.insert(
                        lxml.etree.ElementTree.Element(
                            "format",
                            attrib={"attr": "font-family", "value": font_dict["Default"]},
                        )
                    )

            # formatted_texts = self.xml.xpath("//formatted-text")
            # for text in formatted_texts:
            #     text.insert(
            #         lxml.etree.ElementTree.Element(
            #             "run", attrib={"fontname": font_dict["Default"]}
            #         )
            #     )

    def generate_readme(
        self, save: bool = False, filename: str = None, note: str = None
    ):
        """
        Generates a 'README' documentation string for the workbook populated with
        metadata from attributes of the Workbook class.
        - save: by default, the method outputs a string. Set save to True if you would
        like to save a .txt file with the output.
        - filename: if save is enabled, filename specifies the path and name. By
        default, the file is saved as 'README.txt' in the same directory as the
        workbook.
        - note: a custom note to leave at the end of the README. If left blank, a short
        message about the README is created.
        """

        template_file = pkg_resources.resource_filename(
            "TableauDesktopPy", "assets/README-twb.txt"
        )

        with open(template_file, "r") as readme_template:
            text = readme_template.read()

        # items to fill (in order):
        # title, author, date, custom sql, db connections, file connections, note
        title = os.path.normpath(self.filename).split(os.sep)[-1]

        author = getpass.getuser()

        date = datetime.datetime.fromtimestamp(
            os.stat(self.filename).st_ctime
        ).strftime("%Y-%m-%d-%H:%M:%S")

        custom_sql = f"There are {len(self.custom_sql)} custom SQL queries in this workbook."


        # first element of c is name, second element is connection class (type)
        clean_dbs = [f"{c[0]} ({c[1]})" for c in self.connections]

        dbs = "\n   - ".join(clean_dbs) if clean_dbs else "\n   - N/A"
        files = "\n   - N/A" if self.files == [] else "\n   - ".join(self.files)
        if note is None:
            msg = f'This documentation was generated automatically at {datetime.datetime.now().strftime("%Y-%m-%d-%H:%M:%S")}'

        else:
            msg = note

        if filename is None:
            fn = os.sep.join(self.filename.split(os.sep)[:-1]) + os.sep + "README.txt"
        else:
            fn = filename

        if not save:
            return text.format(title, author, date, custom_sql, dbs, files, msg)
        with open(fn, "w") as workbook_readme:
            workbook_readme.write(
                text.format(title, author, date, custom_sql, dbs, files, msg)
            )
        return "File saved at " + fn

    def save(self, filename: str = None):
        """
        Exports xml to Tableau workbook file.
        - filename: destination and name of the file. Both packaged and unpackaged
        workbooks may be saved as ".twb" files, but only packaged workbooks may be
        saved as ".twbx" files.
        """

        fn = self.filename if filename is None else os.path.normpath(filename)
        # twb / twbx -> twb
        if fn.endswith(".twb"):
            tree = lxml.etree.ElementTree(self.xml)
            tree.write(fn)

        elif fn.endswith(".twbx") and self.filename.endswith(".twbx"):

            # create temp "[workbook name].twb files" folder for holding extracts
            path = os.sep.join(fn.split(os.sep)[:-1])
            name = fn.split(os.sep)[-1][:-1]

            if not os.path.exists(path + os.sep + name + " files"):

                os.mkdir(path=path + os.sep + name + " files")

                # store extract data in folder
                with open(self.filename, "rb") as twbx:

                    zf = zipfile.ZipFile(twbx)
                    package = [x for x in zf.namelist() if not x.endswith(".twb")]

                    for p in package:
                        zf.extract(p, path=path + os.sep + name + " files")

            # create twb
            tree = lxml.etree.ElementTree(self.xml)
            tree.write(path + os.sep + name)

            # gather all files to zip
            all_files = []

            for dirname, subdirs, files in os.walk(path):
                all_files.extend(os.path.join(dirname, filename) for filename in files)
            files_to_zip = [
                f
                for f in all_files
                if f.startswith(path + os.sep + name) and f.find(".twbx") == -1
            ]

            # zip twb with everything else
            with zipfile.ZipFile(fn, "w", zipfile.ZIP_DEFLATED) as zip_writer:

                for f in files_to_zip:
                    zip_writer.write(f, arcname="." + os.sep + name + f.split(name)[-1])

        else:
            raise NameError("Cannot save unpackaged workbooks as packaged workbooks!")
