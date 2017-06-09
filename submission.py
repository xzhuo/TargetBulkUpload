import sys
import xlrd
from collections import OrderedDict
import urllib.request
import urllib.error
import json
import argparse
import logging
import datetime
import ipdb  # for debug

my_token = 'tokenstring'
bearer_token = 'bearer ' + my_token
url = 'http://meta.target.wustl.edu'
testurl = 'http://target.wustl.edu:8006'

# hard code version for now, will get it from a url latter:
versionNo = {"version": "2.0.2"}


def get_args():
    parser = argparse.ArgumentParser(description='simple arguments')
    parser.add_argument(
        '--template',
        '-t',
        action="store",
        dest="tem",
        choices=['V1', 'V2', 'CSV', 'json'],
        default='V2',
        help='The different version of templates. CSV is not supported yet. V1 is the original template with all the data in a single sheet. V2 seperated different tables to different sheets in excel (recommended). json is purely for testing.',
    )
    parser.add_argument(
        '--excel',
        '-x',
        action="store",
        dest="excel",
        help='The excel used for bulk upload.',
    )
    parser.add_argument(
        '--notest',
        '-n',
        action="store_true",
        dest="notest",
        help='test flag. default option is true, which will submit all the metadata to the test database. The metadata only goes to product database if this option is false. Our recommended practice is use TRUE flag (default) here first to test the integrity of metadata, only switch to FALSE once all the metadata successfully submitted to test database.',
    )
    parser.add_argument(
        '--tokenkey',
        '-k',
        action="store",
        dest="token",
        help="User's API key.",
    )
    return parser.parse_args()


def main():
    args = get_args()
    if args.token:
        global bearer_token
        bearer_token = 'bearer ' + args.token
    allfields = urlfields('schema', testurl)
    relationshipDict = urlfields('relationships', testurl)
    if versionNo["version"] not in args.excel:
        logging.error("the excel version does not match the current metadata database version. Please download the latest excel template.")
        sys.exit(1)
    connectDict = {}
    fieldname = {}  # display_name: name for connection fields
    names = {}
    for Header in relationshipDict:
        if Header in relationshipDict and 'one' in relationshipDict[Header]:
            # connectDict[Header] = {}
            # fieldname[Header] = {}
            names[Header] = relationshipDict[Header]['all']
            if 'connections' in relationshipDict[Header]:
                connectDict[Header] = {x['name']: x['to'] for x in relationshipDict[Header]['connections'] if 'to' in x and x['to'] != 'experiment'}  # exclude experiment connections
                fieldname[Header] = {x['display_name']: x['name'] for x in relationshipDict[Header]['connections'] if 'display_name' in x}

    schemarelationshipname = {}  # display_name: name for allfields
    for Header in allfields:
        print(Header)
        if Header in fieldname:
            schemarelationshipname[Header] = {**{x['text']: x['name'] for x in allfields[Header] if 'text' in x}, **fieldname[Header]}  # require python3.5 or later.
        else:
            schemarelationshipname[Header] = {x['text']: x['name'] for x in allfields[Header] if 'text' in x}

    if args.tem == "V1":
        submission = excel2JSON(args.excel, allfields, fieldname)
    elif args.tem == "V2":
        submission = multi_excel2JSON(args.excel, allfields, fieldname)
    elif args.tem == "json":
        with open(args.excel) as data_file:
            submission_in = json.load(data_file)
            submission = dict()
            for header in submission_in:
                submission[header] = list()
                for acc in submission_in[header]:
                    if acc != "NA":
                        if "User Accession" in submission_in[header][acc]:
                            submission_in[header][acc]["User accession"] = submission_in[header][acc].pop("User Accession")
                        # submission[header][acc] = {schemarelationshipname[header][key]: value for (key, value) in submission[header][acc].items()}
                        submission[header].append({schemarelationshipname[header][key]: value for (key, value) in submission_in[header][acc].items()})

                    # for subkey in submission[key][acc]:
                    #     if subkey == "User Accession":
                    #         subkey = "User accession"
                    #     if subkey in schemafieldname[key]:
                    #         submission[key][acc][schemafieldname[key][subkey]] = submission[key][acc].pop(subkey)
                    #         # replace subkey: value to schemafieldname[key][subkey]: value
                    #     elif subkey in fieldname[key]:
                    #         # replace subkey: value to fieldname[key][subkey]: value
                    #         submission[key][acc][fieldname[key][subkey]] = submission[key][acc].pop(subkey)
                    #     # elif subkey == "User Accession" or subkey == "User accession":
                    #     #     submission[key][acc]["user_accession"] = submission[key][acc].pop(subkey)
                    #     else:
                    #         ipdb.set_trace()
                    #         print("not found subkey?")
                    #         print(key)
                    #         print(subkey)

    print(json.dumps(submission, indent=4, sort_keys=True))
    accession_check(submission)
    if args.notest:
        upload(submission, connectDict, names, url)
    else:
        upload(submission, connectDict, names, testurl)
        print("If you did not find errors above, all the records were successfully uploaded to the testing database, now you can upload the same file to real database with the '--notest' flag.")


# Excel to JSON module write by Ananda
def excel2JSON(metadata_file, allfields, fieldname):
    header = ["Lab", "Bioproject", "Litter", "Mouse", "Diet", "Treatment", "Biosample", "Library", "Assay", "Reagent", "File"]  # file.readlines()
    num_head_lines = len(header)
    wb = xlrd.open_workbook(metadata_file)
    sh = wb.sheet_by_index(0)
    numrows = sh.nrows
    j = 0
    header_line = []
    intermediate_rows = []
    # num_cols = [10, 5, 11, 15, 7, 18, 25, 11, 16, 11, 29]  # no longer need this now

    for i in range(0, numrows):
        if(j < num_head_lines and sh.cell(i, 0).value == header[j].rstrip()):
            header_line.append(i)
            if(j > 0):
                intermediate_rows.append(i - header_line[j - 1] - 1)
            j += 1

    intermediate_rows.append(i - header_line[j - 1])
    super_data = OrderedDict()
    for i in range(0, num_head_lines):
        data_list = []
        pointer = header_line[i]
        hr = pointer + 1
        key = str(sh.cell_value(pointer, 0)).rstrip()  # Xiaoyu: remove trailing white spaces
        for j in range(1, intermediate_rows[i]):
            data = OrderedDict()
            row_values = sh.row_values(hr + j)
            valuelength = 0
            for value in row_values:
                valuelength += len(str(value))
            if valuelength == 0:
                continue
            k = 0
            while len(str(sh.cell(hr, k).value).rstrip()):
                # for k in range(0, num_cols[i]):
                Subkey = str(sh.cell(hr, k).value).rstrip()
                # Lot ID and Exposure Classification
                subkey = "NA"
                subkeytype = "unknown"
                if Subkey == "Accession":
                    subkey = "User Accession"
                    subkeytype = "string"
                if Subkey == "Litter size (survived)":
                    Subkey = "Litter size (survived to weaning)"
                for fielddict in allfields[key]:
                    if fielddict["text"] == Subkey:
                        subkey = fielddict["name"]
                        subkeytype = fielddict["type"]
                # subkey = Subkey[:1].lower() + Subkey[1:]  # first character lowercase
                if subkey == "NA" and key in fieldname and Subkey in fieldname[key]:
                    subkey = fieldname[key][Subkey]
                    subkeytype = "string"
                # subkeytype = "string"  # wait until the correct type set!! Temporary line here
                if subkey == "NA":
                    logging.warning(key)
                    logging.warning(Subkey)
                    logging.warning("field name in excel not in the database!")
                else:
                    value = row_values[k]
                    if len(value) == 0 and subkey != 'sysaccession':
                        value = 'NA'
                    if subkeytype == "number":
                        try:
                            data[subkey] = int(value)
                        except:
                            data[subkey] = -1
                    # elif subkeytype == "date":
                    #     data[subkey] =
                    else:
                        data[subkey] = str(value)

                    # if isinstance(value, float):
                    #     if subkey.endswith('Id'):
                    #         data[subkey] = str(value)
                    #     else:
                    #         data[subkey] = int(value)
                    # else:
                    #     data[subkey] = str(value)
                    # data[subkey] = row_values[k]
                k += 1
            data_list.append(data)

        super_data[key] = data_list
    j = json.dumps(super_data)
    # with open('TaRGET_metadata.json', 'w') as f:
    #     f.write(j)
    print("Excel processing DONE")
    return json.loads(j)


def multi_excel2JSON(file, allfields, fieldname):
    wb = xlrd.open_workbook(file)
    sheet_names = wb.sheet_names()
    super_data = OrderedDict()
    for key in sheet_names:
        if key == "Instructions" or key == "Lists":
            continue
        sheet = wb.sheet_by_name(key)
        keys = [str(sheet.cell(1, col_index).value).rstrip() for col_index in range(sheet.ncols)]  # start from row number 1 to skip header
        dict_list = []
        for row_index in range(2, sheet.nrows):
            # d = {keys[col_index]: str(sheet.cell(row_index, col_index).value.rstrip()) for col_index in range(sheet.ncols)}  # use string first
            d = OrderedDict()
            for col_index in range(sheet.ncols):
                Subkey = keys[col_index]
                subkey = "NA"
                subkeytype = "unknown"
                if Subkey == "System Accession":
                    subkey = "sysaccession"
                    subkeytype = "string"
                if Subkey == "User Accession":
                    Subkey = "User accession"
                    subkeytype = "string"
                for fielddict in allfields[key]:
                    if fielddict["text"] == Subkey:
                        subkey = fielddict["name"]
                        subkeytype = fielddict["type"]
                    if fielddict["text"] == "User accession":
                        accession_rule = fielddict["placeholder"][:-4]
                # subkey = Subkey[:1].lower() + Subkey[1:]  # first character lowercase
                if subkey == "NA" and key in fieldname and Subkey in fieldname[key]:
                    subkey = fieldname[key][Subkey]
                    subkeytype = "string"

                if subkey == "zip_code" or subkey == "batchId":
                    subkeytype = "string"
                # subkeytype = "string"  # wait until the correct type set!! Temporary line here
                if subkey == "NA":
                    print(key)
                    print(Subkey)
                    print("field name in excel not in the database!")
                else:
                    value = sheet.cell(row_index, col_index).value
                    if subkey == "strand_specificity":
                        value = "TRUE"  # not enough, there are other restricted columns
                    if value != '' or subkey == "sysaccession":
                        if subkeytype == "string":
                            d[subkey] = str(value).rstrip()  # use string for now. May use number later.
                        elif subkeytype == "date":
                            # ipdb.set_trace()
                            d[subkey] = xlrd.xldate.xldate_as_datetime(value, wb.datemode).date().isoformat()
                        else:
                            d[subkey] = value
            dict_list.append(d)
            # if ("user_accession" in d and d["user_accession"].startswith(accession_rule)):
            #     dict_list.append(d)
            # else:
            #     logging.error("There has to be a valid user accession in %s" % key)
            #     sys.exit(1)

        super_data[key] = dict_list

    # j = json.dumps(super_data)
    print("Excel processing DONE")
    # return json.loads(j)
    return super_data


def request(url, parameter, method):
    bin_data = parameter.encode('ascii')
    req = urllib.request.Request(url, data=bin_data, method=method)
    req.add_header('Content-Type', 'application/json')
    req.add_header('Accept', 'application/json')
    req.add_header('Authorization', bearer_token)  # add token 'bearer hed35h5i1ajf07g5'
    try:
        response = urllib.request.urlopen(req)
    except urllib.error.URLError as e:
        ResponseData = e.read().decode("utf8", 'ignore')
        ResponseDict = json.loads(ResponseData)
        logging.error(ResponseDict["message"])
        sys.exit(1)

    else:
            ResponseDict = json.loads(response.read().decode('ascii'))
            if "accession" in ResponseDict:
                # return response.accession
                return ResponseDict["accession"]


def accession_check(metadata):  # if there is duplicated user accession number.
    for key in metadata:
        accessionlist = []
        for i in metadata[key]:
            if "user_accession" in i:
                user_accession = i["user_accession"]
                if user_accession not in accessionlist:
                    accessionlist.append(user_accession)
                else:
                    logging.error("duplicates user accession %s in %s!" % (user_accession, key))
                    sys.exit(1)


def upload(metadata, connectDict, names, url):
    AcsnDict = {}
    linkDict = {}

    orderList = ["Lab", "Bioproject", "Diet", "Treatment", "Reagent", "Litter", "Mouse", "Biosample", "Library", "Assay", "File"]
    for header in orderList:
        print(header)

        if header in metadata:
            # swap column name in excel to field name in database
            # for entry in metadata[header]:
            #     print(header)
            #     for key in entry:
            #         print(key)
            #         if header in fieldname and key in fieldname[header]:
            #             entry[fieldname[header][key]] = entry.pop(key)
            #             # del entry[key]

            AcsnDict[header] = {}
            fullurl = url + '/api/' + names[header]
            if header not in connectDict or len(connectDict[header]) == 0:  # if nothing to connect in the database during bulk upload
                for entry in metadata[header]:  # metadata[header] is a list of dicts.
                    if "sysaccession" in entry and len(entry["sysaccession"]) > 0:
                        Acsn = entry.pop("sysaccession")
                        if "user_accession" in entry and len(entry["user_accession"]) > 0:
                            tempAcsn = entry["user_accession"]
                        else:
                            tempAcsn = entry["sysaccession"]
                        updateurl = fullurl + '/' + Acsn
                        request(updateurl, json.dumps(entry), 'POST')
                        print("record %s has been updated!" % Acsn)
                        AcsnDict[header][tempAcsn] = Acsn
                    else:
                        tempAcsn = entry["user_accession"]
                        if "sysaccession" in entry:
                            entry.pop("sysaccession")
                        Acsn = request(fullurl, json.dumps(entry), 'POST')
                        AcsnDict[header][tempAcsn] = Acsn
                        # print("%s upload done" % (tempAcsn))
                        print("Record %s has been successfully uploaded to database with a system accession %s" % (tempAcsn, Acsn))

            else:  # if connections need to be established: delete linkage in the dict, post request, and remember which connections need to add later.
                linkDict[header] = {}
                for entry in metadata[header]:  # metadata[header] is a list of dicts.
                    if "sysaccession" in entry and len(entry["sysaccession"]) > 0:
                        tempDict = {}
                        Acsn = entry.pop("sysaccession")
                        if "user_accession" in entry and len(entry["user_accession"]) > 0:
                            tempAcsn = entry["user_accession"]
                        else:
                            tempAcsn = entry["sysaccession"]
                        # tempAcsn = entry["user_accession"]
                        for key in connectDict[header]:
                            if key in entry:
                                tempDict[key] = entry.pop(key)
                        updateurl = fullurl + '/' + Acsn
                        request(updateurl, json.dumps(entry), 'POST')
                        print("record %s has been updated!" % Acsn)
                        AcsnDict[header][tempAcsn] = Acsn
                        linkDict[header][Acsn] = tempDict

                    else:
                        # ipdb.set_trace()
                        tempDict = {}
                        tempAcsn = entry["user_accession"]
                        if "sysaccession" in entry:
                            entry.pop("sysaccession")
                        for key in connectDict[header]:
                            if key in entry:
                                tempDict[key] = entry.pop(key)
                        Acsn = request(fullurl, json.dumps(entry), 'POST')
                        if Acsn is None:
                            logging.error("POST request failed!")
                            sys.exit(1)
                        else:
                            print("accesion created is %s" % Acsn)
                            linkDict[header][Acsn] = tempDict
                            AcsnDict[header][tempAcsn] = Acsn
                            print("%s upload done without link\n" % (tempAcsn))
                            print("Record %s has been successfully uploaded to database with a system accession %s. But there are relationships need to be linked." % (tempAcsn, Acsn))

    # ipdb.set_trace()
    for header in orderList:
        if header in linkDict:
            fullurl = url + '/api/' + names[header]
            for Acsn in linkDict[header]:
                for connection_name in linkDict[header][Acsn]:  # connection_name like "dam", "sire" or "challenge Diet"
                    # regex connection_name here. if true, use it directly, otherwise use connectDict[header][connection_name]:  I don't understand the comment now.
                    # linkTo = AcsnDict[header][connectDict[header][connection_name]]
                    if linkDict[header][Acsn][connection_name] == 'NA':
                        continue
                    linkTo = connectDict[header][connection_name]
                    LinkTo = linkTo[:1].upper() + linkTo[1:]
                    linkurl = fullurl + '/' + Acsn + '/' + linkTo + '/add'
                    if linkDict[header][Acsn][connection_name].startswith("TRGT"):
                        if connection_name == "assay_input_biosample" or connection_name == "assay_input_library":
                            # linkBody = {names[linkTo]['Acsn']: linkDict[header][Acsn][connection_name], "connectionName": "assay_input"}
                            linkBody = {"connectionAcsn": linkDict[header][Acsn][connection_name], "connectionName": "assay_input"}
                        else:
                            linkBody = {"connectionAcsn": linkDict[header][Acsn][connection_name], "connectionName": connection_name}
                    else:
                        if connection_name == "assay_input_biosample" or connection_name == "assay_input_library":
                            # linkBody = {names[linkTo]['Acsn']: linkDict[header][Acsn][connection_name], "connectionName": "assay_input"}
                            linkBody = {"connectionAcsn": AcsnDict[LinkTo][linkDict[header][Acsn][connection_name]], "connectionName": "assay_input"}
                        else:
                            linkBody = {"connectionAcsn": AcsnDict[LinkTo][linkDict[header][Acsn][connection_name]], "connectionName": connection_name}
                    request(linkurl, json.dumps(linkBody), 'POST')
                    print("%s relationships successfully linked!" % (Acsn))


def getfields():
    allfieldnames = {}
    for header in ("assay", "bioproject", "biosample", "challenge", "diet", "drug", "experiment", "file", "lab", "library", "litter", "mouse", "reagent", "replicate", "treatment"):
        filename = 'fields/' + header + '.js'
        string = '[{'
        with open(filename, mode='r', encoding='utf-8') as f:
            for line in f:
                line = line.rstrip()
                line = line.lstrip()
                if not (line.startswith('var') or line.endswith(';')):
                    line = line.replace("'", "\"")
                    index = line.find(":")
                    if index > 0:
                        if line.startswith("type"):
                            line = '"type": "' + line[index + 2:-1] + '",'
                        else:
                            line = '"' + line[:index] + '"' + line[index:]
                    string = string + line
        string = string + '}]'
        Header = header[:1].upper() + header[1:]
        allfieldnames[Header] = json.loads(string)
    return allfieldnames


def urlfields(kind, url):
    allfieldnames = {}
    for header in ("assay", "bioproject", "biosample", "diet", "drug", "experiment", "file", "lab", "library", "litter", "mouse", "reagent", "replicate", "treatment"):
        if kind == 'schema':
            urljson = url + '/schema/' + header + '.json'
        elif kind == 'relationships':
            urljson = url + '/schema/relationships/' + header + '.json'
        Header = header[:1].upper() + header[1:]
        print(urljson)
        data = urllib.request.urlopen(urljson).read().decode('utf8')
        # str_data = data.readall().decode('utf-8')
        data = json.loads(data)
        allfieldnames[Header] = data['data']

    return allfieldnames


if __name__ == '__main__':
    main()
