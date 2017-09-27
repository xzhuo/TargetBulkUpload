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


class FileData:
    def __init__(self, url, categories):
        self.url = url
        self.categories = categories  # it is a dictionary
        self.schema_dict = self._url_to_json('/schema/')
        self.link_dict = self._url_to_json('/schema/relationships/')
        self.version = self.get_version('/api/version')
        self.data = []
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

    def isupdate(self, isupdate):
        self.isupdate = isupdate

    def notest(self, notest):
        self.notest = notest

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

    def read_file(self, file):  # read excel file.
        """
        This method does a lot:
        1. Read the excel file.
        2. Compare the column names to database fields for each sheet.
        3. For each cell in excel file, massage value in excel to fit database datatype.
        4. After processing each row, only append it if the accession is valid.
        5. After processing each sheet, query database to make sure all there is no accession conflict within the sheet and with existing records.
        """
        workbook = xlrd.open_workbook(file)
        sheet_names = workbook.sheet_names()
        for sheet in sheet_names:
            if sheet not in self.schema_dict.keys():  # skip "Instructions" and "Lists"
                continue
            sheet_obj = workbook.sheet_by_name(sheet)
            column_names = [str(sheet_obj.cell(EXCEL_HEADER_ROW, col_index).value).rstrip() for col_index in range(sheet_obj.ncols)]  # start from row number 1 to skip header

            sheet_data = SheetData(self, sheet)
            sheet_data.verify_column_names(column_names)
            for row_index in range(EXCEL_DATA_START_ROW, sheet_obj.nrows):
                row_obj = RowData(sheet_data)
                for col_index in range(sheet_obj.ncols):
                    column_displayname = column_names[col_index]

                    # column_name = SheetData.get_column_name(column_displayname)
                    # data_type = SheetData.get_data_type(column_displayname)
                    # islink = SheetData.islink(column_displayname)
                    value = sheet_obj.cell(row_index, col_index).value
                    ctype = sheet_obj.cell(row_index, col_index).ctype
                    value = sheet_data.process_value(value, ctype, column_displayname, workbook.datemode)
                    row_obj.add(column_displayname, value)  # or use columan display name?

                if row_obj.filter_by_accession(self.isupdate):
                    sheet_data.add_record(row_obj)
            sheet_data.duplication_check(self.isupdate, self.notest)
            self.data.append(sheet_data)


class SheetData:
    def __init__(self, file_data, sheet):
        self.name = sheet
        self.sheeturl = file_data.url + '/api/' + sheet
        schema = file_data.schema_dict[sheet]  # schema is a list
        link = file_data.link_dict[sheet]  # link is a dictionary, link["connections"] is a list.
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
        self.version = file_data.version
        self.all_recrods = []

    # def get_column_name(self, column_displayname):
    #     if column_displayname in self.schema_columns:
    #         column_name = [x["name"] for x in self.schema if x["text"] == column_displayname]
    #     elif column_displayname in self.link_columns:
    #         column_name = [x["name"] for x in self.link["connections"] if x["display_name"] == column_displayname]
    #     if len(column_name) != 1:
    #         sys.exit("invalid column name in %s. There has to be 1 and only 1 %s" % (self.name, column_displayname))
    #     else:
    #         return column_name[0]

    def get_data_type(self, column_displayname):
        if column_displayname == "zip_code" or column_displayname == "batchId" or column_displayname == "System Accession":
            data_type = "text"
        elif column_displayname in self.schema_columns:
            data_type_list = [x["type"] for x in self.schema if x["text"] == column_displayname]
            data_type = data_type_list[0]
        elif column_displayname in self.link_columns:
            data_type = "text"
        return data_type

    def islink(self, column_displayname):
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

    def process_value(self, value, ctype, column_displayname, datemode):
        data_type = self.get_data_type(column_displayname)
        if column_displayname == "User accession" and (value == "NA" or value == ''):  # always us "NA" if user accession is empty
            value == "NA"
        elif ctype == CTYPE_BOOLEAN:
            if value:
                value = "TRUE"
            else:
                value = "FALSE"
        # now consider data_type:
        elif data_type == "text" and ctype == 2:
            value = str(value).rstrip('0').rstrip('.')  # delete trailing 0s if it is a number.
        elif data_type == "date":
            if value == "NA":
                value = '1970-01-01'
            elif ctype == CTYPE_DATE:
                value = xlrd.xldate.xldate_as_datetime(value, datemode).date().isoformat()
        elif data_type == "float":
            if ctype == CTYPE_NUMBER:
                value = round(value, 2)
            else:
                sys.exit("please use number for %s in %s" % (column_displayname, self.name))
        elif data_type == "number" and value == 'NA':  # assign number field to -1 if it is NA in the excel.
            value = -1
            logging.info("Change NA to -1 for %s in %s." % (column_displayname, self.name))

        return value

    def add_record(self, row_obj):  # add row data obj to the metadata obj.
        self.all_records.append(row_obj)

    def fetch_all(self, categories):
        get_url = url + '/api/' + categories
        request = requests.get(get_url)
        return request.json()[categories]  # returns a list of existing records.

    def duplication_check(self, isupdate, notest):
        sheeturl = self.sheeturl
        if isupdate:
            existing_sheet_data = self.get(sheeturl)
            existing_records
        for record in self.all_recrods:


class RecordObject:
    def __init__(self):
        self.schema = dict()
        self.relationships = dict()

    def get_sheet(sheet):
        self.sheet = sheet

    def add(self, column_displayname, value):
        column_name = structure.get_column_name(self.sheet, column_displayname)
        if self.sheet.islink(column_displayname):
            # do link stuff
            accession_list = value.split(",")  # split value in cell by ",""
            linkto = structure.get_linkto(self.sheet, column_displayname)
            if column_name in self.relationships:
                self.relationships[column_name][linkto] = accession_list
            else:
                self.relationships[column_name] = {linkto: accession_list}
        else:
            self.schema[column_name] = value

    def get_token(self, token):
        self.token = {"Authorization": bearer_token}

    def fetch_record(self, url, category, categories, system_accession):
        self.sheet = 
        get_url = url + '/api/' + categories + '/' + system_accession
        main_obj = requests.get(get_url).json()["mainObj"][category]
        self.schema = main_obj[category]
        self.relationships = main_obj[added]

    def submit_record(self, url, category, categories, system_accession):
        post_url = url + '/api/' + categories + '/' + system_accession
        post_body = self.schema
        request = requests.post(post_url, headers=self.token, data=post_body)

    def link_all(self):
        system_accession = self.schema["accession"]
        for column_name in self.relationships:
            for linkto_category in self.relationships[column_name]:
                accession_list = self.relationships[column_name][linkto_category]
                if len(accession_list) > 0:
                    for linkto_accession in accession_list:
                        link_add(url, category, categories, system_accession， linkto_category, linkto_accession, "add")

    def link_add(self, url, category, categories, system_accession， linkto_category, linkto_accession, connection_name, direction):
        linkurl = url + '/api/' + categories + '/' + system_accession + '/' + linkto_category + '/' + direction  # direction should be add or remove
        link_body = {"connectionAcsn": linkto_accession, "connectionName": connection_name}
        request = requests.post(linkurl, headers=self.token, data=link_body)

    def filter_by_accession(self, isupdate):
        """
        fileter TRUE or FALSE based on user accession and system accession of the record.
        During update, return TRUE if at least one of user accession or system accession exists and start with accession rule.
        During submission of new record, return TRUE if system accession does not exist and user accession start with accession rule.

        """
        user_accession_rule = self.sheet.user_accession_rule
        system_accession_rule = self.sheet.system_accession_rule
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
                logging.warning("All records in %s without a valid system accession or user accession will be skipped during update!" % self.sheet.name)
                return 0
        else:
            if system_accession != '':
                logging.info("Skip %s in %s" % (system_accession, self.sheet.name))
                return 0
            elif user_accession.startswith(user_accession_rule):
                return 1
            else:
                sys.exit("Please provide valid User accessions in %s! It should start with %s" % (self.sheet.name, user_accession_rule))


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

    metadata_obj = FileData(action_url_meta, ALL_CATEGORIES)
    metadata_obj.isupdate(args.isupdate)
    metadata_obj.notest(args.notest)
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
