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

URL_META = 'http://target.wustl.edu:7006'
URL_SUBMIT = 'http://target.wustl.edu:7002'
TESTURL_META = 'http://target.wustl.edu:8006'
TESTURL_SUBMIT = 'http://target.wustl.edu:8002'
VERSIONURL = URL_META + '/api/version'

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
        self.schema = self.url_to_json('/schema/')
        self.links = self.url_to_json('/schema/relationships/')

        """
        There are two links in "Assay" named "assay_input", one points to biosample and the other points to library.
        I have to change them to "assay_input_biosample" and "assay_input_library" before useing them as key in my new dict.
        """
        for x in self.links["Assay"]["connections"]:
            if x['display_name'] == "Biosample":
                x['name'] = 'assay_input_biosample'
            if x['display_name'] == "Library":
                x['name'] = 'assay_input_library'

        self.category_to_categories = self.build_dict("category_to_categories")
        self.linkto = self.build_dict("linkto")
        self.contain_links
        self.build_linkto
        self.build_contain_links

    def build_dict(self, type):
        new_dict = {}
        if type == "category_to_categories":
            for db_json, sheet in self.categories.items():
                new_dict[sheet] = self.schema[db_json]["all"]
        if type == "linkto":
            pass
        return new_dict

    def url_to_json(self, string):
        schema = {}
        for db_json, sheet in self.categories.items():
            json_url = self.url + string + db_json + '.json'
            data = requests.get(json_url).json()["data"]  # data is a list for schema, but data is a dict for links. within links: data['connections'] is a list.
            schema[sheet] = data
        return schema

    def get_categories(self, category):  # input is category name (file), return categories name (files)
        pass

    def get_linkto(self, link):  # input is relationship name, return linkto category.
        pass

    def get_link(self, category):  # input is category name, return relationship name
        pass


class ExcelParser:
    def __init__(self, meta_data_structure):
        self.meta_data_structure = meta_data_structure

    def read(self, sheet):
        category_name = sheet.name
        schema = self.schema_source.get_schema_for_category(category_name)
        # Validate with schema if desired
        # Return something Uploader can understand.  It can be a simple dict, or if it gets complicated enough, make a
        # new Metadata class and return an instance of that.
        return {}


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
    reader = ExcelParser(meta_data_structure, args.mode)
    submission_dict = reader.read(args.excel)
    AccessionEnforcer.duplication_check(submission_dict)
    AccessionEnforcer.sys_acc_assign(submission_dict)
    Uploader.upload(submission_dict)

