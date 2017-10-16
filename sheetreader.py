class SheetReader:
    def __init__(self, meta_structure, excel_header_row, excel_data_start_row):
        self.meta_structure = meta_structure
        self.excel_header_row = excel_header_row
        self.excel_data_start_row = excel_data_start_row

    def get_sheet_headers(self, sheet_obj):
        """
        Get all the columan headers from worksheet.

        Note the difference between SheetReader.get_sheet_headers and MetaStructure.get_all_column_headers.
        The former get the headers from the file, while the later get the headers from metadata database structure + system accession.
        :param: sheet_obj - the sheet obj from xlrd package.
        :return: a list of all column headers in the worksheet
        """
        excel_header_row = self.excel_header_row
        return [str(sheet_obj.cell(excel_header_row, col_index).value).rstrip() for col_index in range(sheet_obj.ncols)]  # start from row number 1 to skip header

    def verify_column_names(self, sheet_obj):
        """
        Compare all the columns names in the worksheet with correspondence databases fields.

        Pops up a warning if there is any database field missing in the worksheet.
        Also gives a warning if any column in the worksheet will be skipped because it does not match a field in the database.
        """
        sheet_name = sheet_obj.name
        column_headers_from_sheet = set(self.get_sheet_headers(sheet_obj))
        column_headers_from_structure = set(self.meta_structure.get_all_column_headers(sheet_name))
        missing_columns = column_headers_from_structure - column_headers_from_sheet
        unknown_columns = column_headers_from_sheet - column_headers_from_structure
        if len(missing_columns) or len(missing_columns):
            print("version change history:")
            pp = pprint.PrettyPrinter(indent=2)
            version_number = self.meta_structure.version
            pp.pprint(version_number)
            for column_header in missing_columns:
                logging.warning("warning! column %s is missing in %s. Please update your excel file to the latest version." % (column_header, sheet_name))
            for column_header in unknown_columns:
                logging.warning("warning! The database does not know what is column %s in %s. Please update your excel file to the latest version." % (column_header, sheet_name))

    def read_sheet(self, sheet_obj, datemode):  # read excel file. I need to test this function.
        """
        :param: sheet_obj - The xlrd sheet object.
        :param: datemode - The workbook.datemode got from xlrd workbook class.
        returns a fully validated SheetData object.
        """
        column_headers = self.get_sheet_headers(sheet_obj)
        sheet_data = SheetData(sheet_obj.name, self.meta_structure)
        for row_index in range(self.excel_data_start_row, sheet_obj.nrows):
            row_data = sheet_data.new_row()
            for col_index in range(sheet_obj.ncols):
                column_header = column_headers[col_index]

                # column_name = SheetData.get_column_name(column_header)
                # data_type = SheetData.get_data_type(column_header)
                # islink = SheetData.islink(column_header)
                cell_obj = sheet_obj.cell(row_index, col_index)  # the cell obj from xlrd
                row_data.validate_add(column_header, cell_obj, datemode)
            sheet_data.filter_add(row_data)
        return sheet_data
