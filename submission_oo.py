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
SCHEMASTRING = '/schema/'
RELATIONSHIPSTRING = '/schema/relationships/'
VERSIONSTRING = '/api/version'
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


class MetaStucture:
    def __init__(self, url, categories):
        self.url = url
        self.categories = categories  # it is a dictionary
        self.schema_dict = self._url_to_json(SCHEMASTRING)  # key is sheet name instead of category name.
        for category in self.schema_dict:
            self.schema_dict[category].append({"name": "accession", "text": "System Accession", "type": "text"})
        self.link_dict = self._url_to_json(RELATIONSHIPSTRING)  # key is sheet name instead of category name.
        self.version = self._set_version(VERSIONSTRING)

    def get_sheet_url(self, sheet_name):
        pass

    def get_category(self, sheet_name):
        """
        input: excel worksheet name.
        output: correspondance category name.
        """
        category_dict = self.categories
        category_list = [k for k, v in category_dict.items() if v == sheet_name]
        try:
            return_category = category_list[0]
        except:
            logging.error("wrong sheet name %s?" % sheet_name)
        return category_list[0]

    def get_categories(self, category):
        return self.link["all"]

    def get_schema(self, sheet_name):
        category = self.get_category(sheet_name)
        return self.schema_dict[category]  # schema is a list

    def get_link(self, sheet_name):
        category = self.get_category(sheet_name)
        return self.link_dict[category]  # link is a dictionary, link["connections"] is a list.

    def get_user_accession_rule(self, sheet_name):
        link = self.get_link(sheet_name)
        return link["usr_prefix"][:-NUMBER_ZEROS]

        # alternative solution:
        # schema = self.get_schema(sheet_name)
        # return [x["placeholder"] for x in schema if x["text"] == "User accession"][0][:-4]

    def get_system_accession_rule(self, sheet_name):
        link = self.get_link(sheet_name)
        return link["prefix"][:-NUMBER_ZEROS]

    def get_schema_column_displaynames(self, sheet_name):  # get a list of all column names
        schema = get_schema(sheet_name)
        return [x["text"] for x in schema]

    def get_link_column_displaynames(self, sheet_name):  # get a list of all column names
        link = self.get_link(sheet_name)
        return [x["display_name"] for x in link["connections"]]

    def get_all_column_displaynames(self, sheet_name):
        return self.get_schema_column_displaynames(sheet_name) + self.get_link_column_displaynames(sheet_name)

    def get_data_type(self, sheet_name, column_displayname):
        if column_displayname in self.get_schema_column_displaynames(sheet_name):
            data_type_list = [x["type"] for x in self.get_schema(sheet_name) if x["text"] == column_displayname]
            data_type = data_type_list[0]
        elif column_displayname in self.get_link_column_displaynames(sheet_name):
            data_type = "text"
        return data_type

    def islink(self, sheet_name, column_displayname):
        if column_displayname in self.get_link_column_displaynames(sheet_name):
            return_value = 1
        else:
            return_value = 0
        return return_value

    def _url_to_json(self, string):
        new_dict = {}
        for category in self.categories.keys():
            json_url = self.url + string + category + '.json'
            data = requests.get(json_url).json()["data"]  # data is a list for schema, but data is a dict for links. within links: data['connections'] is a list.
            new_dict[category] = data
        return new_dict

    def _set_version(self, version_string):
        full_url = self.url + version_string
        return requests.get(full_url).json()


class SheetReader:
    def __init__(self, meta_strcture):
        self.meta_strcture = meta_strcture

    def get_all_columan_displaynames(sheet_obj):
        return [str(sheet_obj.cell(EXCEL_HEADER_ROW, col_index).value).rstrip() for col_index in range(sheet_obj.ncols)]  # start from row number 1 to skip header

    def read_sheet(self, sheet_obj, datemode, isupdate):  # read excel file.
        """
        input is a xlrd worksheet obj,
        returns a SheetData obj.
        """
        column_displaynames = get_all_columan_displaynames(sheet_obj)
        sheet_data = SheetData(meta_strcture, sheet_obj.name)
        for row_index in range(EXCEL_DATA_START_ROW, sheet_obj.nrows):
            row_obj = sheet_data.new_row()
            for col_index in range(sheet_obj.ncols):
                column_displayname = column_displaynames[col_index]

                # column_name = SheetData.get_column_name(column_displayname)
                # data_type = SheetData.get_data_type(column_displayname)
                # islink = SheetData.islink(column_displayname)
                value = sheet_obj.cell(row_index, col_index).value
                ctype = sheet_obj.cell(row_index, col_index).ctype
                value = process_value(value, ctype, column_displayname, self.datemode)
                row_obj.add(column_displayname, value)  # or use columan display name?

            if filter_by_accession(row_obj, isupdate):
                sheet_data.add_record(row_obj)
        return sheet_data

    def verify_column_names(self, sheet_obj):
        """
        compare all the columns names in the worksheet with correspondence databases fields.
        pop up a warning if there is any missing column.
        and also give a warning if any column will be skipped.
        """
        sheet_name = sheet_obj.name
        column_displaynames = set(get_all_columan_displaynames(sheet_obj))
        all_database_fields = set(self.meta_strcture.get_all_column_displaynames(sheet_obj.name))
        missing_columns = all_database_fields - column_displaynames
        unknown_columns = column_displaynames - all_database_fields
        if len(missing_columns) or len(missing_columns):
            print("version change history:")
            pp = pprint.PrettyPrinter(indent=2)
            version_number = self.meta_strcture.version
            pp.pprint(version_number)
            for column_displayname in missing_columns:
                logging.warning("warning! column %s is missing in %s. Please update your excel file to the latest version." % (column_displayname, sheet_name))
            for column_displayname in unknown_columns:
                logging.warning("warning! The database does not know what is column %s in %s. Please update your excel file to the latest version." % (column_displayname, sheet_name))

    def process_value(self, value, ctype, column_displayname, datemode):
        """
        modify some invalid value in excel sheet to match database requirement.
        """
        data_type = self.get_data_type(column_displayname)
        if column_displayname == "User accession" and (value == "NA" or value == ''):  # always us "" if user accession is empty or NA
            value == ""
        elif column_displayname == "System Accession" and (value == "NA" or value == ''):  # always us "" if sys accession is empty or NA
            value == ""
        elif ctype == CTYPE_BOOLEAN:
            if value:
                value = "TRUE"
            else:
                value = "FALSE"
        # now consider data_type:
        elif data_type == "text" and ctype == CTYPE_NUMBER:
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

    def filter_by_accession(self, row_obj, isupdate):
        """
        fileter TRUE or FALSE based on user accession and system accession of the record.
        During update, return TRUE if at least one of user accession or system accession exists and start with accession rule.
        During submission of new record, return TRUE if system accession does not exist and user accession start with accession rule.
        user accession and system accession always exist as key.

        """
        sheet_name = row_obj.sheet_name
        user_accession_rule = self.meta_strcture.get_user_accession_rule(sheet_name)
        system_accession_rule = self.meta_strcture.get_system_accession_rule(sheet_name)

        if "User accession" not in row_obj.schema:
            row_obj.schema["User accession"] = ''
        user_accession = row_obj.schema["User accession"]
        if "System Accession" not in row_obj.schema:
            row_obj.schema["System Accession"] = ''
        system_accession = row_obj.schema["System Accession"]

        if isupdate:
            if user_accession.startswith(user_accession_rule) or system_accession.startswith(system_accession_rule):
                return 1
            else:
                logging.warning("All records in %s without a valid system accession or user accession will be skipped during update!" % sheet_name)
                return 0
        else:
            if system_accession != '':
                logging.info("Skip %s in %s" % (system_accession, sheet_name))
                return 0
            elif user_accession.startswith(user_accession_rule):
                return 1
            else:
                sys.exit("Please provide valid User accessions in %s! It should start with %s" % (sheet_name, user_accession_rule))


class Poster:
    def __init__(self, token, meta_url, submit_url, isupdate, notest, meta_strcture):
        self.token_key = 'bearer ' + token
        self.meta_url = meta_url
        self.submit_url = submit_url
        self.isupdate = isupdate
        self.notest = notest
        self.meta_strcture = meta_strcture
        self.token_header = {"Authorization": bearer_token}
        self.user_name = set_username()

    def set_username(self):
        token_url = self.test + '/api/usertoken/' + self.token
        return requests.get(token_url).json()["username"]

    def get_sheet_info(self, sheet_name):
        meta_url = self.meta_url
        category = self.meta_strcture.get_category(sheet_name)
        categories = self.meta_strcture.get_categories(category)
        return meta_url, category, categories

    def fetch_record(self, sheet_name, system_accession):
        meta_url, category, categories = self.get_sheet_info(sheet_name)
        get_url = meta_url + '/api/' + categories + '/' + system_accession
        main_obj = requests.get(get_url).json()["mainObj"][category]
        record = RowData(sheet_name)
        record.schema = main_obj[category]
        record.relationships = main_obj[added]
        return record

    def fetch_all(self, sheet_name):
        meta_url, category, categories = self.get_sheet_info(sheet_name)
        user_name = self.user_name
        get_url = url + '/api/' + categories
        response = requests.get(get_url).json()
        full_list = response[categories]  # returns a list of existing records.
        return [x for x in full_list if x['user'] == user_name]

    def submit_record(self, row_data):
        sheet_name = row_data.sheet_name
        meta_url, category, categories = self.get_sheet_info(sheet_name)
        submit_url = self.submit_url
        saved_submission_url = url_submit + "/api/submission"
        if row_data.schema["accession"] == "":
            row_data.remove("accession")
            post_url = metaurl + '/api/' + categories
        else:
            post_url = metaurl + '/api/' + categories + '/' + system_accession
        post_body = row_data.schema
        response = requests.post(post_url, headers=self.token_header, data=post_body)
        if response['statusCode'] != 200:
            logging.error("%s update failed in line 305!" % system_accession)
        system_accession = response["accession"]

    def link_record(self):
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
        response = requests.post(linkurl, headers=self.token, data=link_body)

    def upload_sheet(self, sheet_data):
        sheet_name = sheet_data.name
        for record in sheet_data.all_records:
            self.submit_record(url, category)

    def duplication_check(self, sheet_data):
        """
        Make sure all the system accessions and user accessions are unique in the sheet.
        To update records, make sure each row has a valid record exisint in the database. Fetch both system accession and user accession for all records.
        """
        isupdate = self.isupdate
        notest = self.notest
        sheet_name = sheet_data.name
        categories = get_categories(sheet_name)
        existing_sheet_data = self.fetch_all(categories)
        existing_user_accessions = [x['user_accession'] for x in existing_sheet_data]
        if len(existing_user_accessions) != len(set(existing_user_accessions)):
            sys.exit("redundant user accession exists in the %s, please contact dcc to fix the issue!" % sheet_name)
        existing_user_system_accession_pair = [{x["user_accession"]: x["accession"]} for x in existing_sheet_data]
        user_accession_list = []
        for record in sheet_data.all_records:
            accession = record.schema["accession"]
            user_accession = record.schema["user_accession"]
            if isupdate:
                # find if there is redundancy in the list:
                system_accession_list = []
                if user_accession == "":  # if user accession does not exist, system accession must exist in both worksheet and database. and it has to be new to system_accession_list.
                    if accession in system_accession_list:
                        sys.exit("redundant system accession %s in %s!" % (accession, sheet_name))
                    elif accession not in existing_user_system_accession_pair.values():
                        sys.exit("system accession %s in %s does not exist in our database, unable to update it!" % (accession, sheet_name))
                    else:
                        matching_user_accession = [k for k, v in existing_user_system_accession_pair.items() if v == accession][0]
                        system_accession_list.append(accession)
                        user_accession_list.append(matching_user_accession)
                        record.add("User accession", matching_user_accession)
                elif user_accession in user_accession_list:
                    sys.exit("redundant user accession %s in %s!" % (user_accession, sheet_name))
                elif user_accession not in existing_user_accessions:
                    sys.exit("user accession %s in %s does not exist in our database, unable to update it!" % (user_accession, sheet_name))
                else:
                    matching_accession = existing_user_system_accession_pair[user_accession]
                    logging.info("Found %s user accession %s in our database with system accession %s" % (sheet_name, user_accession, matching_accession))
                    if matching_accession == accession or accession == "":
                        user_accession_list.append(user_accession)
                        system_accession_list.append(matching_accession)
                        record.add("System Accession", matching_accession)
                    else:
                        sys.exit("for the row in %s with user accession %s, the system accession %s does not match our record %s in the database!" % (sheet_name, user_accession, accession, matching_accession))

            else:  # for submission, all the rows are already filtered. All of them have valid user accession, and all the rows with system accession == ''.
                if user_accession in user_accession_list:
                    sys.exit("redundant user accession %s in %s!" % (user_accession, sheet_name))
                elif not notest:
                    user_accession_list.append(user_accession)
                    record.replace_accession()
                elif user_accession in existing_user_accessions:
                    matching_accession = existing_user_system_accession_pair[user_accession]
                    record.add("System Accession", matching_accession)
                    user_accession_list.append(user_accession)
                else:
                    user_accession_list.append(user_accession)


class BookData:
    def __init__(self, meta_strcture):
        self.meta_strcture = meta_strcture
        self.data = dict()
        self.submission_log = dict()

    def add_sheet(self, sheet_data):
        sheet_name = sheet_data.name
        self.data[sheet_name] = sheet_data

    def save_submission(self, sheet_name, accession)
        category = 
        if category in self.submission_log:
            self.submission_log[category].append(accession)
        else:
            self.submission_log.update({category:[accession]})

    def swipe_accession(self):
        accession_table=dict()
        for sheet in self.data:
            sheet_data = self.data[sheet]
            all_records = sheet_data.all_records
            for record in all_records:
                user_accession = record.schema['user_accession']
                system_accession = record.schema['accession']
                accession_table.update({user_accession:system_accession})
                if old_accession in record:
                    accession_table.update({record.old_accession:system_accession})

        for sheet in self.data:
            sheet_data = self.data[sheet]
            all_records = sheet_data.all_records
                for record in all_records:
                    for column_name in record.relationships:
                        for linkto in record.relationships[column_name]
                            accession_list = record.relationships[column_name][linkto]
                                for index, accession in enumerate(accession_list):
                                    if accession in accession_table:
                                        accession_list[index] = accession_table[accession]


class SheetData:
    def __init__(self, sheet):
        self.name = sheet
        self.all_records = []

    def add_record(self, row_data):
        self.all_records.append(row_data)

    def new_row(self):
        row_obj = RowData(self.name)
        return row_obj


class RowData:
    def __init__(self, sheet_name):
        self.schema = dict()
        self.relationships = dict()
        self.sheet_name = sheet_name

    def add(self, column_displayname, value):  # add or replace value in column
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

    def remove(self, column_name):
        if column_name in self.schema:
            self.schema.pop(column_name)
        else:
            sys.exit("remove method can only delete schema columns, but you are trying to delete %s in %s" % (column_name, self.sheet))

    def replace_accession(self, new_accession=""):
        if new_accession == "":
            randomid = uuid.uuid1()
            new_user_accession = user_accession[:8] + str(randomid)
        self.old_accession = self.schema["user_accession"]
        self.schema["user_accession"] = new_accession


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

    if not args.token:
        logging.error("please provide a user API key!")
        sys.exit("please provide a user API key!")  # make token argument mandatory.

    if args.notest:
        action_url_meta = URL_META
        action_url_submit = URL_SUBMIT
    else:
        action_url_meta = TESTURL_META
        action_url_submit = TESTURL_SUBMIT

    meta_strcture = MetaStucture(action_url_meta, ALL_CATEGORIES)
    meta_strcture.isupdate(args.isupdate)
    meta_strcture.notest(args.notest)

    reader = SheetReader(meta_strcture)
    poster = Poster(args.token, action_url_meta, action_url_submit, args.isupdate, args.notest, meta_strcture)

    workbook = xlrd.open_workbook(args.excel)
    book_data = BookData(meta_strcture)
    sheet_names = workbook.sheet_names()
    for sheet in sheet_names:
        if sheet not in meta_strcture.schema_dict.keys():  # skip "Instructions" and "Lists"
            continue
        sheet_obj = workbook.sheet_by_name(sheet)
        reader.verify_column_names(sheet_obj)
        sheet_data = reader.read_sheet(sheet_obj)

        poster.duplication_check(sheet_data)

        # Now upload all the records on sheet_data:
        for record in sheet_data.all_records:
            poster.submit_record(record)
        book_data.add(sheet_data)
    book_data.swipe_accession()
    for shee_name, sheet_data in book_data.data.items():
        for record in sheet_data.all_records:
            poster.link_record(record)



    metadata_obj.sys_acc_assign()



if __name__ == '__main__':
    main()
