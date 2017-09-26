import sys
import xlrd
from collections import OrderedDict
import requests
import urllib.request
import urllib.error
import json
import argparse
import logging
import uuid  # used to generate unique user accesion if it is not provided.
import pprint
from socket import timeout
import ipdb

URL_META = 'http://target.wustl.edu:7006'
URL_SUBMIT = 'http://target.wustl.edu:7002'
TESTURL_META = 'http://target.wustl.edu:8006'
TESTURL_SUBMIT = 'http://target.wustl.edu:8002'
VERSIONURL = URL_META + '/api/version'

# The ctype represents in xlrd package parsering excel file:
CTYPE_NUMBER = 2
CTYPE_DATE = 3
CTYPE_BOOLEAN = 4

# The database json name : excel worksheet name correlation:
ALL_CATEGORIES = {"assay": "Assay",
                  "bioproject": "Bioproject",
                  "biosample": "Biosample",
                  "diet": "Diet",
                  "experiment": "Experiment",
                  "file": "File",
                  "lab": "Lab",
                  "library": "Library",
                  "litter": "Litter",
                  "mouse": "Mouse",
                  "reagent": "Reagent",
                  "treatment": "Treatment",
                  "mergedFile": "Mergedfile"
                  }


class StructureBuilder:
    def __init__(self, url, categories):
        self.url = url
        self.categories = categories  # it is a dictionary
        self.schema = self._url_to_json('/schema/')
        self.links = self._url_to_json('/schema/relationships/')

        """
        There are two links in "Assay" named "assay_input", one points to biosample and the other points to library.
        I have to change them to "assay_input_biosample" and "assay_input_library" before useing them as key in my new dict.
        
        name example:
        sheet: "File"
        category: "file"
        categories: "files"
        """
        for x in self.links["Assay"]["connections"]:
            if x['display_name'] == "Biosample":
                x['name'] = 'assay_input_biosample'
            if x['display_name'] == "Library":
                x['name'] = 'assay_input_library'
        self.linkto = self.build_dict("linkto")
        self.contain_links
        self.build_linkto
        self.build_contain_links

    def _url_to_json(self, string):
        new_dict = {}
        for db_category, sheet in self.categories.items():
            json_url = self.url + string + db_category + '.json'
            data = requests.get(json_url).json()["data"]  # data is a list for schema, but data is a dict for links. within links: data['connections'] is a list.
            new_dict[sheet] = data
        return new_dict

    def get_categories(self, category):  # input is category name (file), return categories name (files)
        sheet = self.categories[category]
        return self.links[sheet]["all"]

    def get_linkto(self, sheet, link_field):  # from sheet name and link_filed name get which sheet it links to. For example: get_linkto("Bioproject", "work_on") returns "Lab"
        get_list = [x["display_name"] for x in self.links[sheet]["connections"] if x["name"] == link_field]
        return get_list[0]

    def get_link_field(self, link_from, link_to):  # from which sheet link from and which sheet it links to and get the link_field. For example: get_link_field("Bioproject", "Lab") returns "work_on"
        get_list = [x["name"] for x in self.links[link_from]["connections"] if x["display_name"] == link_to]
        return get_list[0]

    def get_all_fields(self, sheet):  # from sheet name get all fields from schema and linkto.
        pass

    def get_accession_rule(self, sheet)
        pass

    def get_column_name(self, sheet, column_displayname)
        pass

    def get_data_type(self, sheet, column_displayname)
        pass

class ExcelParser:

    def __init__(self, metadata_structure, mode):
        self.metadata_structure = metadata_structure
        self.mode = mode  # TRUE if it is update, FALSE if it is submission.

    def read(self, file):
        wb = xlrd.open_workbook(file)
        sheet_names = wb.sheet_names()
        all_sheets = OrderedDict()
        data_structure = self.metadata_structure
        for sheet in sheet_names:
            if sheet not in data_structure.schema.keys():  # skip "Instructions" and "Lists"
                continue
            sheet_obj = wb.sheet_by_name(sheet)
            columns = [str(sheet_obj.cell(1, col_index).value).rstrip() for col_index in range(sheet_obj.ncols)]  # start from row number 1 to skip header
            dict_list = []
            all_database_fields = data_structure.get_all_fields(sheet)
            for database_field in all_database_fields:
                if database_field not in columns:
                    # logging.warning("warning! column %s is missing in %s. Please update your excel file to the latest version." % (database_field, Sheet))
                    print("version change history:")
                    pp = pprint.PrettyPrinter(indent=2)
                    pp.pprint(versionNo)
                    logging.warning("warning! column %s is missing in %s. Please update your excel file to the latest version." % (database_field, Sheet))
            accession_rule = data_structure.get_accession_rule(sheet)
            for row_index in range(2, sheet_obj.nrows):
                row_data = OrderedDict()
                for col_index in range(sheet_obj.ncols):
                    column_displayname = columns[col_index]
                    column_name = data_structure.get_column_name(sheet, column_displayname)
                    data_type = data_structure.get_data_type(sheet, column_displayname)
                    value = sheet_obj.cell(row_index, col_index).value
                    ctype = sheet_obj.cell(row_index, col_index).ctype
                    value = _process_value(value, column_displayname)
                    row_data[column_name] = value  # or use columan display name? 

                if _filter_by_accession():
                    dict_list.append(row_data)

                    all_sheets[sheet] = dict_list

        # Validate with schema if desired
        # Return something Uploader can understand.  It can be a simple dict, or if it gets complicated enough, make a
        # new Metadata class and return an instance of that.
        return all_sheets

        def _process_value(value, column_displayname)
            pass

        def _filter_by_accession()
            pass

class AccessionEnforcer:
    def __init__(self, schema_source):
            self.schema_source = schema_source

    def duplication_check(self):
        pass

    def sys_acc_assign(self):
        pass


class Uploader:
    def __init__(self, schema_source):
        self.schema_source = schema_source

    def upload(self, source):
        pass


def get_args():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        '--excel',
        '-x',
        action="store",
        dest="excel",
        required=True,
        help='The excel used for bulk upload. Required.\n',
    )
    parser.add_argument(
        '--notest',
        '-n',
        action="store_true",
        dest="notest",
        help='test flag. default option is true, which will submit all the metadata to the test database. \
        The metadata only goes to the production database if this option is false. Our recommended practice is use \
        TRUE flag (default) here first to test the integrity of metadata, only switch to FALSE once all the \
        metadata successfully submitted to test database.\n',
    )
    parser.add_argument(
        '--testlink',
        '-l',
        action="store_true",
        dest="testlink",
        help='test flag. if true, test DEV1 links connections\n',
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
        dest="mode",
        help="Run mode. Without the flag (default), only records without systerm accession and without \
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

    if args.token:
        bearer_token = 'bearer ' + args.token
        token_url = TESTURL_SUBMIT + '/api/usertoken/' + args.token
        # user_name_dict = request(token_url)
        user_name = requests.get(token_url).json()["username"]
    else:
        logging.error("please provide a user API key!")
        sys.exit("please provide a user API key!")  # make token argument mandatory.

    if args.notest:
        action_url_meta = URL_META
        action_url_submit = URL_SUBMIT
    else:
        action_url_meta = TESTURL_META
        action_url_submit = TESTURL_SUBMIT

    meta_data_structure = StructureBuilder(action_url_meta, ALL_CATEGORIES)
    ipdb.set_trace()
    reader = ExcelParser(meta_data_structure, args.mode)
    submission_dict = reader.read(args.excel)
    AccessionEnforcer.duplication_check(submission_dict)
    AccessionEnforcer.sys_acc_assign(submission_dict)
    Uploader.upload(submission_dict)


if __name__ == '__main__':
    main()
