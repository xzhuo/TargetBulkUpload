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
NUMBER_ZEROS = 3

# The ctype represents in xlrd package parsering excel file:
CTYPE_NUMBER = 2
CTYPE_DATE = 3
CTYPE_BOOLEAN = 4
EXCEL_HEADER_ROW = 1
EXCEL_DATA_START_ROW = EXCEL_HEADER_ROW + 1
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


class DatabaseStructure:
    def __init__(self, url, categories):
        self.url = url
        self.categories = categories  # it is a dictionary
        self.schema_dict = self._url_to_json('/schema/')
        self.link_dict = self._url_to_json('/schema/relationships/')
        self.version = self.get_version('/api/version')

        """
        There are two links in "Assay" named "assay_input", one points to biosample and the other points to library.
        I have to change them to "assay_input_biosample" and "assay_input_library" before useing them as key in my new dict.
        
        name example:
        sheet: "File"
        category: "file"
        categories: "files"
        """



        # for x in self.link_dict["Assay"]["connections"]:
        #     if x['display_name'] == "Biosample":
        #         x['name'] = 'assay_input_biosample'
        #     if x['display_name'] == "Library":
        #         x['name'] = 'assay_input_library'
        # self.linkto = self.build_dict("linkto")
        # self.contain_links
        # self.build_linkto
        # self.build_contain_links

    def _url_to_json(self, string):
        new_dict = {}
        for db_category, sheet in self.categories.items():
            json_url = self.url + string + db_category + '.json'
            data = requests.get(json_url).json()["data"]  # data is a list for schema, but data is a dict for links. within links: data['connections'] is a list.
            new_dict[sheet] = data
        return new_dict

    def get_version(self, version_string):
        full_url = self.url + version_string
        return requests.get(full_url).json()


class SheetStructure:
    def __init__(self, structure_obj, sheet):
        self.name = sheet
        schema = structure_obj.schema_dict[sheet]  # schema is a list
        link = structure_obj.link_dict[sheet]  # link is a dictionary, link["connections"] is a list.
        self.schema = schema
        self.link = link
        self.categories = link["all"]
        self.category = link["one"]
        # self.user_accession_rule = link["usr_prefix"][:-NUMBER_ZEROS]
        self.user_accession_rule = [x["placeholder"] for x in schema if x["text"] == "User accession"][0][:-4]
        self.system_accession_rule = link["prefix"][:-NUMBER_ZEROS]
        self.schema_columns = [x["text"] for x in schema]
        self.link_columns = [x["display_name"] for x in link["connections"]]
        self.all_columns = self.schema_columns + self.link_columns
        self.version = structure_obj.version

    def get_column_name(self, column_displayname):
        if column_displayname in self.schema_columns:
            column_name = [x["name"] for x in self.schema if x["text"] == column_displayname]
        elif column_displayname in self.link_columns:
            column_name = [x["name"] for x in self.link["connections"] if x["display_name"] == column_displayname]
        if len(column_name) != 1:
            sys.exit("invalid column name in %s. There has to be 1 and only 1 %s" % (self.name, column_displayname))
        else:
            return column_name[0]

    def get_data_type(self, column_displayname):
        if column_displayname in self.schema_columns:
            data_type = [x["type"] for x in self.schema if x["text"] == column_displayname]
        elif column_displayname in self.link_columns:
            data_type = ["text"]
        return data_type[0]

    def get_islink(self, column_displayname):
        if column_displayname in self.link_columns:
            return_value = 1
        else:
            return_value = 0
        return return_value

    def verify_column_names(self, column_names):
        all_database_fields = self.all_columns
        # compare two lists: all_data_fields and column_names
        for database_field in all_database_fields:
            if database_field not in column_names:
                # logging.warning("warning! column %s is missing in %s. Please update your excel file to the latest version." % (database_field, Sheet))
                print("version change history:")
                pp = pprint.PrettyPrinter(indent=2)
                version_number = self.get_version()
                pp.pprint(version_number)
                logging.warning("warning! column %s is missing in %s. Please update your excel file to the latest version." % (database_field, self.name))


class RowData:
    def __init__(self, sheet_structure):
        self.value = OrderedDict()
        self.relationships = dict()
        self.structure = sheet_structure
        self.sheet = sheet_structure.name

    def add(self, display_name, value):
        if self.structure.get_islink(display_name):
            # do link stuff
            self.relationships[display_name] = value
        else:
            self.value[display_name] = value

    def filter_by_accession(self, isupdate):
        user_accession_rule = self.structure.user_accession_rule
        system_accession_rule = self.structure.system_accession_rule
        if "User accession" in self.value:
            user_accession = self.value["User accession"]
        else:
            user_accession = ''
        if "System Accession" in self.value:
            system_accession = self.value["System Accession"]
        else:
            system_accession = ''
        if isupdate:
            if user_accession.startswith(user_accession_rule) or system_accession.startswith(system_accession_rule):
                return 1
            else:
                logging.warning("All records in %s without a valid system accession or user accession will be skipped during update!" % self.sheet)
                return 0
        else:
            if system_accession != '':
                logging.info("Skip %s in %s" % (system_accession, self.sheet))
            elif user_accession.startswith(user_accession_rule):
                return 1
            else:
                logging.error("Please provide valid User accessions in %s! It should start with %s" % (self.sheet, user_accession_rule))


    def get_all_dict(self):  # return a dictionary with all the data in Row_data obj
        pass

    def get_schema_dict(self):  # return a dictionary with pure value (not links) in Row_data obj
        pass

    def get_link_dict(self):  # return a dictionary with all the links in Row data pbj
        pass


class Metadata:
    def __init__(self, data_structure, isupdate):
        self.structure = data_structure  # input is a database_structure_obj
        self.isupdate = isupdate
        self.all_rows = []

    def read_file(self, file):  # read excel file.
        workbook = xlrd.open_workbook(file)
        sheet_names = workbook.sheet_names()
        data_structure_obj = self.structure
        for sheet in sheet_names:
            if sheet not in data_structure_obj.schema_dict.keys():  # skip "Instructions" and "Lists"
                continue
            sheet_obj = workbook.sheet_by_name(sheet)
            sheet_structure = SheetStructure(data_structure_obj, sheet)
            column_names = [str(sheet_obj.cell(EXCEL_HEADER_ROW, col_index).value).rstrip() for col_index in range(sheet_obj.ncols)]  # start from row number 1 to skip header

            sheet_structure.verify_column_names(column_names)
            for row_index in range(EXCEL_DATA_START_ROW, sheet_obj.nrows):
                row_obj = RowData(sheet_structure)
                for col_index in range(sheet_obj.ncols):
                    column_displayname = column_names[col_index]

                    # column_name = SheetStructure.get_column_name(column_displayname)
                    # data_type = SheetStructure.get_data_type(column_displayname)
                    # islink = SheetStructure.get_islink(column_displayname)
                    value = sheet_obj.cell(row_index, col_index).value
                    ctype = sheet_obj.cell(row_index, col_index).ctype
                    value = self._process_value(value, ctype, column_displayname)
                    row_obj.add(column_displayname, value)  # or use columan display name?

                if row_obj.filter_by_accession(self.isupdate):
                    self.add_row(row_obj)

    def _process_value(self, value, ctype, column_displayname):
        pass

    def add_row(self, row_obj):  # add row data obj to the metadata obj.
        self.all_rows.append(row_obj)


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
        dest="isupdate",
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

    data_structure_obj = DatabaseStructure(action_url_meta, ALL_CATEGORIES)
    metadata_obj = Metadata(data_structure_obj, args.isupdate)
    metadata_obj.read_file(args.excel)
    ipdb.set_trace()
    metadata_obj.duplication_check()
    metadata_obj.sys_acc_assign()
    for row_obj in metadata_obj.all_rows:
        # upload here...
        pass
    for row_obj in metadata_obj.all_rows:
        # upload here...
        pass


if __name__ == '__main__':
    main()
