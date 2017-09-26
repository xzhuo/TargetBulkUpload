import sys
import xlrd
from collections import OrderedDict
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

uploader_to_use = Uploader()


def change_uploader(new_uploader):
    uploader_to_use = new_uploader


######

import submission.py as submission

class FakeUploader():
    pass


fake = FakeUploader()
submission.change_uploader(fake)
submission.main()
assert(fake.the_json_that_I_didnt_send).equals({})

#####
total_tabs = {"assay": "Assay",
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


class SheetReader:
    def __init__(self, schema_source):
        self.schema_source = schema_source

    def read_sheet(self, sheet):
        category_name = sheet.name
        schema = self.schema_source.get_schema_for_category(category_name)
        # Validate with schema if desired
        # Return something Uploader can understand.  It can be a simple dict, or if it gets complicated enough, make a
        # new Metadata class and return an instance of that.
        return {}


class SchemaSource:
    def __init__(self, url):
        self.url = url

    def get_schema_for_category(self, category_name):
        pass

    def get_relationships_for_category(self, category_name):
        pass


class Uploader:
    def __init__(self, url):
        self.url = url

    def upload(self, data):
        pass


def upload_example():
    schema_source = SchemaSource(SCHEMA_URL)
    reader = SheetReader(schema_source)
    uploader = Uploader(UPLOAD_URL)
    for sheet in excel_doc:
        sheet_data = reader.read_sheet(sheet)
        uploader.upload(sheet_data)


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

    return parser.parse_args()


def main():
    logging.getLogger().setLevel(logging.INFO)  # Do I need a flag to change this?
    args = get_args()
    if args.token:
        bearer_token = 'bearer ' + args.token
        token_url = TESTURL_SUBMIT + '/api/usertoken/' + args.token
        # user_name_dict = request(token_url)
        user_name = request(token_url)["username"]
    else:
        logging.error("please provide a user API key!")
        sys.exit("please provide a user API key!")  # make token argument mandatory.
    schema_json = urlfields('schema', TESTURL_META)
    relationship_json = urlfields('relationships', TESTURL_META)
    for x in relationship_json["Assay"]["connections"]:
        if x['display_name'] == "Biosample":
            x['name'] = 'assay_input_biosample'
        if x['display_name'] == "Library":
            x['name'] = 'assay_input_library'
    versionNo = request(VERSIONURL)
    # if versionNo["current"] not in args.excel:
    #     logging.error("the excel version does not match the current metadata database version %s. Please use the latest template, or modify your file to match changes we made.\nVersion change history:" % versionNo["current"])
    #     pp = pprint.PrettyPrinter(indent=2)
    #     pp.pprint(versionNo)
        # sys.exit(1)
    relationship_connectto = {}  # relationship_name: table_name for connection fields.  {'Bioproject': {'works_on': 'lab'},...}
    ColumnnameToRelationship = {}  # display_column_name: relationship_name for connection fields.  {'Bioproject': {'Lab': 'works_on'},...}
    SheetToTable = {}  # excel file work sheet name to database table name correlation. {Assay:assays,...}
    for Table in relationship_json:
        if Table in relationship_json and 'one' in relationship_json[Table]:
            # relationship_connectto[Table] = {}
            # ColumnnameToRelationship[Table] = {}
            SheetToTable[Table] = relationship_json[Table]['all']
            if 'connections' in relationship_json[Table]:
                relationship_connectto[Table] = {x['name']: x['to'] for x in relationship_json[Table]['connections'] if 'to' in x}  # include experiment connections
                # relationship_connectto[Table] = {x['name']: x['to'] for x in relationship_json[Table]['connections'] if 'to' in x and x['to'] != 'experiment'}  # exclude experiment connections
                ColumnnameToRelationship[Table] = {x['display_name']: x['name'] for x in relationship_json[Table]['connections'] if 'display_name' in x}

    ColumnnameToAllfields = {}  # display_name: name for schema_json, all items with or without relationships. {'Assay': {'Assay protocol': 'assay_protocol',...},...}
    for Table in schema_json:
        logging.debug(Table)
        if Table in ColumnnameToRelationship:
            ColumnnameToAllfields[Table] = {**{x['text']: x['name'] for x in schema_json[Table] if 'text' in x}, **ColumnnameToRelationship[Table]}  # require python3.5 or later.
        else:
            ColumnnameToAllfields[Table] = {x['text']: x['name'] for x in schema_json[Table] if 'text' in x}

    submission = multi_excel2JSON(args.excel, schema_json, ColumnnameToRelationship, args.mode, versionNo)

    logging.debug(json.dumps(submission, indent=4, sort_keys=True))
    if args.notest:
        action_url_meta = URL_META
        action_url_submit = URL_SUBMIT
    else:
        action_url_meta = TESTURL_META
        action_url_submit = TESTURL_SUBMIT

    # a dict to track accession names.
    acc_name = {}
    # make sure there is no redundant user accession in the submission. Add the system accession if a record exists in the database.
    accession_check(args.notest, submission, action_url_meta, SheetToTable, args.mode, user_name, acc_name)
    logging.debug(json.dumps(submission, indent=4, sort_keys=True))


    ###############
    uploader_to_use.upload(args.testlink, args.notest, submission, relationship_connectto, SheetToTable, action_url_meta, action_url_submit, user_name, bearer_token, args.mode, acc_name)

    #upload(args.testlink, args.notest, submission, relationship_connectto, SheetToTable, action_url_meta, action_url_submit, user_name, bearer_token, args.mode, acc_name)
    if args.notest or args.mode:
        print("If you did not find errors above, all the records were successfully uploaded/updated to TaRGET metadata database!")
    else:
        print("If you did not find errors above, all the records were successfully uploaded to the testing database, \
            now you can upload the same file to real database with the '--notest' flag if you are using command line, \
            if you are using our website uploading excel then click the submit button.")


def multi_excel2JSON(file, schema_json, ColumnnameToRelationship, mode, versionNo):
    """
    it does blah blah blah.

    :param: file - is a file object.
    :param: schema_json - dict that blahs
    :...:
    :return: it returns unicorns and happiness
    """
    wb = xlrd.open_workbook(file)
    sheet_names = wb.sheet_names()
    all_sheets = OrderedDict()
    for Sheet in sheet_names:
        if Sheet == "Instructions" or Sheet == "Lists":
            continue
        sheet = wb.sheet_by_name(Sheet)
        columns = [str(sheet.cell(1, col_index).value).rstrip() for col_index in range(sheet.ncols)]  # start from row number 1 to skip header
        dict_list = []
        column_name_type_dict = {x['text']: {"column_name": x['name'], "data_type": x["type"]} for x in schema_json[Sheet] if 'text' in x}
        all_database_fields = list(column_name_type_dict.keys()) + list(ColumnnameToRelationship[Sheet].keys())
        for database_field in all_database_fields:
            if database_field not in columns:
                # logging.warning("warning! column %s is missing in %s. Please update your excel file to the latest version." % (database_field, Sheet))
                print("version change history:")
                pp = pprint.PrettyPrinter(indent=2)
                pp.pprint(versionNo)
                logging.warning("warning! column %s is missing in %s. Please update your excel file to the latest version." % (database_field, Sheet))
        accession_rule = [x['placeholder'] for x in schema_json[Sheet] if x['text'] == "User accession"][0][:-4]
        for row_index in range(2, sheet.nrows):
            # d = {columns[col_index]: str(sheet.cell(row_index, col_index).value.rstrip()) for col_index in range(sheet.ncols)}  # use string first
            d = OrderedDict()
            for col_index in range(sheet.ncols):
                Column_name = columns[col_index]
                column_name = "NA"
                data_type = "unknown"
                if Column_name == "System Accession":
                    column_name = "sysaccession"
                    data_type = "text"
                elif Column_name == "User Accession":
                    Column_name = "User accession"
                    data_type = "text"
                elif Column_name in column_name_type_dict:
                    column_name = column_name_type_dict[Column_name]["column_name"]
                    data_type = column_name_type_dict[Column_name]["data_type"]
                # for fielddict in schema_json[Sheet]:
                #     if fielddict["text"] == Column_name:
                #         column_name = fielddict["name"]
                #         data_type = fielddict["type"]
                #     if fielddict["text"] == "User accession":
                #         accession_rule = fielddict["placeholder"][:-4]

                # column_name = Column_name[:1].lower() + Column_name[1:]  # first character lowercase
                elif Column_name in ColumnnameToRelationship[Sheet]:
                # if column_name == "NA" and Sheet in ColumnnameToRelationship and Column_name in ColumnnameToRelationship[Sheet]:
                    column_name = ColumnnameToRelationship[Sheet][Column_name]
                    data_type = "text"

                if column_name == "zip_code" or column_name == "batchId":
                    data_type = "text"
                # data_type = "text"  # wait until the correct type set!! Temporary line here
                if column_name == "NA":
                    logging.warning("field name %s from %s in excel is not in the database! The column will be skipped and please download the latest excel template." % (Column_name, Sheet))
                else:
                    value = sheet.cell(row_index, col_index).value
                    ctype = sheet.cell(row_index, col_index).ctype
                    if column_name == "user_accession" and (value == "NA" or value == ''):  # delete 'NA' in user_accession.
                        # randomid = uuid.uuid1()
                        value = 'NA'  # accession_rule + str(randomid)

                    if ctype == 4:  # boolean
                        if value:
                            value = "TRUE"
                        else:
                            value = "FALSE"
                        # value = "TRUE"  # not enough, there are other restricted columns
                    # if value != '' or column_name == "sysaccession":
                    if 1:  # temporary indent holder
                        if data_type == "textnumber":
                            d[column_name] = value
                        elif data_type == "text":
                            if ctype == 2:
                                d[column_name] = str(value).rstrip('0').rstrip('.')  # delete trailing 0s if it is a number.
                                # d[column_name] = str(round(value))
                            else:
                                d[column_name] = str(value).rstrip()  # use string for now. May use number later.
                        elif data_type == "date":
                            if value == 'NA':
                                d[column_name] = '1970-01-01'
                            elif ctype == 3:
                                # ipdb.set_trace()
                                d[column_name] = xlrd.xldate.xldate_as_datetime(value, wb.datemode).date().isoformat()
                            else:
                                d[column_name] = value
                        elif data_type == "float":
                            if ctype == 2:
                                d[column_name] = round(value, 2)
                            else:
                                sys.exit("please use number for %s in %s" % (Column_name, Sheet))

                        elif data_type == "number" and value == 'NA':  # assign number field to -1 if it is NA in the excel.
                            d[column_name] = -1
                            logging.info("Change NA to -1 for %s in %s." % (column_name, Sheet))
                        else:
                            d[column_name] = value
            if mode:
                if d["user_accession"].startswith(accession_rule) or ("sysaccession" in d and d["sysaccession"].startswith("TRGT")):
                    dict_list.append(d)
                else:
                    logging.warning("All records in %s without a valid system accession or user accession will be skipped during update!" % Sheet)
            else:
                if "sysaccession" in d and d["sysaccession"].startswith("TRGT"):
                    logging.info("Skip %s in %s" % (d["sysaccession"], Sheet))
                elif "sysaccession" in d and d["sysaccession"] != '':
                    logging.error("Invalid system accession %s in %s!" % (d["sysaccession"], Sheet))
                else:
                    if d["user_accession"].startswith(accession_rule):
                        dict_list.append(d)
                    else:
                        logging.error("Please provide valid User accessions in %s! It should start with %s" % (Sheet, accession_rule))
                        # dict_list.append(d)  # temporary to import ENCODE data
                        sys.exit(1)  # temporary to import ENCODE data

        all_sheets[Sheet] = dict_list

    # j = json.dumps(all_sheets)
    print("Excel processing DONE")
    # return json.loads(j)
    return all_sheets


def request(url, parameter="", method="", bearer_token=""):
    if parameter == "" and method == "":  # a GET request
        req = urllib.request.Request(url, method="GET")
    else:
        bin_data = parameter.encode('ascii')
        req = urllib.request.Request(url, data=bin_data, method=method)
    req.add_header('Content-Type', 'application/json')
    req.add_header('Accept', 'application/json')
    req.add_header('Authorization', bearer_token)
    try:
        response = urllib.request.urlopen(req, timeout=10)
    except urllib.error.URLError as e:
        ResponseData = e.read().decode("utf8", 'ignore')
        ResponseDict = json.loads(ResponseData)
        if "message" in ResponseDict:
            logging.error(ResponseDict["message"])
        return ResponseDict
        # sys.exit(1)
    except timeout:
        sys.exit("Fail to create or update the following record to databse link %s. Please make sure the url used here is correct.\n%s" % (url, parameter))
        # return ResponseDict
        # sys.exit(1)

    else:
        ResponseDict = json.loads(response.read().decode())
        return ResponseDict


def accession_check(notest, metadata, url, SheetToTable, mode, user_name, acc_name):  # if there is duplicated user accession number.
    if not mode:  # user_accession exits always.
        for Sheet in metadata:
            table = SheetToTable[Sheet]
            fullurl = url + '/api/' + table
            existing = request(fullurl)
            # check if user_accession and user combination in the database.
            # if not SheetToTable[Sheet] in existing:
            #     logging.error("Error getting records of %s from database" % SheetToTable[Sheet])
            #     sys.exit(1)
            # redundant_user_accession = 0
            # for DB_entries in existing[SheetToTable[Sheet]]:
            #     if DB_entries["user_accession"] == tempAcsn and DB_entries["user"] == user_name:
            #         logging.info("Seems record %s submitted by %s already exists in the database.\nIf %s in the excel has been uploaded to the database, ignore this warning.\n" % (tempAcsn, DB_entries["user"], tempAcsn))
            #         redundant_user_accession = 1
            #         continue
            # if redundant_user_accession == 0:

            existing_user_accession = [x['user_accession'] for x in existing[table] if ('user_accession' in x and x["user"] == user_name)]
            accessionlist = []
            # replace = 0  # if replace is 1, it will automatically replace redundant user accession to a new uuid. if it is 2, all redundant user accessions will be deleted.
            # delete_i = []  # Hold all index to be deleted.
            for i, records in enumerate(metadata[Sheet]):
                user_accession = records["user_accession"]
                if user_accession == 'NA':
                    logging.error("please provide user accession for all rows in %s" % Sheet)
                    sys.exit(1)
                elif user_accession not in accessionlist:
                    if not notest:  # if it is test in DEV1, also append it for post request.
                        accessionlist.append(user_accession)
                        newname = replace_accession(metadata, user_accession)
                        acc_name[newname] = user_accession
                    elif user_accession not in existing_user_accession:
                        accessionlist.append(user_accession)
                    else:
                        existing_sys_acc = [x['accession'] for x in existing[table] if (x['user'] == user_name and x['user_accession'] == user_accession)]
                        logging.warning("Found %s user accession %s in our database with system accession %s, the record in excel file will not be submitted." % (Sheet, user_accession, " ".join(existing_sys_acc)))
                        if len(existing_sys_acc) == 1:
                            if "sysaccession" in metadata[Sheet][i] and len(metadata[Sheet][i]["sysaccession"]) > 0 and metadata[Sheet][i]["sysaccession"] != existing_sys_acc[0]:
                                logging.error("the system accession %s in the excel file does not match the system accession %s in our database!" % (metadata[Sheet][i]["sysaccession"], existing_sys_acc[0]))
                                sys.exit(1)
                            else:
                                metadata[Sheet][i]["sysaccession"] = existing_sys_acc[0]
                            # replace_accession(metadata, user_accession, existing_sys_acc[0])
                        else:
                            logging.error("redundant user accession exists in the database, please contact dcc to fix the issue!")
                            sys.exit(1)

                        # delete_i.append(i)

                        # if replace == 1:
                        #     logging.warning("Replace %s in %s with a new user accession." % (user_accession, Sheet))
                        #     replace_accession(metadata, user_accession)
                        # elif replace == 2:
                        #     # delete current record
                        #     delete_i.append(i)
                        # else:
                        #     prompt = input('Here are your options:\n1) submit %s as a new record to the database anyway;\n2) submit all the rows in the excel with redundant user accession to database as new records;\n'
                        #                    '3) skip %s because it has been submitted before;\n4) skip all rows with redundant user accession.\n\n'
                        #                    'Please type 1 or 2 or 3 or 4:    ' % (user_accession, user_accession))
                        #     if prompt == '1':
                        #         logging.warning("Ok, I will replace %s in %s with a new accession." % (user_accession, Sheet))
                        #         replace_accession(metadata, user_accession)
                        #     elif prompt == '2':
                        #         confirm_prompt = input("Are you sure all your data in the excel are new records? If you can confirm, all the following redundant records in the excel will be automatically uploaded.\n\
                        #             Please typle Yes or No:    ")
                        #         if confirm_prompt == "Yes" or confirm_prompt == "yes" or confirm_prompt == "Y" or confirm_prompt == "y":
                        #             logging.warning("Replace %s in %s with a new user accession." % user_accession, Sheet)
                        #             replace_accession(metadata, user_accession)
                        #             replace = 1
                        #         else:
                        #             logging.warning("Ok, I will only replace %s in the submission with a new user accession." % user_accession)
                        #             replace_accession(metadata, user_accession)
                        #     elif prompt == '3':
                        #         # delete this record
                        #         delete_i.append(i)
                        #     elif prompt == '4':
                        #         # delete this record
                        #         logging.warning("Ok, always skip the row with redundant user accession!")
                        #         delete_i.append(i)
                        #         replace = 2
                        #     else:
                        #         logging.error("Please provide valid response! (1,2,3,4)")
                        #         sys.exit(1)

                else:
                    logging.error("duplicated user accession %s in %s! Please always use unique user accession in an excel file!" % (user_accession, Sheet))
                    sys.exit(1)
            # for i in sorted(delete_i, key=int, reverse=True):
            #     logging.warning("Skip %s in %s!" % (metadata[Sheet][i]['user_accession'], Sheet))
            #     metadata[Sheet].pop(i)

    else:
        for Sheet in metadata:
            table = SheetToTable[Sheet]
            fullurl = url + '/api/' + table
            existing = request(fullurl)
            # check if user_accession and user combination in the database.
            # if not SheetToTable[Sheet] in existing:
            #     logging.error("Error getting records of %s from database" % SheetToTable[Sheet])
            #     sys.exit(1)
            # redundant_user_accession = 0
            # for DB_entries in existing[SheetToTable[Sheet]]:
            #     if DB_entries["user_accession"] == tempAcsn and DB_entries["user"] == user_name:
            #         logging.info("Seems record %s submitted by %s already exists in the database.\nIf %s in the excel has been uploaded to the database, ignore this warning.\n" % (tempAcsn, DB_entries["user"], tempAcsn))
            #         redundant_user_accession = 1
            #         continue
            # if redundant_user_accession == 0:
            existing_user_accession = [x['user_accession'] for x in existing[table] if "user_accession" in x and x["user"] == user_name]
            existing_sys_accession = [x['accession'] for x in existing[table] if "accession" in x and x["user"] == user_name]
            accessionlist = []
            sysaccession_list = []
            # replace = 0  # if replace is 1, it will automatically replace redundant user accession to a new uuid. if it is 2, all redundant user accessions will be deleted.
            # delete_i = []  # Hold all index to be deleted.
            for i, records in enumerate(metadata[Sheet]):
                user_accession = 'NA'
                sysaccession = 'NA'
                if "user_accession" in records:
                    user_accession = records["user_accession"]
                if "sysaccession" in records:
                    sysaccession = records["sysaccession"]
                if user_accession == 'NA':
                    if sysaccession not in sysaccession_list:
                        if sysaccession not in existing_sys_accession:
                            logging.error("system accession %s in %s does not exist in our database, unable to update it!" % (sysaccession, Sheet))
                            sys.exit(1)
                        else:
                            sysaccession_list.append(sysaccession)
                            records.pop("user_accession")
                    else:
                        logging.error("redundant system accession %s in %s!" % (sysaccession, Sheet))
                        sys.exit(1)
                elif user_accession not in accessionlist:
                    if user_accession not in existing_user_accession:
                        logging.error("user accession %s in %s does not exist in our database, unable to update it!" % (user_accession, Sheet))
                        sys.exit(1)
                    else:
                        accessionlist.append(user_accession)
                        existing_sys_acc = [x['accession'] for x in existing[table] if (x['user'] == user_name and x['user_accession'] == user_accession)]
                        logging.info("Found %s user accession %s in our database with system accession %s" % (Sheet, user_accession, " ".join(existing_sys_acc)))
                        if len(existing_sys_acc) == 1:
                            if "sysaccession" in metadata[Sheet][i] and len(metadata[Sheet][i]["sysaccession"]) > 0 and metadata[Sheet][i]["sysaccession"] != existing_sys_acc[0]:
                                logging.error("the system accession %s in the excel file does not match the system accession %s in our database!" % (metadata[Sheet][i]["sysaccession"], existing_sys_acc[0]))
                                sys.exit(1)
                            else:
                                metadata[Sheet][i]["sysaccession"] = existing_sys_acc[0]
                            # replace_accession(metadata, user_accession, existing_sys_acc[0])
                        else:
                            logging.error("redundant user accession exists in the database, please contact dcc to fix the issue!")
                            sys.exit(1)
                else:
                    logging.error("redundant user accession %s in %s!" % (user_accession, Sheet))
                    sys.exit(1)


def replace_accession(metadata, user_accession, new_accession=""):
    if new_accession == "":
        randomid = uuid.uuid1()
        new_accession = user_accession[:8] + str(randomid)
    for Sheet in metadata:
        for i, row in enumerate(metadata[Sheet]):
            for key in row:
                if row[key] == user_accession:
                    metadata[Sheet][i][key] = new_accession
    return new_accession


def upload(testlink, notest, metadata, relationship_connectto, SheetToTable, url, url_submit, user_name, bearer_token, mode, acc_name):
    AcsnDict = {}
    linkDict = {}
    submission_log = dict()  # a log of all system accession successfully uploaded or updated. It will be saved in api submission.
    saved_submission_url = url_submit + "/api/submission"
    all_possible_Sheets = total_tabs.values()  # I need to use all possible sheets here because some links may point to other tabs not in the metadata
    #["Lab", "Bioproject", "Diet", "Treatment", "Reagent", "Litter", "Mouse", "Biosample", "Library", "Assay", "File", "Experiment", "Mergedfile"]
    noerror = 0
    for Sheet in all_possible_Sheets:
        print("\nworking on: ")
        print(Sheet)
        if Sheet in metadata:
            # swap column name in excel to field name in database
            # for entry in metadata[Sheet]:
            #     print(Sheet)
            #     for key in entry:
            #         print(key)
            #         if Sheet in ColumnnameToRelationship and key in ColumnnameToRelationship[Sheet]:
            #             entry[ColumnnameToRelationship[Sheet][key]] = entry.pop(key)
            #             # del entry[key]

            AcsnDict[Sheet] = {}
            fullurl = url + '/api/' + SheetToTable[Sheet]
            if Sheet not in relationship_connectto or len(relationship_connectto[Sheet]) == 0:  # if nothing to connect in the database during bulk upload
                for entry in metadata[Sheet]:  # metadata[Sheet] is a list of dicts.
                    if mode:  # if it is update mode:
                        if "sysaccession" in entry and len(entry["sysaccession"]) > 0:
                            Acsn = entry.pop("sysaccession")
                            if "user_accession" in entry and len(entry["user_accession"]) > 0:
                                tempAcsn = entry["user_accession"]
                            else:
                                tempAcsn = Acsn
                            updateurl = fullurl + '/' + Acsn
                            response = request(updateurl, json.dumps(entry), 'POST', bearer_token)
                            if response['statusCode'] != 200:
                                logging.error("%s update failed in line 506!" % Acsn)
                                noerror = 1
                                break

                            if SheetToTable[Sheet] in submission_log:
                                submission_log[SheetToTable[Sheet]].append(Acsn)
                            else:
                                submission_log[SheetToTable[Sheet]] = []
                                submission_log[SheetToTable[Sheet]].append(Acsn)
                            logging.info("record %s has been updated!" % Acsn)
                            AcsnDict[Sheet][tempAcsn] = Acsn
                        elif "user_accession" in entry and len(entry["user_accession"]) > 0:
                            tempAcsn = entry["user_accession"]
                            existing = request(fullurl)
                            # check if user_accession and user combination in the database.
                            if not SheetToTable[Sheet] in existing:
                                logging.error("Error getting records of %s from database" % SheetToTable[Sheet])
                                noerror = 1
                                break
                            userAcc_found = 0
                            for DB_entries in existing[SheetToTable[Sheet]]:
                                if DB_entries["user_accession"] == tempAcsn and DB_entries["user"] == user_name:
                                    AcsnDict[Sheet][tempAcsn] = DB_entries["accession"]
                                    userAcc_found = 1
                                    logging.info("%s has been assigned with system accession %s. It won't be updated because you did not provide the system accession in the excel, but you can still link other records to it by calling %s!" % (tempAcsn, DB_entries["accession"], tempAcsn))
                                    continue
                            if not userAcc_found:
                                logging.warning("%s could not be found in the database, it will be ignored during update!" % tempAcsn)

                        else:
                            logging.warning("all rows without system accession or user accession will be ignored during update!")
                    else:  # if it is upload mode: skip records with system accession. skip records with user accession that match one in database.
                        if "sysaccession" in entry and len(entry["sysaccession"]) > 0:
                            tempAcsn = entry["user_accession"]
                            AcsnDict[Sheet][tempAcsn] = entry["sysaccession"]
                            continue
                        else:
                            tempAcsn = entry["user_accession"]  # user_accession always exists here.
                            if "sysaccession" in entry:
                                entry.pop("sysaccession")

                            response = request(fullurl, json.dumps(entry), 'POST', bearer_token)
                            if "accession" not in response:
                                logging.error("POST request failed in line 549!")
                                noerror = 1
                                break
                            else:
                                Acsn = response["accession"]
                                AcsnDict[Sheet][tempAcsn] = Acsn
                                if SheetToTable[Sheet] in submission_log:
                                    submission_log[SheetToTable[Sheet]].append(Acsn)
                                else:
                                    submission_log[SheetToTable[Sheet]] = []
                                    submission_log[SheetToTable[Sheet]].append(Acsn)
                                if notest:
                                    logging.info("Record %s has been successfully uploaded to database with a system accession %s" % (tempAcsn, Acsn))
                                else:
                                    logging.info("Record %s has been successfully validated!" % acc_name[tempAcsn])

            else:  # if connections need to be established: delete linkage in the dict, post request, and remember which connections need to add later.
                linkDict[Sheet] = {}
                for entry in metadata[Sheet]:  # metadata[Sheet] is a list of dicts.
                    if mode:
                        if "sysaccession" in entry and len(entry["sysaccession"]) > 0:
                            tempDict = {}
                            Acsn = entry.pop("sysaccession")
                            if "user_accession" in entry and len(entry["user_accession"]) > 0:
                                tempAcsn = entry["user_accession"]
                            else:
                                tempAcsn = Acsn
                            # tempAcsn = entry["user_accession"]
                            for key in relationship_connectto[Sheet]:
                                if key in entry:
                                    tempDict[key] = entry.pop(key)
                            updateurl = fullurl + '/' + Acsn
                            response = request(updateurl, json.dumps(entry), 'POST', bearer_token)
                            if response['statusCode'] != 200:
                                logging.error("%s update failed in line 583!" % Acsn)
                                noerror = 1
                                break

                            logging.info("record %s has been updated!" % Acsn)
                            AcsnDict[Sheet][tempAcsn] = Acsn
                            linkDict[Sheet][Acsn] = tempDict
                            if SheetToTable[Sheet] in submission_log:
                                submission_log[SheetToTable[Sheet]].append(Acsn)
                            else:
                                submission_log[SheetToTable[Sheet]] = []
                                submission_log[SheetToTable[Sheet]].append(Acsn)
                        elif "user_accession" in entry and len(entry["user_accession"]) > 0:
                            tempAcsn = entry["user_accession"]
                            existing = request(fullurl)
                            # check if user_accession and user combination in the database.
                            if not SheetToTable[Sheet] in existing:
                                logging.error("Error getting records of %s from database" % SheetToTable[Sheet])
                                noerror = 1
                                break
                            userAcc_found = 0
                            for DB_entries in existing[SheetToTable[Sheet]]:
                                if DB_entries["user_accession"] == tempAcsn and DB_entries["user"] == user_name:
                                    AcsnDict[Sheet][tempAcsn] = DB_entries["accession"]
                                    userAcc_found = 1
                                    logging.info("%s has been assigned with system accession %s. It won't be updated because you did not provide the system accession in the excel, but you can still link other records to it by calling %s!" % (tempAcsn, DB_entries["accession"], tempAcsn))
                                    continue
                            if not userAcc_found:
                                logging.warning("%s could not be found in the database, it will be ignored during update!" % tempAcsn)

                        else:
                            logging.warning("all rows without syster accession or user accession will be ignored during update!")
                    else:
                        if "sysaccession" in entry and len(entry["sysaccession"]) > 0:
                            tempAcsn = entry["user_accession"]
                            AcsnDict[Sheet][tempAcsn] = entry["sysaccession"]
                            continue
                        else:
                            # ipdb.set_trace()
                            # check if user_accession and user combination in the database.
                            tempDict = {}
                            tempAcsn = entry["user_accession"]
                            # existing = request(fullurl)
                            # if not SheetToTable[Sheet] in existing:
                            #     logging.error("Error getting records of %s from database" % SheetToTable[Sheet])
                            #     sys.exit(1)
                            # redundant_user_accession = 0
                            # for DB_entries in existing[SheetToTable[Sheet]]:
                            #     if DB_entries["user_accession"] == tempAcsn and DB_entries["user"] == user_name:
                            #         logging.info("Seems record %s submitted by %s already exists in the database.\nIf %s in the excel has been uploaded to the database, ignore this warning.\nIf %s is a new record, please use a non-redundant user accession; or leave the user accession blank and let our system assign a new id." % (tempAcsn, DB_entries["user"], tempAcsn, tempAcsn))
                            #         redundant_user_accession = 1
                            #         Acsn = DB_entries["accession"]
                            #         linkDict[Sheet][Acsn] = tempDict
                            #         AcsnDict[Sheet][tempAcsn] = Acsn
                            #         continue
                            # if redundant_user_accession == 0:
                            if "sysaccession" in entry:
                                entry.pop("sysaccession")
                            for key in relationship_connectto[Sheet]:
                                if key in entry:
                                    tempDict[key] = entry.pop(key)
                            response = request(fullurl, json.dumps(entry), 'POST', bearer_token)
                            if "accession" not in response:
                                logging.error("POST request failed in line 646!")
                                noerror = 1
                                break
                            else:
                                Acsn = response["accession"]
                                linkDict[Sheet][Acsn] = tempDict
                                AcsnDict[Sheet][tempAcsn] = Acsn
                                if SheetToTable[Sheet] in submission_log:
                                    submission_log[SheetToTable[Sheet]].append(Acsn)
                                else:
                                    submission_log[SheetToTable[Sheet]] = []
                                    submission_log[SheetToTable[Sheet]].append(Acsn)
                                if notest:
                                    logging.info("Record %s has been successfully uploaded to database with a system accession %s. Relationship will be established in the next step." % (tempAcsn, Acsn))
                                else:
                                    logging.info("Record %s has been successfully validated." % (acc_name[tempAcsn]))


    # ipdb.set_trace()
    if noerror:
        sys.exit("something wrong processing the excel file, quitting...")
    elif notest or mode or testlink:
        logging.info("all the records uploaded/updated, it is time to connect all the relationships!\n")
        for Sheet in all_possible_Sheets:
            if Sheet in linkDict:
                fullurl = url + '/api/' + SheetToTable[Sheet]
                for Acsn in linkDict[Sheet]:
                    existing_url = fullurl + '/' + Acsn
                    existing_record = request(existing_url)
                    existing_connection = existing_record["mainObj"]["added"]
                    # "added": {
                    #     "recruits": {
                    #         "reagent": [
                    #             ""
                    #         ]
                    #     },
                    #     "assay_input": {
                    #         "biosample": [
                    #             "TRGTSMP00021230"
                    #         ],
                    #         "library": [
                    #             "TRGTLIB000243"
                    #         ]
                    #     },
                    #     "control": {
                    #         "assay": [
                    #             ""
                    #         ]
                    #     },
                    #     "technical_replicate": {
                    #         "assay": [
                    #             ""
                    #         ]
                    #     }
                    # },
                    for connection_name in linkDict[Sheet][Acsn]:  # connection_name like "dam", "sire" or "challenge Diet"
                        # regex connection_name here. if true, use it directly, otherwise use relationship_connectto[Sheet][connection_name]:  I don't understand the comment now.
                        # linkTo = AcsnDict[Sheet][relationship_connectto[Sheet][connection_name]]
                        # if linkDict[Sheet][Acsn][connection_name] == 'NA':
                        #     continue
                        linkTo = relationship_connectto[Sheet][connection_name]
                        LinkTo = total_tabs[linkTo]
                        linkurl = fullurl + '/' + Acsn + '/' + linkTo + '/add'
                        if linkDict[Sheet][Acsn][connection_name].startswith("TRGT"):
                            linkTo_TRGTacc = linkDict[Sheet][Acsn][connection_name]
                        elif linkDict[Sheet][Acsn][connection_name] == "" or linkDict[Sheet][Acsn][connection_name] == "NA":
                            linkTo_TRGTacc = ""
                        else:  # no longer need user accession start with USR
                        # elif linkDict[Sheet][Acsn][connection_name].startswith("USR"):  # temporary for ENCODE data
                            if linkDict[Sheet][Acsn][connection_name] not in AcsnDict[LinkTo]:
                                logging.error("Can't connect %s in %s to %s. Accession %s cannot be found in %s. Please make sure all the connections have valid accessions." %
                                              (Acsn, Sheet, linkDict[Sheet][Acsn][connection_name], linkDict[Sheet][Acsn][connection_name], LinkTo))
                                noerror = 1
                            else:
                                linkTo_TRGTacc = AcsnDict[LinkTo][linkDict[Sheet][Acsn][connection_name]]
                        # else:  # temporary for ENCODE data 3 lines.
                        #     logging.warning("%s is not a valid accession. %s %s relationship %s is not established." %
                        #                     (linkDict[Sheet][Acsn][connection_name], Sheet, Acsn, connection_name))
                        if connection_name == "assay_input_biosample" or connection_name == "assay_input_library":
                            sys_connection_name = "assay_input"
                        else:
                            sys_connection_name = connection_name
                        existing_linkTo = existing_connection[sys_connection_name][linkTo][0]
                        if linkTo_TRGTacc == existing_linkTo:  # if there is only one connection!
                            if existing_linkTo != "":
                                logging.info("%s's connection to %s remains!" % (Acsn, linkTo_TRGTacc))
                            continue
                        else:
                            if existing_linkTo != "":  # delete connection.
                                removeurl = fullurl + '/' + Acsn + '/' + linkTo + '/remove'
                                RemoveBody = {"connectionAcsn": existing_linkTo, "connectionName": sys_connection_name}
                                responsestatus = request(removeurl, json.dumps(RemoveBody), 'POST', bearer_token)
                                if responsestatus["statusCode"] == 200:
                                    logging.info("%s relationship to %s has been successfully deleted!" % (Acsn, existing_linkTo))
                                else:
                                    if "message" in responsestatus:
                                        logging.error(responsestatus["message"])
                                    else:
                                        logging.error("%s's connection to %s failed to be deleted!" % (Acsn, existing_linkTo))
                                    noerror = 1
                            if linkTo_TRGTacc != "":
                                linkBody = {"connectionAcsn": linkTo_TRGTacc, "connectionName": sys_connection_name}
                                responsestatus = request(linkurl, json.dumps(linkBody), 'POST', bearer_token)
                                if responsestatus["statusCode"] == 200:
                                    logging.info("%s has been successfully linked to %s!" % (Acsn, linkTo_TRGTacc))
                                elif(linkDict[Sheet][Acsn][connection_name].startswith("TRGT") or linkDict[Sheet][Acsn][connection_name].startswith("USR")):
                                    logging.error("%s relationships is not linked, seems like an error! Please correct your relationships in your excel file, and update the database with correct connections." % (Acsn))
                                    noerror = 1
                                else:
                                    logging.warning("%s relationships is not linked. Make sure it does not matter. Or you can correct your relationships in your excel file, and update the database with correct connections." % (Acsn))
        if noerror:
            sys.exit("something wrong establishing relationships in the excel file, quitting...")
    else:
        logging.info("We did not verify relationships between records in your excel, but everything else looks fine!")
    if bool(submission_log):  # Only save not empty submissions, and also save update submissions.
        submission_details = {"details": json.dumps(submission_log), "update": mode}
        submitted_logs = request(saved_submission_url, json.dumps(submission_details), 'POST', bearer_token)
        if submitted_logs["statusCode"] == 201:
            logging.info("Submission has been successfully saved as %s!" % submitted_logs["submission_id"])
        else:
            logging.error("Fail to save submission!")


def urlfields(kind, url):
    allfieldnames = {}
    for table, Table in total_tabs.items():
        if kind == 'schema':
            urljson = url + '/schema/' + table + '.json'
        elif kind == 'relationships':
            urljson = url + '/schema/relationships/' + table + '.json'
        # Table = table[:1].upper() + table[1:].lower()
        logging.debug(urljson)
        data = urllib.request.urlopen(urljson).read().decode('utf8')
        # str_data = data.readall().decode('utf-8')
        data = json.loads(data)
        allfieldnames[Table] = data['data']

    return allfieldnames


if __name__ == '__main__':
    main()
