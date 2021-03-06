import pprint
import logging
import xlrd
import re
import sheetreader

CTYPE_NUMBER = 2
CTYPE_DATE = 3
CTYPE_BOOLEAN = 4


class Validator:
    def __init__(self, meta_structure):
        self.meta_structure = meta_structure

    def verify_column_names(self, sheet_obj):
        """
        Compare all the columns names in the worksheet with correspondence databases fields.

        Pops up a warning if there is any database field missing in the worksheet.
        Also gives a warning if any column in the worksheet will be skipped because it does not match a field in the database.
        """
        reader = sheetreader.SheetReader(self.meta_structure)
        sheet_name = sheet_obj.name
        column_headers_from_sheet = set(reader.get_sheet_headers(sheet_obj))
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

    def duplication_check(self, poster, sheet_data):
        """
        Make sure all the system accessions and user accessions are unique in the sheet. (except user_accession=="NA-web")

        In the input sheet_data, each record has been validated.
        At least one of user or system accession exists, the other one must be "" if don't exists.

        If the record exists in the database, make sure both system and user accession match the record in the database.
        If there is only one accession in the sheet record, fetch and fill in the other accession from database.

        In the end, for records exist in database, both system and user accession must exist in the record;
        fo new records, only user accession in the record, system accession is ""
        """

        sheet_name = sheet_data.name
        existing_sheet_data = poster.fetch_all(sheet_name)
        existing_sheet_data_uniq = [x for x in existing_sheet_data if x["user_accession"] != "NA-web"]  # python2.7+, remove NA-web so I can get a list with uniq user_accessions.
        existing_user_accessions = [x['user_accession'] for x in existing_sheet_data_uniq]
        if len(existing_user_accessions) != len(set(existing_user_accessions)):
            raise ValidatorError("redundant user accession exists in the %s, please contact dcc to fix the issue!" % sheet_name)
            # sys.exit("redundant user accession exists in the %s, please contact dcc to fix the issue!" % sheet_name)
        existing_user_system_accession_pair = {x["user_accession"]: x["accession"] for x in existing_sheet_data_uniq}  # python2.7+
        existing_system_accessions = existing_user_system_accession_pair.values()
        # FIMXE user_accessions_in_sheet = Set(...)
        # system_accessions_in_sheet = Set(...)
        user_accession_list = []
        system_accession_list = []
        for record in sheet_data.all_records:
            accession = record.schema["accession"]
            user_accession = record.schema["user_accession"]
            """
            three possibilities:
            both user and system accession exist;
            system accession exists but user accession is "";
            system accession is "" but user accession exists.
            """
            if user_accession != "" and accession != "":
                if user_accession == "NA-web":  # add the system accession to the list and no more validation if it is NA-web.
                    system_accession_list.append(accession)
                else:
                    if user_accession in existing_user_accessions and existing_user_system_accession_pair[user_accession] == accession:
                        if user_accession not in user_accession_list and accession not in system_accession_list:
                            user_accession_list.append(user_accession)
                            system_accession_list.append(accession)
                        else:
                            raise ValidatorError("redundant accession %s or %s in %s!" % (user_accession, accession, sheet_name))
                            # sys.exit("redundant accession %s or %s in %s!" % (user_accession, accession, sheet_name))
                    else:
                        raise ValidatorError("accession %s or %s in %s does not match our database record!" % (user_accession, accession, sheet_name))
            elif user_accession == "" and accession != "":
                if accession in system_accession_list:
                    raise ValidatorError("System accession %s in %s in invalid. It is a redundant accession in the worksheet." % (accession, sheet_name))
                elif accession not in existing_system_accessions:
                    raise ValidatorError("System accession %s in %s in invalid. It does not exist in the database." % (accession, sheet_name))
                else:
                    matching_user_accession = [k for k, v in existing_user_system_accession_pair.items() if v == accession][0]
                    record.schema["user_accession"] = matching_user_accession
                    user_accession_list.append(matching_user_accession)
                    system_accession_list.append(accession)
            elif user_accession != "" and accession == "":
                if user_accession in user_accession_list:
                    raise ValidatorError("User accession %s in %s in invalid. It is a redundant accesion in the worksheet." % (user_accession, sheet_name))
                elif user_accession in existing_user_accessions:
                    matching_accession = existing_user_system_accession_pair[user_accession]
                    record.schema["accession"] = matching_accession
                    user_accession_list.append(user_accession)
                    system_accession_list.append(matching_accession)
                else:
                    user_accession_list.append(user_accession)
            else:
                raise ValidatorError("Unexpected validation error")

    def cell_value_audit(self, sheet_name, column_header, cell_obj, datemode):
        """
        :param: column_header - the column_header of the cell you want to add.
        :param: cell_obj - the cell object from xrld package.
        :validate and add the cell value to the row_data:
        modify some invalid value in excel sheet to match database requirement.
        empty accessions ("" or "NA") become "".
        "NA" for date become 1970-01-01.
        "NA" in number fields become -1.
        "" in text become "NA"
        all float value round to 2 digits.
        """
        value = cell_obj.value
        ctype = cell_obj.ctype
        # Now begin validation:

        # change accessions from "NA" to "":
        if column_header == "User accession" or column_header == "System Accession":
            value = "" if value == "NA" else value

        # Validate other fields:
        else:
            column_schema = self.meta_structure.get_column_dict(sheet_name, column_header)
            data_type = column_schema['type']
            required = column_schema['required']
            if required and value == "":
                raise ValidatorError("column %s in %s is a required!" % (column_header, sheet_name))

            elif ctype == CTYPE_BOOLEAN:
                if value:
                    value = "TRUE"
                else:
                    value = "FALSE"
            # now consider data_type:
            elif data_type == "text":
                if ctype == CTYPE_NUMBER:
                    if "(include units)" in column_header:
                        raise ValidatorError("please include units for %s in %s" % (column_header, sheet_name))
                    else:
                        value = str(value).rstrip('0').rstrip('.')  # delete trailing 0s if it is a number.
                elif value == "":
                    value = "NA"
            elif data_type == "date":
                if value == "NA" or value == "":
                    value = '1970-01-01'
                elif ctype == CTYPE_DATE:
                    value = xlrd.xldate.xldate_as_datetime(value, datemode).date().isoformat()
            elif data_type == "number" or data_type == "float":
                if ctype == CTYPE_NUMBER:
                    value = round(value, 2)
                elif value == "NA" or value == "":  # assign number field to -1 if it is NA in the excel.
                    value = -1
                    logging.debug("Change NA to -1 for %s in %s." % (column_header, sheet_name))
                else:
                    raise ValidatorError("please use number for %s in %s" % (column_header, sheet_name))
            elif data_type == "textnumber":
                if ctype == CTYPE_NUMBER:
                    value = round(value, 2)
                elif value == "":
                    value = "NA"
            if "values_restricted" in column_schema and column_schema["values_restricted"] and value not in column_schema["values"]:
                raise ValidatorError("%s in column %s in %s is not from the provided list: %s!" % (value, column_header, sheet_name, column_schema["values"]))
            # if column_header in self.meta_structure.get_link_column_headers(sheet_name) and (not ("allow_multiple" in column_schema and column_schema["allow_multiple"])) and re.search(',',value):
                # raise ValidatorError("relationship column %s in %s does not allow multiple connection!" % (column_header, sheet_name))
        return value

    def row_value_audit(self, row_data):
        """
        1. For records without user accession or system accession, assign "" to the field.
        2. Only add the row_data to self if:
        Both user accession and system accession follow the accession rule;
        One of them follows the accession rule, and the other is "".

        """
        sheet_name = row_data.sheet_name
        user_accession_rule = self.meta_structure.get_user_accession_rule(sheet_name)
        system_accession_rule = self.meta_structure.get_system_accession_rule(sheet_name)

        if "user_accession" not in row_data.schema:
            row_data.schema["user_accession"] = ""
        user_accession = row_data.schema["user_accession"]
        if "accession" not in row_data.schema:
            row_data.schema["accession"] = ""
        system_accession = row_data.schema["accession"]
        valid = False
        if user_accession.startswith(user_accession_rule) and system_accession.startswith(system_accession_rule):
            valid = True
        elif user_accession.startswith(user_accession_rule) and system_accession == "":
            valid = True
        elif (user_accession == "" or user_accession == "NA-web") and system_accession.startswith(system_accession_rule):
            valid = True
        if not valid:
            raise ValidatorError("Either user accession or system accession wrong in the excel file.\n\
                    Record %s %s in %s is not valid!" % (system_accession, user_accession, sheet_name))

        valid = False
        if sheet_name == 'Assay':  # ATAC-seq links to biosample, starting amount of cells,  others link to library, starting amount of dna.
            valid = True
            # if (row_data.schema["technique"] == "ATAC-seq" or row_data.schema["technique"] == "ChIP-seq") and row_data.schema["starting_nucleic_acid"] == "NA" and row_data.relationships["assay_input"]["library"] == [""]:
            #     valid = True
            # elif row_data.schema["technique"] != "ATAC-seq" and row_data.schema["technique"] != "ChIP-seq" and row_data.schema["starting_cells"] == "NA" and row_data.relationships["assay_input"]["biosample"] == [""]:
            #     valid = True
            # else:
            #     raise ValidatorError("ATAC-seq assay starts from cells, other assays start from nucleic acid. ATAC-seq record can only connect to biosample, other type assay record can only connect to library.\n\
            #         Record %s %s in %s is not valid, quit!" % (system_accession, user_accession, sheet_name))

        elif sheet_name == "Biosample":
            if row_data.schema["tissue_classification"] == "Surrogate" and (row_data.schema["tissue"].startswith("Blood") or row_data.schema["tissue"] == "Skin"):
                valid = True
            elif row_data.schema["tissue_classification"] == "Target" and (row_data.schema["tissue"] != "Blood" and row_data.schema["tissue"] != "Skin"):
                valid = True
            else:
                raise ValidatorError("Only skin and blood can be surrogate,\n\
                    Record %s %s in %s is not valid, quit!" % (system_accession, user_accession, sheet_name))
            if (row_data.schema["cell_culture_protocol"] == "NA" and row_data.schema["culture_length"] == "NA" and (row_data.schema["passage_number"] == -1 or row_data.schema["passage_number"] == 0)) or (row_data.schema["collection_protocol"] != "NA" and row_data.schema["culture_length"] != "NA" and row_data.schema["passage_number"] >= 0):
                valid = True
            else:
                raise ValidatorError("Only cell culture samples are required to have collection protocol, culture length and passage number,\n\
                    Record %s %s in %s is not valid, quit!" % (system_accession, user_accession, sheet_name))

        elif sheet_name == "File":  # paired end information
            if row_data.schema["run_type"] == "single-end" and row_data.relationships["paired_file"]["file"] == [""]:
                valid = True
            elif row_data.schema["run_type"] == "paired-end" and row_data.schema["pair"] != "NA" and row_data.relationships["paired_file"]["file"] != [""]:
                valid = True
            # if row_data.schema["run_type"] == "single-end" and row_data.schema["pair"] == "NA" and row_data.relationships["paired_file"]["file"] == [""]:
            #     valid = True
            # elif row_data.schema["run_type"] == "paired-end" and row_data.schema["pair"] != "NA" and row_data.relationships["paired_file"]["file"] != [""]:
            #     valid = True
            else:
                raise ValidatorError("column Pair and Paired file must be blank for single end records, but they are required for paired end records.\n\
                    Record %s %s in %s is not valid, quit!" % (system_accession, user_accession, sheet_name))
        elif sheet_name == "Mouse":
            if (row_data.schema["fasted"] == "Yes" and row_data.schema["fasted_hours"] > 0) or (row_data.schema["fasted"] == "No" and (row_data.schema["fasted_hours"] == 0 or row_data.schema["fasted_hours"] == -1)):
                valid = True
            else:
                raise ValidatorError("Only for fasted mouse, fasted hours are required.\n\
                    Record %s %s in %s is not valid, quit!" % (system_accession, user_accession, sheet_name))

        elif sheet_name == "Reagent":  # Purification method, Host organism, Isotype, Clonality, Antigen sequence filled out only if Reagent == antibody
            if row_data.schema["reagent"] == "Antibody":
                if row_data.schema["host"] != "NA" and row_data.schema["purification_method"] != "NA" and row_data.schema["isotype"] != "NA" and row_data.schema["clonality"] != "NA" and row_data.schema["antigen_sequence"] != "NA":
                    valid = True
                else:
                    raise ValidatorError("Purification method, Host organism, Isotype, Clonality, Antigen sequence are all requied if Reagent is antibody.\n\
                        Record %s %s in %s is not valid, quit!" % (system_accession, user_accession, sheet_name))
            else:
                if row_data.schema["host"] == "NA" and row_data.schema["purification_method"] == "NA" and row_data.schema["isotype"] == "NA" and row_data.schema["clonality"] == "NA" and row_data.schema["antigen_sequence"] == "NA":
                    valid = True
                else:
                    raise ValidatorError("Purification method, Host organism, Isotype, Clonality, Antigen sequence should not be filled if Reagent is not antibody.\n\
                        Record %s %s in %s is not valid, quit!" % (system_accession, user_accession, sheet_name))
        elif sheet_name == "Treatment":  # Challenge after exposure must link to challenge diet

            if (row_data.schema["challenge_after_exposure"] != "NA" and row_data.relationships["challenged_with"]["diet"] == [""]) or (row_data.schema["challenge_after_exposure"] == "NA" and row_data.relationships["challenged_with"]["diet"] == [""]):
                valid = True
            else:
                raise ValidatorError("Only rows with challenge after exposure have to fill in challenge diet.\n\
                    Record %s %s in %s is not valid, quit!" % (system_accession, user_accession, sheet_name))
        elif sheet_name == "Bioproject":  # no specific validation for bioproject.
            valid = True
        elif sheet_name == "Litter":  # no specific validation for litter.
            valid = True
        elif sheet_name == "Diet":  # no specific validation for diet.
            valid = True
        elif sheet_name == "Library":  # no specific validation for library.
            valid = True
        elif sheet_name == "Mergedfile":  # no specific validation for mergedfile.
            valid = True
        elif sheet_name == "Experiment":  # no specific validation for mergedfile.
            valid = True
        elif sheet_name == "Lab":  # no specific validation for lab.
            valid = True

        else:
            raise ValidatorError("record %s %s in %s is not valid and will be skipped!" % (system_accession, user_accession, sheet_name))
        return valid


class ValidatorError(Exception):
    """catch my validation errors"""
    pass
