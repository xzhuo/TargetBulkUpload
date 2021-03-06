import logging
import sheetdata
import validator
import datetime
import csv


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
        schema_headers = self.meta_structure.get_schema_column_headers(sheet_obj.name)
        link_headers = self.meta_structure.get_link_column_headers(sheet_obj.name)
        column_headers = self.get_sheet_headers(sheet_obj)
        sheet_data = sheetdata.SheetData(sheet_obj.name, self.meta_structure)
        data_validator = validator.Validator(self.meta_structure)
        validation = True
        for row_index in range(self.excel_data_start_row, sheet_obj.nrows):
            row_data = sheet_data.new_row()
            for col_index in range(sheet_obj.ncols):
                column_header = column_headers[col_index]
                if column_header in schema_headers or column_header in link_headers:
                    # column_name = SheetData.get_column_name(column_header)
                    # data_type = SheetData.get_data_type(column_header)
                    # islink = SheetData.islink(column_header)
                    cell_obj = sheet_obj.cell(row_index, col_index)  # the cell obj from xlrd
                    try:
                        value = data_validator.cell_value_audit(sheet_data.name, column_header, cell_obj, datemode)
                    except validator.ValidatorError as validator_error:
                        logging.error(validator_error)
                        validation = False
                    except TypeError as type_error:
                        logging.error(type_error)
                        validation = False
                    row_data.add(column_header, value)

            try:
                data_validator.row_value_audit(row_data)
            except validator.ValidatorError as validator_error:
                logging.error(validator_error)
                validation = False
            except TypeError as type_error:
                logging.error(type_error)
                validation = False
            if not validation:
                break
            sheet_data.add_record(row_data)
        return sheet_data, validation

    def write_book_header(self, workbook, csv_ready=False):
        excel_header_row = self.excel_header_row
        if excel_header_row < 1 and csv_ready:
            logging.error("CSV ready template needs at least 2 lines of header!")
        excel_data_start_row = self.excel_data_start_row
        meta_structure = self.meta_structure
        version_dict = meta_structure.version
        version = version_dict['current']
        # Create Instructions worksheet
        sheet0 = workbook.add_worksheet('Instructions')
        sheet0.write(0, 0, 'Version ' + version)  # This will need to come from URL, not hardcoded
        today = datetime.datetime.today().strftime('%Y-%m-%d')
        sheet0.write(1, 0, 'Updated on ' + today)

        # sheet0.write(1, 0, 'Updated Dec 11, 2017')
        # sheet0.write(2, 0, 'Note: All fields except System Accession are required unless otherwise specified.')
        sheet0.write(2, 0, 'Note: User Accessions are unique accessions assigned by the user. They must follow the specified format (e.g, URSBPRxxx) and be unique for all your records. Once submitted, each entry will be automatically assigned a System Accession (e.g., TRGTBPRxxx). Metadata can be updated by resubmitting entries with the System Accession field populated.')
        sheet0.write(3, 0, 'Note: Required metadata fields are colored brown, while optional fields are yellow. Metadata required connections are colored purple, optional connections are blue. To create a connection, specify the accession (user or system) of the object you wish to link to.')
        sheet0.write(4, 0, 'In the File tab, you must complete the fields Pair and Paired file for paired-end files.')
        sheet0.write(5, 0, 'Note: By default, paired files and sequencing replicates will be organized into a single Experiment in the data portal. Please contact the DCC for a custom organization.')
        # sheet0.write(6, 0, 'Note: By default, paired files and sequencing replicates will be organized into a single Experiment in the data portal. You can overwrite this organization using the Experiment tab. However, it is not required.')

        # Create Lists worksheet
        sheet1 = workbook.add_worksheet('Lists')
        lists = 0
        for sheet_name in meta_structure.schema_dict.keys():
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
            bold_dark = workbook.add_format({'bold': True, 'bg_color': 'CC6600'})  # format3 used for required columns
            light_yellow = workbook.add_format({'bold': False, 'italic': True, 'bg_color': 'FED254'})  # format4 used for not required columns
            light_blue = workbook.add_format({'bold': False, 'italic': True, 'bg_color': 'B0CDEA'})        # format5 used for not required link columns
            bold_purple = workbook.add_format({'bold': True, 'bg_color': '#A569BD'})        # format used for required link columns
            bold_red = workbook.add_format({'bold': True, 'font_color': 'red'})  # format used in the list tab header.
            # schema columns
            header_property = 'name' if csv_ready else 'text'
            for m in range(0, len(sheet_schema)):
                # Write header
                column_dict = sheet_schema[m]
                if m == 0 or m == 1:
                    if csv_ready:
                        sheet.write(excel_header_row - 1, m, column_dict['text'], bold_gray)  # system accession
                    sheet.write(excel_header_row, m, column_dict[header_property], bold_gray)  # system accession
                elif 'required' in column_dict and column_dict['required']:  # Color-coding required and optional fields
                    if csv_ready:
                        sheet.write(excel_header_row - 1, m, column_dict['text'], bold_dark)
                    sheet.write(excel_header_row, m, column_dict[header_property], bold_dark)
                else:
                    if csv_ready:
                        sheet.write(excel_header_row - 1, m, column_dict['text'], light_yellow)
                    sheet.write(excel_header_row, m, column_dict[header_property], light_yellow)
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
            header_property = 'name' if csv_ready else 'display_name'
            for n in range(0, len(sheet_relationships['connections'])):
                link_dict = sheet_relationships['connections'][n]
                if 'required' in link_dict and link_dict['required']:
                    if csv_ready:
                        sheet.write(excel_header_row - 1, n + m + 1, link_dict['display_name'], bold_purple)
                    sheet.write(excel_header_row, n + m + 1, link_dict[header_property], bold_purple)
                else:
                    if csv_ready:
                        sheet.write(excel_header_row - 1, n + m + 1, link_dict['display_name'], light_blue)
                    sheet.write(excel_header_row, n + m + 1, link_dict[header_property], light_blue)
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
                    if connection in record_row.relationships:
                        for connection_name in record_row.relationships[connection]:
                            if connection_name == link_dict['to']:
                                links_to = record_row.relationships[connection][connection_name]

                        if len(links_to) > 0:
                            sheet.write(row, i + j + 1, ','.join(links_to))  # Use comma to separate entries for those with multiple allowed

    def write_csv(self, book_data):
        for sheet_name, sheet_data in book_data.data.items():
            # print category
            properties_flat_json = [x.schema for x in sheet_data.all_records]
            self.json_2_csv(properties_flat_json, sheet_name + "nodes.csv")
            data_both = [x for x in sheet_data.all_records]
            relationships_flat_json = []
            # import ipdb;ipdb.set_trace()
            for each_both_dict in data_both:
                each_dict = {"accession": each_both_dict.schema.get("accession"), "user": each_both_dict.schema.get("user"), "user_accession": each_both_dict.schema.get("user_accession")}
                for name, link_to_dict in each_both_dict.relationships.items():
                    for link_to, acc_list in link_to_dict.items():
                        for acc in acc_list:
                            each_dict.update({name + ":" + link_to: acc})
                relationships_flat_json.append(each_dict)

            self.json_2_csv(relationships_flat_json, sheet_name + "relationships.csv")

    def json_2_csv(self, input, csv_file):  # the input is a list of single level dict.
        '''https://stackoverflow.com/questions/1871524/how-can-i-convert-json-to-csv'''
        columns = [x for row in input for x in row.keys()]
        columns = list(set(columns))
        with open(csv_file, 'w') as out_file:
            csv_w = csv.writer(out_file)
            csv_w.writerow(columns)
            for i_r in input:
                csv_w.writerow(map(lambda x: i_r.get(x, ""), columns))

# the structure:
# ipdb> pp sheet_relationships
# {'all': 'bioprojects',
#  'connections': [{'all': 'labs',
#                   'allow_multiple': True,
#                   'display_name': 'Lab',
#                   'name': 'works_on',
#                   'placeholder': 'Link to Lab accession',
#                   'required': False,
#                   'to': 'lab',
#                   'type': 'text'}],
#  'one': 'bioproject',
#  'prefix': 'TRGTBPR000',
#  'usr_prefix': 'USRBPR000'}
# ipdb> pp sheet_schema
# [{'name': 'accession', 'text': 'System Accession', 'type': 'text'},
#  {'name': 'user_accession',
#   'placeholder': 'USRBPR####',
#   'required': False,
#   'text': 'User accession',
#   'type': 'text'},
#  {'name': 'title',
#   'placeholder': '255 characters max',
#   'required': True,
#   'text': 'Title',
#   'type': 'text'},
#  {'name': 'design',
#   'placeholder': 'Description of goals and objectives (publically accessible)',
#   'required': True,
#   'text': 'Design',
#   'type': 'textarea'},
#  {'name': 'summary',
#   'placeholder': 'Description of number of samples, replicates, controls, etc.',
#   'required': True,
#   'text': 'Summary',
#   'type': 'textarea'}]

#   ipdb> pp sheet_data.__dict__
# {'all_records': [<rowdata.RowData object at 0x10e59bfd0>,
#                  <rowdata.RowData object at 0x10e59bef0>,
#                  <rowdata.RowData object at 0x10e59bf60>,
#                  <rowdata.RowData object at 0x10e59bf28>,
#                  <rowdata.RowData object at 0x10e59beb8>,
#                  <rowdata.RowData object at 0x10e59be10>,
#                  <rowdata.RowData object at 0x10e59be48>,
#                  <rowdata.RowData object at 0x10e5a69e8>,
#                  <rowdata.RowData object at 0x10e5a6668>],
#  'meta_structure': <metastructure.MetaStructure object at 0x10d70d240>,
#  'name': 'Bioproject'}
# ipdb> pp sheet_data.all_records[0].__dict__
# {'meta_structure': <metastructure.MetaStructure object at 0x10d70d240>,
#  'relationships': {'works_on': {'lab': ['TRGTLAB0003']}},
#  'schema': {'accession': 'TRGTBPR0002',
#             'created': 1497295464032,
#             'design': 'To investigate alternations in transcription profile '
#                       'and chromatin accessibility in BPA exposure mice.',
#             'modified': 1533668028925,
#             'summary': 'Ctrl / Low / Up-dose exposure, female / male '
#                        'separately',
#             'title': 'BPA exposure on prenatal mice',
#             'user': 'yeminlan',
#             'user_accession': 'NA-web'},
#  'sheet_name': 'Bioproject'}
