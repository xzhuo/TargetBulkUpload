# populate_metadata_Excel.py
# TaRGET II DCC
# Exports a blank Excel metadata template or populates with previously submitted user metadata (--submission [url])
# Copyright 2017, Erica Pehrsson, erica.pehrsson@wustl.edu
# Incorporating code from JSON2Excel.py, copyright Ananda Datta, ananda.datta@wustl.edu


import sys
import logging
import requests
import xlsxwriter
import json
import argparse
import metastructure
import sheetreader
import poster


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
        '--user',
        '-u',
        action="store",
        dest="user",
        required=False,
        help="cypher query fetch all record for a user.\n",
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
    logging.getLogger().setLevel(logging.INFO)
    is_production = args.is_production or args.notest

    try:
        meta_structure = metastructure.MetaStructure(is_production)
    except metastructure.StructureError as structure_error:
        sys.exit(structure_error)

    # meta_structure = submission_oo.MetaStructure.start_metastructure(is_production, ALL_CATEGORIES, SCHEMA_STRING, RELATIONSHIP_STRING, VERSION_STRING)
    version_dict = meta_structure.version
    version = version_dict['current']
    db_poster = poster.Poster('', '', is_production, meta_structure)
    reader = sheetreader.SheetReader(meta_structure)
    if args.submission:
        # Retrieve submission JSON
        submission_string = requests.get(args.submission).text
        submission = json.loads(submission_string)['submission']

        # Create workbook
        if "_id" not in submission:
            sys.exit("failed get request at line 64!")
        workbook = xlsxwriter.Workbook('TaRGET_metadata_sub_' + submission["_id"] + '_V' + version + '.xlsx')  # The submission should be extracted, replace url
        reader.write_book_header(workbook)
        book_data = db_poster.fetch_submission(submission)
        reader.write_book(workbook, book_data)
        workbook.close()
    elif args.user:
        user = args.user
        workbook = xlsxwriter.Workbook('TaRGET_metadata_sub_' + user + '-V' + version + '.xlsx')  # The submission should be extracted, replace url
        reader.write_book_header(workbook)
        # with open(args.cypher, 'r') as file:
        #     cypher_json = json.load(file)
        # book_data = db_poster.read_cypher(cypher_json, 'Assay')
        book_data = db_poster.fetch_user_all(user)
        reader.write_book(workbook, book_data)
        workbook.close()
    else:
        workbook = xlsxwriter.Workbook('TaRGET_metadata_V' + version + '.xlsx')
        reader.write_book_header(workbook)
        workbook.close()


if __name__ == "__main__":
    main()
