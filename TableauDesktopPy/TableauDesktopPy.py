from zipfile import ZipFile
from lxml import etree
import pandas as pd
import re


class Workbook:
    """
    Defines a workbook object from a filename.
    """

    def __init__(self, filename):
        self.filename = filename
        self.xml = self._get_xml()

        self.custom_sql = self._get_custom_sql()
        self.excel = self._get_excel()
        self.onedrive = self._get_onedrive()
        self.connections = self._get_db_connections()

        self.fonts = self._get_fonts()
        self.colors = self._get_colors()
        self.color_palettes = self._get_color_palettes()
        self.images = self._get_images()
        self.shapes = self._get_shapes()

        self.fields = self._get_fields()
        self.active_fields = self._get_active_fields()

    @property # allow hidden fields attrib to get value after calling hide method
    def hidden_fields(self):
        return self._get_hidden_fields()

    def _get_xml(self):
        """
        Returns the xml of the given .twb or .twbx file.
        """

        # Ensure workbook_file is a workbook file
        twb = self.filename.split(".")

        if twb[-1][:3] != "twb" or len(twb) == 1:
            return self.filename + " is not a valid .twb or .twbx file."

        else:

            # unzip packaged workbooks to obtain xml
            if twb[-1] == "twb":
                xml = etree.parse(self.filename).getroot()

            else:
                with open(self.filename, "rb") as binfile:
                    twbx = ZipFile(binfile)
                    name = [w for w in twbx.namelist() if w.find(".twb") != -1][0]
                    unzip = twbx.open(name)
                    xml = etree.parse(unzip).getroot()

            return xml

    def _get_custom_sql(self):
        """
        Returns a list of all unique custom sql queries in the workbook.
        """

        search = self.xml.xpath("//relation[@type='text']")
        queries = list(set([sql.text.lower() for sql in search]))

        return queries

    def _get_excel(self):
        """
        Returns a list of excel and csv connections in the workbook.
        """

        search = self.xml.xpath("//connection[@filename != '']")
        files = list(set([xls.attrib["filename"].lower() for xls in search]))

        return files

    def _get_onedrive(self):
        """
        Returns a list of onedrive connections in the workbook.
        """

        search = self.xml.xpath("//connection[@cloudFileProvider='onedrive']")
        onedrive = list(set([od.attrib["filename"].lower() for od in search]))

        return onedrive

    def _get_db_connections(self):

        """
        Returns a list of other database connections in the workbook.
        """

        search = self.xml.xpath("//connection[@dbname]")
        dbs = list(set([(db.attrib["dbname"],) for db in search]))

        return dbs

    def _get_fonts(self):
        """
        Returns a list of fonts used in the workbook.
        """

        font_search = self.xml.xpath("//format[@attr = 'font-family']")
        fonts = list(set([font.attrib["value"].lower() for font in font_search]))

        return fonts

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
                for color in color_search:
                    all_colors.append(
                        (
                            sheet.attrib["name"],
                            style.attrib["element"],
                            color.attrib["value"],
                        )
                    )

            # Get tooltip elements for each worksheet
            text_search = sheet.xpath(
                ".//formatted-text[./run[contains(@fontcolor, '#')]]"
            )
            for text in text_search:

                # Get fontcolors for each tooltip text element
                ttcolor_search = text.xpath(".//run[contains(@fontcolor, '#')]")
                for color in ttcolor_search:
                    all_colors.append(
                        (
                            sheet.attrib["name"],
                            "tooltip",
                            color.attrib["fontcolor"],
                        )
                    )

        unique_colors = list(set(all_colors))

        color_df = pd.DataFrame(
            unique_colors, columns=["Sheet", "Element", "Color"]
        ).sort_values(["Sheet", "Element"])

        return color_df

    def _get_color_palettes(self):
        """
        Returns list of all named color palettes used in the workbook.
        """

        search = self.xml.xpath("//encoding[@palette !='']")
        palettes = list(set([color.attrib["palette"] for color in search]))

        return palettes

    def _get_hidden_fields(self):
        """
        Returns list of all hidden fields and their datasources in the workbook.
        """

        datasources = self.xml.xpath("//datasource[./column[@caption or @name]]")
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

        views = self.xml.xpath("//view[./datasource-dependencies//column[@caption or @name]]")
        regex = r"^\[|\]\Z"  # replace brackets from field strings
        fields = []

        for v in views:

            datasources = v.xpath("./datasource-dependencies[./column[@caption or @name]]")

            for d in datasources:

                # datasource-dependencies element does not show datasource name, just coded string
                ds_name = d.attrib["datasource"]
                ds_caption = v.xpath(".//datasource[@name='{}']".format(ds_name))[0].attrib["caption"]

                # return captions for calculated fields, otherwise return name
                has_caption = d.xpath("./column[@caption and @name]")
                all_cols = d.xpath("./column[@name]")

                fields += [
                    (col.attrib["caption"], ds_caption) for col in has_caption
                ]
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

        datasources = self.xml.xpath("//datasource[./column[@caption or @name]]")
        regex = r"^\[|\]\Z"  # replace brackets from field strings
        fields = []

        for d in datasources:

            # return captions for calculated fields, otherwise return name
            has_caption = d.xpath("./column[@caption and @name]")
            all_cols = d.xpath("./column[@name]")

            fields += [
                (col.attrib["caption"], d.attrib["caption"]) for col in has_caption
            ]
            fields += [
                (re.sub(regex, "", col.attrib["name"]), d.attrib["caption"])
                for col in all_cols
                if col not in has_caption
            ]

        return sorted(fields)

    def _get_images(self):
        """
        Returns list of all image paths in the workbook.
        """

        search = self.xml.xpath(
            "//zone[@_.fcp.SetMembershipControl.false...type = 'bitmap']"
        )
        images = list(set([img.attrib["param"].lower() for img in search]))

        return images

    def _get_shapes(self):
        """
        Returns list of all shape names in the workbook.
        """

        search = self.xml.xpath("//shape[@name != '']")
        shapes = list(set([shape.attrib["name"].lower() for shape in search]))

        return shapes

    def hide_field(self, field: str, datasource: str = None, hide: bool = True):
        """
        Hides arbitrary field from workbook.
        - datasource: if the datasource is not specified, all instances of the
        provided field (for all datasources) will be hidden.
        - hide: by default, the function hides fields. Set hide to False to
        unhide hidden fields from the workbook.
        """

        col_name = "[{}]".format(field)

        # search for captions for calculated fields, otherwise search for name
        if datasource == None:  # grab all instances of field
            to_hide = self.xml.xpath(
                "//datasource/column[@name = '{}']".format(col_name)
            ) + self.xml.xpath("//datasource/column[@caption = '{}']".format(field))

        else:  # grab all instances of datasource/field (should be length 1)
            to_hide = self.xml.xpath(
                "//datasource[@caption = '{}']/column[@name = '{}']".format(
                    datasource, col_name
                )
            ) + self.xml.xpath(
                "//datasource[@caption = '{}']/column[@caption = '{}']".format(
                    datasource, field
                )
            )

        for col in to_hide:
            col.attrib["hidden"] = str(hide).lower()
