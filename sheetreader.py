import logging
import sheetdata
import validator


class SheetReader:  # Of cause, the Reader can write, too.
    def __init__(self, meta_structure, excel_header_row=1, excel_data_start_row=2):
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

    def read_sheet(self, sheet_obj, datemode):  # read excel file. I need to test this function.
        """
        :param: sheet_obj - The xlrd sheet object.
        :param: datemode - The workbook.datemode got from xlrd workbook class.
        returns a fully validated SheetData object.
        """
        column_headers = self.get_sheet_headers(sheet_obj)
        sheet_data = sheetdata.SheetData(sheet_obj.name, self.meta_structure)
        data_validator = validator.Validator(self.meta_structure)
        for row_index in range(self.excel_data_start_row, sheet_obj.nrows):
            row_data = sheet_data.new_row()
            for col_index in range(sheet_obj.ncols):
                column_header = column_headers[col_index]

                # column_name = SheetData.get_column_name(column_header)
                # data_type = SheetData.get_data_type(column_header)
                # islink = SheetData.islink(column_header)
                cell_obj = sheet_obj.cell(row_index, col_index)  # the cell obj from xlrd
                value = data_validator.cell_value_audit(sheet_data.name, column_header, cell_obj, datemode)
                row_data.add(column_header, value)

            valid = data_validator.row_value_audit(row_data)
            if valid:
                sheet_data.add_record(row_data)
        return sheet_data

    def write_book_header(self, workbook):
        excel_header_row = self.excel_header_row
        excel_data_start_row = self.excel_data_start_row
        meta_structure = self.meta_structure
        version_dict = meta_structure.version
        version = version_dict['current']
        # Create Instructions worksheet
        sheet0 = workbook.add_worksheet('Instructions')
        sheet0.write(0, 0, 'Version ' + version)  # This will need to come from URL, not hardcoded
        sheet0.write(1, 0, 'Updated Aug 29, 2017')
        sheet0.write(2, 0, 'Note: All fields except System Accession and User Accession are required unless otherwise specified.')
        sheet0.write(3, 0, 'Note: User Accessions are placeholders used to link entries together prior to submission. They must follow the specified format (e.g, URSBPRxxx) and be unique within this workbook. Once submitted, each entry will be automatically assigned a System Accession (e.g., TRGTBPRxxx). Metadata can be updated by resubmitting entries with the System Accession field populated.')
        sheet0.write(4, 0, 'Note: Required metadata fields are colored gold, while optional fields are orange. Metadata connections are colored blue. To create a connection, specify the accession (user or system) of the object you wish to link to.')
        sheet0.write(5, 0, 'Note: Experiments organize data files within the Data Portal. Please group together technical replicates within a single Experiment.')

        # Create Lists worksheet
        sheet1 = workbook.add_worksheet('Lists')
        lists = 0
        for sheet_name in meta_structure.schema_dict.keys():
            categories = meta_structure.get_categories(sheet_name)
            # print category
            sheet_schema = meta_structure.get_sheet_schema(sheet_name)
            sheet_relationships = meta_structure.get_sheet_link(sheet_name)
            sheet = workbook.add_worksheet(sheet_name)

            # Print out standard headers and formatting for each sheet
            bold_format = workbook.add_format({'bold': True})
            sheet.write(0, 0, sheet_name, bold_format)
            user_accession_format = meta_structure.get_user_accession_rule(sheet_name) + "####"  # with 4 # at the end of user accession rule here.
            sheet.write(0, 1, user_accession_format, bold_format)
            # Column headers
            bold_gray = workbook.add_format({'bold': True, 'bg_color': 'B6B6B6'})
            bold_dark = workbook.add_format({'bold': True, 'bg_color': 'FED254'})  # format3 used for required columns
            bold_light = workbook.add_format({'bold': True, 'bg_color': 'FFB602'})  # format4 used for not required columns
            bold_blue = workbook.add_format({'bold': True, 'bg_color': 'B0CDEA'})        # format5 used for link columns
            bold_red = workbook.add_format({'bold': True, 'font_color': 'red'})  # format used in the list tab header.
            # schema columns
            for m in range(0, len(sheet_schema)):
                # Write header
                column_dict = sheet_schema[m]
                if m == 0:
                    sheet.write(excel_header_row, m, column_dict['text'], bold_gray)  # system accession
                elif 'required' in column_dict and column_dict['required']:  # Color-coding required and optional fields
                    sheet.write(excel_header_row, m, column_dict['text'], bold_dark)
                else:
                    sheet.write(excel_header_row, m, column_dict['text'], bold_light)
                # Write comment
                if 'placeholder' in column_dict and len(column_dict['placeholder']) > 0:
                    sheet.write_comment(excel_header_row, m, column_dict['placeholder'])
                # Format entire column
                if 'values' in column_dict:  # Drop-down
                    if column_dict['values_restricted']:  # Drop-down with restricted values
                        sheet.data_validation(excel_data_start_row, m, 10000, m,
                                              {'validate': 'list',
                                               'source': column_dict['values'],
                                               'input_title': 'Enter a value:',
                                               'input_message': 'Select an option.',
                                               'error_title': 'Error:',
                                               'error_message': 'Select value from list.'
                                               })
                    else:  # Drop-down with non-restricted values
                        sheet.data_validation(excel_data_start_row, m, 10000, m,
                                              {'validate': 'length',  # Work on this
                                               'criteria': '>',
                                               'value': 1,
                                               'input_message': 'Enter value from Lists: ' + column_dict['text'] + ' (Column ' + chr(lists + 65) + ') OR enter own value.'
                                               })
                        sheet1.write(0, lists, column_dict['text'], bold_red)
                        for p in range(0, len(column_dict['values'])):
                            sheet1.write(p + 1, lists, column_dict['values'][p])
                        lists += 1
            # Connection columns
            for n in range(0, len(sheet_relationships['connections'])):
                link_dict = sheet_relationships['connections'][n]
                sheet.write(excel_header_row, n + m + 1, link_dict['display_name'], bold_blue)
                if len(link_dict['placeholder']) > 0:
                    sheet.write_comment(excel_header_row, n + m + 1, link_dict['placeholder'])

    def write_book(self, workbook, book_data):
        meta_structure = self.meta_structure
        date_format = workbook.add_format({'num_format': 'mm/dd/yy'})  # Format for date fields
        for sheet_name, sheet_data in book_data.data.items():
            # print category
            sheet_schema = meta_structure.get_sheet_schema(sheet_name)
            sheet_relationships = meta_structure.get_sheet_link(sheet_name)
            sheet = workbook.get_worksheet_by_name(sheet_name)
            total_rows = len(sheet_data.all_records)
            for record_count, record_row in enumerate(sheet_data.all_records):
                row = record_count + self.excel_data_start_row
                logging.info("Printing %d of %d rows in excel sheet %s" % (record_count + 1, total_rows, sheet_name))
                for i in range(0, len(sheet_schema)):
                    column_dict = sheet_schema[i]
                    field = column_dict['name']
                    datatype = column_dict['type']
                    requrirement = column_dict.get('required')
                    if field in record_row.schema.keys():
                        record_data = record_row.schema[field]
                        if (datatype == "date"):  # For dates, convert to date format if possible
                            try:
                                float(record_data)
                                sheet.write(row, i, float(record_data), date_format)
                            except ValueError:
                                sheet.write(row, i, record_data)
                        else:
                            sheet.write(row, i, record_data)
                    elif requrirement == "true":  # Print placeholders only if field is required
                        if datatype == "number":
                            sheet.write(row, i, -1)
                        else:
                            sheet.write(row, i, 'NA')

                for j in range(0, len(sheet_relationships['connections'])):
                    link_dict = sheet_relationships['connections'][j]
                    connection = link_dict['name']
                    for connection_name in record_row.relationships[connection]:
                        if connection_name == link_dict['to']:
                            links_to = record_row.relationships[connection][connection_name]

                    if len(links_to) > 0:
                        sheet.write(row, i + j + 1, ','.join(links_to))  # Use comma to separate entries for those with multiple allowed
