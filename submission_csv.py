import requests
from neo4j.v1 import GraphDatabase
import pandas as pd
import argparse
import xlrd
import json
import logging
import sys

import metastructure
import sheetreader
import poster
import validator
import bookdata


def get_args():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        '--excel',
        '-x',
        action="store",
        dest="excel",
        required=True,
        help="The excel used for bulk upload. Required.\n",
    )
    parser.add_argument(
        '--password',
        '-p',
        action="store",
        dest="password",
        required=True,
        help="The password of neo4j database. Required.\n",
    )
    parser.add_argument(
        '--isproduction',
        action="store_true",
        dest="isproduction",
        help="test flag. default option is true, which will submit all the metadata to the test database. \
        The metadata only goes to the production database if this option is false. Our recommended practice is use \
        TRUE flag (default) here first to test the integrity of metadata, only switch to FALSE once all the \
        metadata successfully submitted to test database.\n",
    )
    parser.add_argument(
        '--tokenkey',
        '-k',
        action="store",
        dest="token",
        required=True,
        help="User's API key. Required.\n",
    )
    parser.add_argument(
        '--update',
        '-u',
        action="store_true",
        dest="isupdate",
        help="Run mode. Without the flag (default), only records without system accession and without \
        matching user accession with be posted to the database. All the records with system accession in the \
        excel with be ignored. For records without system accession but have user accessions, the user accession \
        will be compared with all records in the database. If a matching user accession found in the database, the \
        record will be ignored. If the '--update' flag is on, it will update records in the database match the given \
        system accession (only update filled columns). it will complain with an error if no matching system \
        accession is found in the database.\n"
    )
    parser.add_argument(
        '--debug',
        '-d',
        action="store_true",
        dest="debug",
        help="debug or not. with the flag the script will run as debug mode.\n"
    )
    return parser.parse_args()

# Functions I need to code for this:
# Create new system accession, user, date_created and date_modified properties for each node;
# Incremental change uniqId nodes;
# Create relationships using (user and user_accession) or system accession;
# Create multiple relationships using comma delimited list;
# Accession validation?
# modify date_modified on update query;
# delete relationships;
# create new relationships.


def main():
    args = get_args()
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    else:
        logging.getLogger().setLevel(logging.INFO)  # using INFO as default output information level.
        logging.getLogger("requests").setLevel(logging.WARNING)

    if not args.token:
        logging.error("please provide a user API key!")
        sys.exit("please provide a user API key!")  # make token argument mandatory.

    is_production = args.isproduction
    is_update = args.isupdate
    try:
        meta_structure = metastructure.MetaStructure(is_production)
    except metastructure.StructureError as structure_error:
        logging.error(structure_error)
    # meta_structure.isupdate(args.isupdate)
    # meta_structure.isproduction(args.isproduction)
    # These options no longer saved in meta_structure

    reader = sheetreader.SheetReader(meta_structure)
    db_poster = poster.Poster(args.token, '', is_update, is_production, meta_structure)

    workbook = xlrd.open_workbook(args.excel)
    book_data = bookdata.BookData(meta_structure)
    sheet_names = workbook.sheet_names()
    validation = True
    for sheet_name in sheet_names:
        if sheet_name not in meta_structure.schema_dict.keys():  # skip "Instructions" and "Lists"
            continue
        sheet_obj = workbook.sheet_by_name(sheet_name)
        data_validator = validator.Validator(meta_structure)

        data_validator.verify_column_names(sheet_obj)
        sheet_data, row_validation = reader.read_sheet(sheet_obj, workbook.datemode)
        if not row_validation:
            validation = False
        try:
            data_validator.duplication_check(db_poster, sheet_data)
            book_data.add_sheet(sheet_data)
        except validator.ValidatorError as validator_error:
            logging.error(validator_error)
            validation = False
        except TypeError as type_error:
            logging.error(type_error)
            validation = False
    if validation:
        print("successfully validated exported all the data in the excel file to csv files!")
        reader.write_csv(book_data)


    # sheet_names = workbook.sheet_names()

    #     url = "bolt://10.20.127.31:6687" if is_production else "bolt://10.20.127.31:8687"
    #     driver = GraphDatabase.driver(url, auth=("neo4j", args.password))
    #     # reader = sheetreader.SheetReader(meta_structure)
    #     # db_poster = poster.Poster(args.token, '', is_update, is_production, meta_structure)

    #     data_xls = pd.read_excel(args.excel, None, index_col=None, skiprows=[0])
    #     for key in data_xls:
    #         csv = key + "_test.csv"
    #         data_xls[key].to_csv(csv, index=False, encoding='utf-8')
    #         url = 'https://wangftp.wustl.edu/~xzhuo/target/' + csv
    #         statement = "LOAD CSV WITH HEADERS FROM '{csv}' AS line " \
    #                     "MERGE (pilot:file {{ md5sum: line.md5sum }}) " \
    #                     "ON CREATE SET {json} " \
    #                     "ON MATCH SET {json}".format(csv=url, json=set_string)
    #         with driver.session() as session:
    #             with session.begin_transaction() as tx:
    #                 tx.run(statement)


if __name__ == "__main__":
    main()