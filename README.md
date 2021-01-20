# TableauDesktopPy
 Tools for extracting metadata from Tableau Desktop workbook files. This package parses the underlying xml of a workbook to retrieve information on its style and data connections.

 ## Installation

 Install with pip:

 ```pip install TableauDesktopPy```

 ## Usage

 1. Provide a valid Tableau workbook file ('.twb' or '.twbx') to declare a `Workbook` object:

 ```
import TableauDesktopPy as tdp

my_workbook = tdp.Workbook("C:\Users\bpewyllie\test_workbook.twbx")
 ```

 2. Then use any of the following attributes to retrieve workbook metadata:

 * `Workbook.colors`
 * `Workbook.custom_sql`
 * `Workbook.excel`
 * `Workbook.fonts`
 * `Workbook.fields`
 * `Workbook.onedrive`
 * `Workbook.images`
 * `Workbook.shapes`
 * ... and more

 3. Other metadata may be retrieved by calling the `Workbook.xml` attribute and parsing with an xml parser such as BeautifulSoup.

 4. The module also provides methods for modifying a workbook's xml. `Workbook.hide_field()`, for example, hides an arbitrary field from the workbook's xml. To make the changes appear when opening the workbook in Tableau, first call the `Workbook.save()` method.


## To do (for release 1.0.8)

* ~~Include datasource in parenthetical in any field-related attribute to overcome duplicate-named fields from different datasources~~

* Create method for building workbook README file

* ~~Create save method for overwriting workbooks~~

* ~~Create method for changing fonts~~