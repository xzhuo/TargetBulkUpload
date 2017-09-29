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
SCHEMA_STRING = '/schema/'
RELATIONSHIP_STRING = '/schema/relationships/'
VERSION_STRING = '/api/version'
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


class MetaStructure:
    def __init__(self, url, categories, schema_string, relationship_string, version_string):
        """
        Set up metastructure:
        :param: url - it is the meta_url used for submission.
        :param: categories - it is the ALLCATEGORIES dictionary. the key is category, the value is sheet_name.
        :schema_string: - it is the the schema string part of the url.
        :relationship_string: - it is the relationship string part of the url.
        :version_string: it is the version string parl of the url
        :return:

        :atribiutes: url - the meta_url
        :categories: the category-sheet_name dictionary.
        :version: the version of current system, retrived from a get request.
        :schema_dict: the dictionary with all the schema structure. Each schema_dict[sheet_name] is a list of dictionary.
        An example with experiment, the last item (system accession) is added after the get request.
        {
            "Experiment": [
                {
                    name: "user_accession",
                    text: "User accession",
                    placeholder: "USREXP####",
                    type: "text",
                    required: false
                },
                {
                    name: "experiment_alias",
                    text: "Experiment Alias",
                    placeholder: "",
                    type: "text",
                    required: true
                },
                {
                    name: "design_description",
                    text: "Design Description",
                    placeholder: "",
                    type: "textarea",
                    required: false
                },
                {
                    name: "accession",
                    text: "System Accession",
                    type: "text"
                }
            ]
            ...
        }
        :link_dict: the dictionary with all the linkage structure. Each link_dict[sheet_name] is a dictionary {"one": category, "all": categories, "prefix"}
        An example with experiment:
        {
            "Experiment": {
                one: "experiment",
                all: "experiments",
                prefix: "TRGTEXP000",
                usr_prefix: "USREXP000",
                connections: [
                    {
                        name: "performed_under",
                        placeholder: "Link to Bioproject accession",
                        to: "bioproject",
                        all: "bioprojects",
                        display_name: "Bioproject"
                    }
                ]
            }
            ...
        }
        """
        self.url = url
        self.categories = categories  # it is a dictionary
        self.schema_dict = self._url_to_json(schema_string)
        self.link_dict = self._url_to_json(relationship_string)
        self.version = self._set_version(version_string)
        for category in self.schema_dict:
            self.schema_dict[category].append({"name": "accession", "text": "System Accession", "type": "text"})

    def get_sheet_url(self, sheet_name):
        pass

    def get_category(self, sheet_name):
        """
        :param: sheet_name - the excel worksheet name.
        :return: the category name.
        """
        return self.link_dict[sheet_name]["one"]

    def get_categories(self, sheet_name):
        """
        :param: sheet_name - the sheet_name in excel file
        :return: the name of "categories"
        """
        return self.link_dict[sheet_name]["all"]

    def get_sheet_schema(self, sheet_name):
        return self.schema_dict[sheet_name]  # schema is a list

    def get_sheet_link(self, sheet_name):
        return self.link_dict[sheet_name]  # link is a dictionary, link["connections"] is a list.

    def get_user_accession_rule(self, sheet_name):
        """
        :param: sheet_name - the excel sheet name
        :return: the user accession rule prefix for the sheet.
        """
        link = self.get_sheet_link(sheet_name)
        return link["usr_prefix"][:-NUMBER_ZEROS]

        # alternative solution:
        # schema = self.get_schema(sheet_name)
        # return [x["placeholder"] for x in schema if x["text"] == "User accession"][0][:-4]

    def get_system_accession_rule(self, sheet_name):
        """
        :param: sheet_name - the excel sheet name
        :return: the system accession rule prefix for the sheet.
        """
        link = self.get_sheet_link(sheet_name)
        return link["prefix"][:-NUMBER_ZEROS]

    def get_schema_column_headers(self, sheet_name):  # get a list of all column display names, including "System Accession"
        schema = self.get_sheet_schema(sheet_name)
        return [x["text"] for x in schema]

    def get_link_column_headers(self, sheet_name):  # get a list of all column display names
        link = self.get_sheet_link(sheet_name)
        return [x["display_name"] for x in link["connections"]]

    def get_all_column_headers(self, sheet_name):
        return self.get_schema_column_headers(sheet_name) + self.get_link_column_headers(sheet_name)


    def get_data_type(self, sheet_name, column_header):
        """
        :param: sheet_name - the sheet name! what the fuck do you expect?!
        :param: column_header - the column header shown in the excel file.
        :return: the data type of that column, for relationship it is always a "text"
        """
        return self._get_column_info(sheet_name, column_header, "type")

    def get_column_name(self, sheet_name, column_header):
        """
        get column_name in database using column header in excel.
        """
        return self._get_column_info(sheet_name, column_header, "name")

    def get_linkto(self, sheet_name, column_header):
        """
        :param: sheet_name
        :param: column_header
        :return: another sheet_name the columna_header in sheet_name linked to.
        """
        if column_header in self.get_link_column_headers(sheet_name):
            link = self.get_sheet_link(sheet_name)
            category = [x["to"] for x in link["connections"] if x["display_name"] == column_header][0]
            return self.categories[category]
        else:
            sys.exit("%s in %s is not a connection column" % (column_header, sheet_name))

    def _url_to_json(self, string):
        new_dict = {}
        for category, sheet_name in self.categories.items():
            json_url = self.url + string + category + '.json'
            data = requests.get(json_url).json()["data"]  # data is a list for schema, but data is a dict for links. within links: data['connections'] is a list.
            new_dict[sheet_name] = data
        return new_dict

    def _set_version(self, version_string):
        full_url = self.url + version_string
        return requests.get(full_url).json()

    def _get_column_info(self, sheet_name, column_header, info):
        """
        info is either "type" or "name"
        """
        if column_header in self.get_schema_column_headers(sheet_name):
            info_list = [x[info] for x in self.get_sheet_schema(sheet_name) if x["text"] == column_header]
            info = info_list[0]
        elif column_header in self.get_link_column_headers(sheet_name):
            if info == "type":
                info = "text"
            else:  # info == "name"
                info_list = [x[info] for x in self.get_sheet_link(sheet_name)["connections"] if x["display_name"] == column_header]
                info = info_list[0]
        else:
            sys.exit("unknow info %s of %s in %s" % (info, column_header, sheet_name))
        return info


class SheetReader:
    def __init__(self, meta_structure, excel_header_row, excel_data_start_row, isupdate):
        self.meta_structure = meta_structure
        self.isupdate = isupdate
        self.excel_header_row = excel_header_row
        self.excel_data_start_row = excel_data_start_row

    def get_sheet_headers(self, sheet_obj):
        """
        Get all the columan headers from worksheet.
        Note the difference between SheetReader.get_sheet_headers and MetaStructure.get_all_column_headers.
        The former get the headers from the file, while the later get the headers from metadata database structure + system accession.
        :param: sheet_obj - the sheet obj from xlrd package.
        :return: a list of all column headers in the worksheet
        """
        excel_header_row = self.excel_header_row
        return [str(sheet_obj.cell(excel_header_row, col_index).value).rstrip() for col_index in range(sheet_obj.ncols)]  # start from row number 1 to skip header

    def verify_column_names(self, sheet_obj):
        """
        compare all the columns names in the worksheet with correspondence databases fields.
        pop up a warning if there is any missing column.
        and also give a warning if any column will be skipped.
        """
        sheet_name = sheet_obj.name
        column_headers_from_sheet = set(self.get_sheet_headers(sheet_obj))
        column_headers_from_structure = set(self.meta_structure.get_all_column_headers(sheet_name))
        missing_columns = column_headers_from_structure - column_headers_from_sheet
        unknown_columns = column_headers_from_sheet - column_headers_from_structure
        if len(missing_columns) or len(missing_columns):
            print("version change history:")
            pp = pprint.PrettyPrinter(indent=2)
            version_number = self.meta_structure.version
            pp.pprint(version_number)
            for column_header in missing_columns:
                logging.warning("warning! column %s is missing in %s. Please update your excel file to the latest version." % (column_header, sheet_name))
            for column_header in unknown_columns:
                logging.warning("warning! The database does not know what is column %s in %s. Please update your excel file to the latest version." % (column_header, sheet_name))

    def read_sheet(self, sheet_obj, datemode):  # read excel file.
        """
        :param: sheet_obj - The xlrd sheet object.
        :param: datemode - The workbook.datemode got from xlrd workbook class.
        returns a fully validated SheetData object.
        """
        isupdate = self.isupdate
        column_headers = self.get_sheet_headers(sheet_obj)
        sheet_data = SheetData(sheet_obj.name, self.meta_structure)
        for row_index in range(self.excel_data_start_row, sheet_obj.nrows):
            row_data = sheet_data.new_row()
            for col_index in range(sheet_obj.ncols):
                column_header = column_headers[col_index]

                # column_name = SheetData.get_column_name(column_header)
                # data_type = SheetData.get_data_type(column_header)
                # islink = SheetData.islink(column_header)
                cell_obj = sheet_obj.cell(row_index, col_index)  # the cell obj from xlrd
                row_data.validate_add(column_header, cell_obj, datemode)
            sheet_data.filter_add(row_data, isupdate)
        return sheet_data


class Poster:
    def __init__(self, token, meta_url, submit_url, isupdate, notest, meta_structure):
        self.token = token
        self.token_key = 'bearer ' + token
        self.meta_url = meta_url
        self.submit_url = submit_url
        self.isupdate = isupdate
        self.notest = notest
        self.meta_structure = meta_structure
        self.token_header = {"Authorization": self.token_key}
        self.user_name = self.set_username()

    def set_username(self):
        token_url = self.submit_url + '/api/usertoken/' + self.token
        return requests.get(token_url).json()["username"]

    def get_sheet_info(self, sheet_name):
        meta_url = self.meta_url
        category = self.meta_structure.get_category(sheet_name)
        categories = self.meta_structure.get_categories(sheet_name)
        return meta_url, category, categories

    def fetch_record(self, sheet_name, system_accession):
        meta_url, category, categories = self.get_sheet_info(sheet_name)
        get_url = meta_url + '/api/' + categories + '/' + system_accession
        main_obj = requests.get(get_url).json()["mainObj"][category]
        record = RowData(sheet_name, self.meta_structure)
        record.schema = main_obj[category]
        record.relationships = main_obj["added"]
        return record

    def fetch_all(self, sheet_name):
        meta_url, category, categories = self.get_sheet_info(sheet_name)
        user_name = self.user_name
        get_url = self.meta_url + '/api/' + categories
        response = requests.get(get_url).json()
        full_list = response[categories]  # returns a list of existing records.
        return [x for x in full_list if x['user'] == user_name]

    def submit_record(self, row_data):
        sheet_name = row_data.sheet_name
        meta_url, category, categories = self.get_sheet_info(sheet_name)
        submit_url = self.submit_url

        accession = row_data.remove("accession")  # it is essentially a dict pop.
        # for update, accession must exists, so it goes to else. for submit, accession must be "".
        if accession == "":
            post_url = meta_url + '/api/' + categories
        else:
            post_url = meta_url + '/api/' + categories + '/' + accession
        post_body = row_data.schema
        response = requests.post(post_url, headers=self.token_header, data=post_body)
        return response.json()

    def link_record(self, row_data):
        sheet_name = row_data.sheet_name
        system_accession = row_data.schema["accession"]
        for column_name in row_data.relationships:
            for linkto_category in row_data.relationships[column_name]:
                accession_list = row_data.relationships[column_name][linkto_category]
                for linkto_accession in accession_list:
                    self.link_change(sheet_name, system_accession, linkto_category, linkto_accession, column_name, "add")

    def link_update(self):
        pass

    def link_change(self, sheet_name, system_accession, linkto_category, linkto_accession, connection_name, direction):
        meta_url, category, categories = self.get_sheet_info(sheet_name)
        linkurl = meta_url + '/api/' + categories + '/' + system_accession + '/' + linkto_category + '/' + direction  # direction should be add or remove
        link_body = {"connectionAcsn": linkto_accession, "connectionName": connection_name}
        response = requests.post(linkurl, headers=self.token, data=link_body)
        return response.json()

    def save_submission(self, book_data):
        saved_submission_url = self.submit_url + "/api/submission"

    def duplication_check(self, sheet_data):
        """
        each record has been validated by themselves.
        for update, at least one of user or system accession exists, the other one must be "".
        for submit, system accesion must be "", user accesion must fit the rule.

        Make sure all the system accessions and user accessions are unique in the sheet.
        To update records, make sure each row has a valid record exisint in the database. Fetch both system accession and user accession for all records.
        
        exit if duplicated system accession or user accession found in the sheet;
        
        for update:
            exit if the record not found in the database, or the record in the database has different user-system accession pair.
            passed records contains both user and system accession that matchs record in the database.
        for submit:
            if test:
                replace user accesion with a random string, save original accession as record.old_accession.
                assign all system accession to "".
            if notest:
                for record existing in the database, assign system accession to the record.
                for record do not exist in the database, leave system accession as "".

        I kept all the record there and assigned both system accession and user accession for submission. 
        Now I can filter that later to remove those with system accesion before upload.
        Maybe in the future I can add a "submit and update option" to submit new data and update exising ones at same time,
        and I don't need to change this part for that new fuction.
        """
        isupdate = self.isupdate
        notest = self.notest
        sheet_name = sheet_data.name
        existing_sheet_data = self.fetch_all(sheet_name)
        existing_user_accessions = [x['user_accession'] for x in existing_sheet_data]
        if len(existing_user_accessions) != len(set(existing_user_accessions)):
            sys.exit("redundant user accession exists in the %s, please contact dcc to fix the issue!" % sheet_name)
        existing_user_system_accession_pair = {x["user_accession"]: x["accession"] for x in existing_sheet_data}  # python2.7+
        user_accession_list = []
        for record in sheet_data.all_records:
            accession = record.schema["accession"]
            user_accession = record.schema["user_accession"]
            if user_accession in user_accession_list:
                sys.exit("redundant user accession %s in %s!" % (user_accession, sheet_name))
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
                if not notest:
                    user_accession_list.append(user_accession)
                    record.replace_accession()
                elif user_accession in existing_user_accessions:
                    matching_accession = existing_user_system_accession_pair[user_accession]
                    record.add("System Accession", matching_accession)
                    user_accession_list.append(user_accession)
                else:
                    user_accession_list.append(user_accession)


class BookData:
    def __init__(self, meta_structure):
        self.meta_structure = meta_structure
        self.data = dict()
        self.submission_log = dict()

    def add_sheet(self, sheet_data):
        sheet_name = sheet_data.name
        self.data[sheet_name] = sheet_data

    def save_submission(self, sheet_name, accession):
        category = self.meta_structure.get_category(sheet_name)
        if category in self.submission_log:
            self.submission_log[category].append(accession)
        else:
            self.submission_log.update({category: [accession]})

    def swipe_accession(self):
        """
        for all the relationships in the bookdata, point it to a system accession according to user accession.
        """
        accession_table = dict()
        for sheet in self.data:
            sheet_data = self.data[sheet]
            all_records = sheet_data.all_records
            for record in all_records:
                user_accession = record.schema['user_accession']
                system_accession = record.schema['accession']
                accession_table.update({user_accession: system_accession})
                if record.old_accession:
                    accession_table.update({record.old_accession: system_accession})

        for sheet in self.data:
            sheet_data = self.data[sheet]
            all_records = sheet_data.all_records
            for record in all_records:
                for column_name in record.relationships:
                    for linkto in record.relationships[column_name]:
                        accession_list = record.relationships[column_name][linkto]
                        for index, accession in enumerate(accession_list):
                            if accession in accession_table:
                                accession_list[index] = accession_table[accession]


class SheetData:
    def __init__(self, sheet_name, meta_structure):
        self.name = sheet_name
        self.meta_structure = meta_structure
        self.all_records = []

    def add_record(self, row_data):
        self.all_records.append(row_data)

    def new_row(self):
        row_data = RowData(self.name, self.meta_structure)
        return row_data

    def filter_add(self, row_data, isupdate):
        """
        1. For records without user accession or system accession, assign "" to the field.
        2. Fileter TRUE or FALSE based on user accession and system accession of the record.
        During update, return TRUE if at least one of user accession or system accession exists and start with accession rule.
        During submission of new record, return TRUE if system accession does not exist and user accession start with accession rule.
        user accession and system accession always exist as key.

        once filtered, add the row_data to the sheet_data.

        """
        sheet_name = self.name
        user_accession_rule = self.meta_structure.get_user_accession_rule(sheet_name)
        system_accession_rule = self.meta_structure.get_system_accession_rule(sheet_name)

        if "user_accession" not in row_data.schema:
            row_data.schema["user_accession"] = ''
        user_accession = row_data.schema["user_accession"]
        if "accession" not in row_data.schema:
            row_data.schema["accession"] = ''
        system_accession = row_data.schema["accession"]
        valid = 0
        if isupdate:
            if user_accession.startswith(user_accession_rule) and system_accession.startswith(system_accession_rule):
                valid = 1
            elif user_accession.startswith(user_accession_rule) and system_accession == "":
                valid = 1
            elif user_accession == "" and system_accession.startswith(system_accession_rule):
                valid = 1
            else:
                logging.warning("All records in %s without a valid system accession or user accession will be skipped during update!" % sheet_name)

        else:
            if user_accession.startswith(user_accession_rule) and system_accession == "":
                valid = 1
            else:
                logging.warning("skip row %s %s in %s! It should not have system_accession and the user accession must follow the accession rule %s!" % (sheet_name, system_accession, user_accession, user_accession_rule))
        if valid:
            self.add_record(row_data)


class RowData:
    def __init__(self, sheet_name, meta_structure):
        self.sheet_name = sheet_name
        self.meta_structure = meta_structure
        self.schema = dict()
        self.relationships = dict()

    def add(self, column_header, value):  # add or replace value in column
        sheet_name = self.sheet_name
        meta_structure = self.meta_structure
        column_name = meta_structure.get_column_name(sheet_name, column_header)
        if column_header in meta_structure.get_link_column_headers(sheet_name):
            # do link stuff
            accession_list = value.split(",")  # split value in cell by ",""
            sheetlinkto = meta_structure.get_linkto(self.sheet_name, column_header)
            categorylinkto = meta_structure.get_category(sheetlinkto)
            if column_name in self.relationships:
                self.relationships[column_name][categorylinkto] = accession_list
            else:
                self.relationships[column_name] = {categorylinkto: accession_list}
        elif column_header in meta_structure.get_schema_column_headers(sheet_name):
            self.schema[column_name] = value
        else:
            sys.exit("unknown column %s in %s!" % (column_header, sheet_name))

    def remove(self, column_name):
        """
        It's input is a column_name, instead of a column_header! And it only works for column names in schema. I use it only to delete accession columns
        """
        if column_name in self.schema:
            return self.schema.pop(column_name)
        else:
            sys.exit("remove method can only delete schema columns, but you are trying to delete %s in %s" % (column_name, self.sheet_name))

    def replace_accession(self, new_user_accession=""):
        sheet_name = self.sheet_name
        meta_structure = self.meta_structure
        user_accession_rule = meta_structure.get_user_accession_rule(sheet_name)
        if new_user_accession == "":
            randomid = uuid.uuid1()
            new_user_accession = user_accession_rule + str(randomid)
        self.old_accession = self.schema["user_accession"]
        self.schema["user_accession"] = new_user_accession

    def validate_add(self, column_header, cell_obj, datemode):
        """
        :param: column_header - the column_header of the cell you want to add.
        :param: cell_obj - the cell object from xrld package.
        :validate and add the cell value to the row_data:
        modify some invalid value in excel sheet to match database requirement.
        empty accessions ("" or "NA") become "".
        "NA" for date become 1970-01-01.
        "NA" in number fields become -1.
        all float value round to 2 digits.
        """
        value = cell_obj.value
        ctype = cell_obj.ctype
        data_type = self.meta_structure.get_data_type(self.sheet_name, column_header)
        # Now begin validation:

        if column_header == "User accession" and (value == "NA" or value == ''):  # always us "" if user accession is empty or NA
            value == ""
        elif column_header == "System Accession" and (value == "NA" or value == ''):  # always us "" if sys accession is empty or NA
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
                sys.exit("please use number for %s in %s" % (column_header, self.sheet_name))
        elif data_type == "number" and value == 'NA':  # assign number field to -1 if it is NA in the excel.
            value = -1
            logging.info("Change NA to -1 for %s in %s." % (column_header, self.sheet_name))
        self.add(column_header, value)  # or use columan display name?


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

    meta_structure = MetaStructure(action_url_meta, ALL_CATEGORIES, SCHEMA_STRING, RELATIONSHIP_STRING, VERSION_STRING)
    # meta_structure.isupdate(args.isupdate)
    # meta_structure.notest(args.notest)
    # These options no longer saved in meta_structure

    reader = SheetReader(meta_structure, EXCEL_HEADER_ROW, EXCEL_DATA_START_ROW, args.isupdate)
    poster = Poster(args.token, action_url_meta, action_url_submit, args.isupdate, args.notest, meta_structure)

    workbook = xlrd.open_workbook(args.excel)
    book_data = BookData(meta_structure)
    sheet_names = workbook.sheet_names()
    for sheet in sheet_names:
        if sheet not in meta_structure.schema_dict.keys():  # skip "Instructions" and "Lists"
            continue
        sheet_obj = workbook.sheet_by_name(sheet)
        reader.verify_column_names(sheet_obj)
        sheet_data = reader.read_sheet(sheet_obj, workbook.datemode)
        poster.duplication_check(sheet_data)
        # Now upload all the records on sheet_data:
        for record in sheet_data.all_records:
            response = poster.submit_record(record)  # submit the record, and assign system accession to the record.
            if response['statusCode'] != 200:
                logging.error("post request failed!")
            if not args.isupdate:
                accession = response["accession"]
                record.schema['accession'] = accession
                book_data.save_submission(sheet, accession)
        book_data.add_sheet(sheet_data)

    book_data.swipe_accession()
    poster.save_submission(book_data)
    for sheet_name, sheet_data in book_data.data.items():
        for record in sheet_data.all_records:
            poster.link_record(record)


if __name__ == '__main__':
    main()
