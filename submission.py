import sys
import xlrd
import json
import argparse
import logging
import unittest

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
        '--isproduction',
        action="store_true",
        dest="isproduction",
        help="test flag. default option is true, which will submit all the metadata to the test database. \
        The metadata only goes to the production database if this option is false. Our recommended practice is use \
        TRUE flag (default) here first to test the integrity of metadata, only switch to FALSE once all the \
        metadata successfully submitted to test database.\n",
    )
    parser.add_argument(
        '--notest',
        '-n',
        action="store_true",
        dest="isproduction",
        help="test flag. Without the flag it will submit all the metadata to the test database. \
        The metadata only goes to the production database if this option is TRUE. Our recommended practice is use \
        FALSE flag (default) here first to test the integrity of metadata, only switch to TRUE once all the \
        metadata successfully submitted to dev1 database.\n",
    )
    parser.add_argument(
        '--testlink',
        '-l',
        action="store_true",
        dest="testlink",
        help="test flag. if true, test DEV1 links connections\n",
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
        # Now upload all the records on sheet_data:
    if validation:
        for sheet_name, sheet_data in book_data.data.items():
            for record in sheet_data.all_records:
                db_poster.submit_record(record)  # submit/update the record, track which record has been submitted or updated, and assign system accession to the submitted record.

        if is_production or args.testlink:
            book_data.swipe_accession()
            for sheet_name, sheet_data in book_data.data.items():
                for record in sheet_data.all_records:
                    db_poster.link_record(record)  # submit/update the record link.
            db_poster.save_submission(book_data)


class SubmissionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        print("setUpClass runs before ALL tests")
        meta_structure = metastructure.MetaStructure()
        # meta_structure.isupdate(args.isupdate)
        # meta_structure.isproduction(args.isproduction)
        # These options no longer saved in meta_structure

        cls.reader = sheetreader.SheetReader(meta_structure)

        cls.test_book = xlrd.open_workbook("test/test_sheet.xlsx")
        # cls.test_book = BookData(meta_structure)

    def setUp(self):
        print("setUp runs before EACH test")

    def test_read_sheet(self):
        sheet_obj = self.test_book.sheet_by_name("Litter")
        self.reader.verify_column_names(sheet_obj)
        sheet_data = self.reader.read_sheet(sheet_obj, self.test_book.datemode)
        test_sheet_list = []
        for record_object in sheet_data.all_records:
            record_dict = record_object.__dict__
            record_dict.pop("meta_structure")
            test_sheet_list.append(record_dict)
        with open('test/sheet_reader.json') as data_file:
            expected_sheet_list = json.load(data_file)
            self.assertEqual(expected_sheet_list, test_sheet_list)

    # def test_duplication_check(self):
    #     pass
    #     # self.assertEqual(result, expected)

    def tearDown(self):
        print("tearDown runs after EACH test")

    @classmethod
    def tearDownClass(cls):
        print("tearDownClass runs after ALL tests")


if __name__ == "__main__":
    main()
