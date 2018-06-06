# prep_meta_submission.py
# TaRGET II DCC
# Exports an Excel metadata template with some file infomation filled in.


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
        '--submission_id',
        '-s',
        action="store",
        dest="submission_id",
        required=True,
        help="submission id. \n",
    )
    return parser.parse_args()


def main():
    args = get_args()
    is_production = True
    submission_id = args.submission_id
    logging.getLogger().setLevel(logging.INFO)

    try:
        meta_structure = metastructure.MetaStructure(is_production)
    except metastructure.StructureError as structure_error:
        sys.exit(structure_error)

    # meta_structure = submission_oo.MetaStructure.start_metastructure(is_production, ALL_CATEGORIES, SCHEMA_STRING, RELATIONSHIP_STRING, VERSION_STRING)
    version_dict = meta_structure.version
    version = version_dict['current']
    db_poster = poster.Poster('', '', '', is_production, meta_structure)
    reader = sheetreader.SheetReader(meta_structure)

    workbook = xlsxwriter.Workbook(submission_id + '.xlsx')  # The submission should be extracted, replace url
    reader.write_book_header(workbook)
    # with open(args.cypher, 'r') as file:
    #     cypher_json = json.load(file)
    # book_data = db_poster.read_cypher(cypher_json, 'Assay')
    book_data = db_poster.fetch_file_info(submission_id)
    reader.write_book(workbook, book_data)
    workbook.close()



if __name__ == "__main__":
    main()
