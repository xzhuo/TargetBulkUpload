# populate_metadata_Excel.py
# TaRGET II DCC
# Exports a blank Excel metadata template or populates with previously submitted user metadata (--submission [url])
# Copyright 2017, Erica Pehrsson, erica.pehrsson@wustl.edu
# Incorporating code from JSON2Excel.py, copyright Ananda Datta, ananda.datta@wustl.edu


import sys
import requests
import xlsxwriter
import json
import argparse
import datetime
import logging
import submission_oo

# Got all the constant from submission.py.
EXCEL_HEADER_ROW = 1
EXCEL_DATA_START_ROW = EXCEL_HEADER_ROW + 1
meta_structure = MetaStructure(action_url_meta, ALL_CATEGORIES)


def get_args():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        '--submission',
        '-s',
        action="store",
        dest="submission",
        required=False,
        help="submission id. If provided, it will fetch the specific submission. Without it it will produce an empty excel template.\n",
    )
    parser.add_argument(
        '--notest',
        '-n',
        action="store_true",
        dest="notest",
        help="test flag. Same as is_production flag. \
        The metadata only fetch records from the production database if this option is TRUE.\n",
    )
    parser.add_argument(
        '--is_production',
        '-p',
        action="store_true",
        dest="is_production",
        help="test flag. default option is true, which will get records from the test database. \
        The metadata only fetch records from the production database if this option is TRUE.\n",
    )
    return parser.parse_args()


def main():
    args = get_args()
    is_production = args.is_production or args.notest

    meta_structure = submission_oo.MetaStructure.start_metastructure(is_production, ALL_CATEGORIES, SCHEMA_STRING, RELATIONSHIP_STRING, VERSION_STRING)
    version = meta_structure.version
    if args.submission:
        # Retrieve submission JSON
        submission_string = requests.get(args.submission).text
        submission = json.loads(submission_string)['submission']

        # Create workbook
        if "_id" not in submission:
            sys.exit("failed get request at line 64!")
        workbook = xlsxwriter.Workbook('TaRGET_metadata_sub_' + submission["_id"] + '_V' + version + '.xlsx')  # The submission should be extracted, replace url
    else:
        workbook = xlsxwriter.Workbook('TaRGET_metadata_V' + version + '.xlsx')

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
    for category, sheet_name in meta_structure.categories.items():
        categories = meta_structure.get_categories(sheet_name)
        # print category
        logging.info("working on %s!" % sheet_name)
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
        sheet.write(EXCEL_HEADER_ROW, 0, 'System Accession', bold_gray)
        # Field columns
        bold_dark = workbook.add_format({'bold': True, 'bg_color': 'FED254'})  # format3 used for required columns
        bold_light = workbook.add_format({'bold': True, 'bg_color': 'FFB602'})  # format4 used for not required columns
        bold_blue = workbook.add_format({'bold': True, 'bg_color': 'B0CDEA'})        # format5 used for link columns
        bold_red = workbook.add_format({'bold': True, 'font_color': 'red'})  # format used in the list tab header.
        # schema columns
        for m in range(0, len(sheet_schema)):
            # Write header
            column_dict = sheet_schema[m]
            if column_dict['required']:  # Color-coding required and optional fields
                sheet.write(EXCEL_HEADER_ROW, m + 1, column_dict['text'], bold_dark)
            else:
                sheet.write(EXCEL_HEADER_ROW, m + 1, column_dict['text'], bold_light)
            # Write comment
            if len(column_dict['placeholder']) > 0:
                sheet.write_comment(EXCEL_HEADER_ROW, m + 1, column_dict['placeholder'])
            # Format entire column
            if 'values' in column_dict:  # Drop-down
                if column_dict['values_restricted']:  # Drop-down with restricted values
                    sheet.data_validation(EXCEL_DATA_START_ROW, m + 1, 10000, m + 1,
                                          {'validate': 'list',
                                           'source': column_dict['values'],
                                           'input_title': 'Enter a value:',
                                           'input_message': 'Select an option.',
                                           'error_title': 'Error:',
                                           'error_message': 'Select value from list.'
                                           })
                else:  # Drop-down with non-restricted values
                    sheet.data_validation(EXCEL_DATA_START_ROW, m + 1, 10000, m + 1,
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
            sheet.write(EXCEL_HEADER_ROW, n + m + 2, link_dict['display_name'], bold_blue)
            if len(link_dict['placeholder']) > 0:
                sheet.write_comment(EXCEL_HEADER_ROW, n + m + 2, link_dict['placeholder'])

        # Write each object onto a single row, connection fields last
        logging.info("filling data in sheet %s" % sheet_name)
        if args.submission:
            row = EXCEL_HEADER_ROW
            entries_string = submission["details"]
            whole_data = json.loads(entries_string.replace("'", "\""))  # Gets a list of all accessions created for that object category
            date_format = workbook.add_format({'num_format': 'mm/dd/yy'})  # Format for date fields
            if categories in whole_data:
                entry_list = whole_data[categories]
                for entry in entry_list:
                    row += 1
                    record = requests.get(action_url_meta + '/api/' + categories + '/' + entry).json()
                    record_row = submission_oo.Poster.fetch_record(sheet_name, entry)  # A Rowdata obj.

                    column = 1
                    for i in range(0, len(sheet_schema)):
                        column_dict = sheet_schema[i]
                        field = column_dict['name']
                        datatype = column_dict['type']
                        requrirement = column_dict['required']
                        if field in record_row.schema.keys():
                            record_data = record_row.schema[field]
                            if (datatype == "date"):  # For dates, convert to date format if possible
                                try:
                                    float(record_data)
                                    sheet.write(row, column, float(record_data), date_format)
                                except ValueError:
                                    sheet.write(row, column, record_data)
                            else:
                                sheet.write(row, column, record_data)
                        elif requrirement == "true":  # Print placeholders only if field is required
                            if datatype == "number":
                                sheet.write(row, column, -1)
                            else:
                                sheet.write(row, column, 'NA')
                        column += 1
                    for j in range(0, len(sheet_relationships['connections'])):
                        link_dict = sheet_relationships['connections'][j]
                        connection = link_dict['name']
                        for connection_name in record.relationships[connection]:
                            if connection_name == link_dict['to']:
                                links_to = record_row.relationships[connection][connection_name]

                        if len(links_to) > 0:
                            sheet.write(row, column, ','.join(links_to))  # Use comma to separate entries for those with multiple allowed
                        column += 1

    workbook.close()


if __name__ == "__main__":
    main()
